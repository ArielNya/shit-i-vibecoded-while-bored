"""Shared fixtures: a real Godot editor running the plugin, one per test module.

Skipped unless GODOT_BIN points at a Godot 4.7+ editor binary. The editor opens a copy
of tests/fixtures/demo_project (in a folder with a space in its name, to exercise path
handling) with scenes/main.tscn open.

By default the editor runs --headless. A module can set
    EDITOR_OPTIONS = {"display": True}
to run it with a real window under Xvfb (needs xvfb-run and Mesa), e.g. for screenshots,
and "user_args": [...] for extra plugin arguments (after `--`).
"""

import asyncio
import base64
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from mcp import Client

from godot_mcp import protocol
from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "demo_project"
ADDON = ROOT / "addon" / "addons" / "godot_mcp"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
STARTUP_TIMEOUT = 180
MAIN_SCENE = "res://scenes/main.tscn"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def editor_options(request):
    return getattr(request.module, "EDITOR_OPTIONS", {})


@pytest.fixture(scope="module")
def project_dir(tmp_path_factory):
    """A fresh copy of the demo project with the plugin installed."""
    path = tmp_path_factory.mktemp("projects") / "demo project"
    shutil.copytree(FIXTURE, path)
    shutil.copytree(ADDON, path / "addons" / "godot_mcp")
    return path


@pytest.fixture(scope="module")
def token_file(tmp_path_factory):
    return tmp_path_factory.mktemp("config") / "godot-mcp" / "token"


async def _wait_until_ready(port, token_file, proc, log):
    """On first open the editor imports everything, then opens scenes/main.tscn; the
    listener is up long before that. Wait until the scene is open and scanning is done."""
    bridge = GodotBridge(BridgeConfig(port=port, timeout=30, token=None))
    bridge.config.token = protocol.read_token_file(token_file)
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"Godot exited (code {proc.returncode}):\n" + "".join(log))
            ping = await bridge.call("ping")
            info = await bridge.call("get_project_info")
            if ping.get("editor_ready") and info["editor"]["edited_scene"] == MAIN_SCENE:
                return
            await asyncio.sleep(0.5)
        pytest.fail("The editor never opened the demo scene:\n" + "".join(log))
    finally:
        await bridge.close()


@pytest.fixture(scope="module")
def editor(project_dir, token_file, editor_options):
    """Starts the editor; yields {"port", "lsp_port", "log"}."""
    godot = os.environ.get("GODOT_BIN")
    if not godot:
        pytest.skip("set GODOT_BIN to a Godot 4.7+ editor binary to run integration tests")
    lsp_port = _free_port()
    cmd = [godot, "--editor", "--path", str(project_dir), "--lsp-port", str(lsp_port)]
    if editor_options.get("display"):
        xvfb = shutil.which("xvfb-run")
        if xvfb is None:
            pytest.skip("xvfb-run is needed to run the editor with a window")
        cmd = [xvfb, "-a", "-s", "-screen 0 1600x900x24", *cmd, "--rendering-driver", "opengl3"]
    else:
        cmd.insert(1, "--headless")
    cmd += [
        "scenes/main.tscn",
        "--",
        "--mcp-port=0",
        f"--mcp-lsp-port={lsp_port}",
        "--mcp-test-hooks",
        *editor_options.get("user_args", []),
    ]
    env = {**os.environ, protocol.TOKEN_FILE_ENV: str(token_file)}
    proc = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    lines: queue.Queue = queue.Queue()
    log: list[str] = []

    def pump():
        for line in proc.stdout:
            log.append(line)
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    try:
        port = None
        while port is None:
            try:
                line = lines.get(timeout=STARTUP_TIMEOUT)
            except queue.Empty:
                pytest.fail("Godot did not start the MCP listener in time:\n" + "".join(log))
            if line is None:
                pytest.fail(f"Godot exited (code {proc.wait()}):\n" + "".join(log))
            if line.startswith("godot-mcp: listening on"):
                port = int(line.rsplit(":", 1)[1])
        asyncio.run(_wait_until_ready(port, token_file, proc, log))
        yield {"port": port, "lsp_port": lsp_port, "log": log}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        if os.environ.get("GODOT_MCP_SHOW_EDITOR_LOG"):
            sys.stderr.write("".join(log))


@pytest.fixture
async def bridge(editor, token_file):
    token = protocol.read_token_file(token_file)
    assert token, "the plugin should have created the token file"
    b = GodotBridge(BridgeConfig(port=editor["port"], timeout=120, token=token))
    yield b
    await b.close()


@pytest.fixture
async def client(bridge):
    async with Client(create_server(bridge)) as c:
        yield c


@pytest.fixture
def call(client):
    """await call("tool", arg=...) -> parsed JSON; fails the test on a tool error."""

    async def call_json(tool, **args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        return json.loads(result.content[0].text)

    return call_json


@pytest.fixture
def call_error(client):
    """await call_error("tool", ...) -> error text; fails the test if the tool succeeds."""

    async def call(tool, **args):
        result = await client.call_tool(tool, args)
        assert result.is_error, result.content
        return result.content[0].text

    return call


@pytest.fixture
def call_image(client):
    async def call(tool, **args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        image, meta = result.content
        assert image.type == "image" and image.mime_type == "image/png"
        assert base64.b64decode(image.data).startswith(PNG_MAGIC)
        return json.loads(meta.text)

    return call
