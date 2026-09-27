"""Shared fixtures: a real headless Blender running the add-on, one per test module.

Skipped unless one of these is set:
    BLENDER_BIN=/path/to/blender            a Blender executable
    BLENDER_PYTHON=/path/to/python          a Python with the `bpy` wheel installed

Blender starts from its factory scene: "Cube" (material "Material"), "Camera", "Light".
Rendering needs OpenGL; on a GPU-less Linux box install Mesa (libegl1 libgl1-mesa-dri).
"""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

from blender_mcp.bridge import BlenderBridge, BridgeConfig
from blender_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_in_blender.py"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _command() -> list[str] | None:
    if blender := os.environ.get("BLENDER_BIN"):
        return [blender, "--background", "--factory-startup", "--python", str(SCRIPT)]
    if python := os.environ.get("BLENDER_PYTHON"):
        return [python, str(SCRIPT)]
    return None


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """The folder file tools may use in this module's Blender."""
    return tmp_path_factory.mktemp("workspace")


@pytest.fixture(scope="module")
def blender_port(workspace):
    cmd = _command()
    if cmd is None:
        pytest.skip("set BLENDER_BIN or BLENDER_PYTHON to run Blender integration tests")
    proc = subprocess.Popen(
        [*cmd, "--", "--port", "0", "--workspace", str(workspace)],
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
    )
    try:
        port = None
        for line in proc.stdout:
            if line.startswith("BLENDER_MCP_READY"):
                port = int(line.rsplit(":", 1)[1])
                break
        if port is None:
            pytest.fail(f"Blender exited before the listener started (code {proc.wait()})")
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
async def client(blender_port):
    bridge = BlenderBridge(BridgeConfig(port=blender_port, timeout=120))
    async with Client(create_server(bridge)) as client:
        yield client
    await bridge.close()


@pytest.fixture
def call(client):
    """await call("tool", arg=...) -> parsed JSON; fails the test on a tool error."""

    async def call_json(tool, **args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        return json.loads(result.content[0].text)

    return call_json


@pytest.fixture
def call_image(client):
    """await call_image("tool", ...) -> metadata; asserts a PNG image came back."""

    async def call(tool, **args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, result.content
        image, meta = result.content
        assert image.type == "image" and image.mime_type == "image/png"
        assert base64.b64decode(image.data).startswith(PNG_MAGIC)
        return json.loads(meta.text)

    return call


@pytest.fixture
def call_error(client):
    """await call_error("tool", ...) -> error text; asserts the call failed."""

    async def call(tool, **args):
        result = await client.call_tool(tool, args)
        assert result.is_error, result.content
        return result.content[0].text

    return call
