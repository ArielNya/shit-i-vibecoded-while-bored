"""Runs the add-on inside a real headless Blender and drives it through the MCP server.

Skipped unless one of these is set:
    BLENDER_BIN=/path/to/blender            a Blender executable
    BLENDER_PYTHON=/path/to/python          a Python with the `bpy` wheel installed
"""

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

pytestmark = pytest.mark.anyio


def _command() -> list[str] | None:
    if blender := os.environ.get("BLENDER_BIN"):
        return [blender, "--background", "--factory-startup", "--python", str(SCRIPT)]
    if python := os.environ.get("BLENDER_PYTHON"):
        return [python, str(SCRIPT)]
    return None


@pytest.fixture(scope="module")
def blender_port():
    cmd = _command()
    if cmd is None:
        pytest.skip("set BLENDER_BIN or BLENDER_PYTHON to run Blender integration tests")
    proc = subprocess.Popen(
        [*cmd, "--", "--port", "0"],
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


async def test_ping_and_scene_info(blender_port):
    bridge = BlenderBridge(BridgeConfig(port=blender_port, timeout=20))
    async with Client(create_server(bridge)) as client:
        ping = await client.call_tool("ping", {})
        assert not ping.is_error, ping.content
        ping_data = json.loads(ping.content[0].text)
        assert ping_data["pong"] is True
        assert ping_data["blender_version"]

        info = await client.call_tool("get_scene_info", {})
        assert not info.is_error, info.content
        scene = json.loads(info.content[0].text)
        # Blender's factory startup scene: cube, camera, light.
        assert scene["object_count"] == 3
        assert scene["objects_by_type"] == {"MESH": 1, "CAMERA": 1, "LIGHT": 1}
        assert scene["camera"] == "Camera"
        assert scene["collections"]["children"][0]["name"] == "Collection"
    await bridge.close()
