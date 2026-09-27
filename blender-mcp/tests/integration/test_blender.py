"""Runs the add-on inside a real headless Blender and drives it through the MCP server.

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


@pytest.fixture
async def client(blender_port):
    bridge = BlenderBridge(BridgeConfig(port=blender_port, timeout=120))
    async with Client(create_server(bridge)) as client:
        yield client
    await bridge.close()


async def call_json(client, tool, **args):
    result = await client.call_tool(tool, args)
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def call_image(client, tool, **args):
    result = await client.call_tool(tool, args)
    assert not result.is_error, result.content
    image, meta = result.content
    assert image.type == "image" and image.mime_type == "image/png"
    assert base64.b64decode(image.data).startswith(PNG_MAGIC)
    return json.loads(meta.text)


async def test_ping_and_scene_info(client):
    ping = await call_json(client, "ping")
    assert ping["pong"] is True
    assert ping["blender_version"]

    scene = await call_json(client, "get_scene_info")
    assert scene["object_count"] == 3
    assert scene["objects_by_type"] == {"MESH": 1, "CAMERA": 1, "LIGHT": 1}
    assert scene["camera"] == "Camera"
    assert scene["collections"]["children"][0]["name"] == "Collection"


async def test_list_objects(client):
    everything = await call_json(client, "list_objects")
    assert [o["name"] for o in everything["objects"]] == ["Camera", "Cube", "Light"]
    assert everything["total"] == 3 and "next_offset" not in everything

    meshes = await call_json(client, "list_objects", type="MESH")
    assert [o["name"] for o in meshes["objects"]] == ["Cube"]
    assert meshes["objects"][0]["dimensions"] == [2.0, 2.0, 2.0]

    first = await call_json(client, "list_objects", limit=2)
    assert first["returned"] == 2 and first["next_offset"] == 2


async def test_get_object_info(client):
    cube = await call_json(client, "get_object_info", name="Cube")
    mesh = cube["mesh"]
    assert (mesh["vertices"], mesh["edges"], mesh["faces"]) == (8, 12, 6)
    assert mesh["quads"] == 6 and mesh["is_manifold"] is True
    assert cube["materials"] == [{"slot": 0, "material": "Material", "link": "DATA"}]
    assert cube["world_bounds"] == {"min": [-1.0, -1.0, -1.0], "max": [1.0, 1.0, 1.0]}

    camera = await call_json(client, "get_object_info", name="Camera")
    assert camera["camera"]["is_scene_camera"] is True

    light = await call_json(client, "get_object_info", name="Light")
    assert light["light"]["type"] == "POINT"


async def test_get_object_info_unknown_name_lists_objects(client):
    result = await client.call_tool("get_object_info", {"name": "Nope"})
    assert result.is_error
    assert "No object named 'Nope'" in result.content[0].text
    assert "Cube" in result.content[0].text


async def test_get_mesh_data(client):
    data = await call_json(client, "get_mesh_data", name="Cube", space="world")
    assert data["vertices"]["total"] == 8 and len(data["vertices"]["items"]) == 8
    assert all(abs(c) == 1.0 for v in data["vertices"]["items"] for c in v)
    assert data["faces"]["total"] == 6
    assert all(len(face) == 4 for face in data["faces"]["items"])

    window = await call_json(client, "get_mesh_data", name="Cube", limit=3, offset=3)
    assert len(window["vertices"]["items"]) == 3 and window["vertices"]["next_offset"] == 6


async def test_materials(client):
    listed = await call_json(client, "list_materials")
    material = next(m for m in listed["materials"] if m["name"] == "Material")
    assert material["objects"] == ["Cube"]

    info = await call_json(client, "get_material_info", name="Material")
    assert "Base Color" in info["principled_bsdf"]
    assert any("Principled BSDF" in link for link in info["links"])


async def test_render_preview_restores_scene(client):
    meta = await call_image(client, "render_preview", view="front", size=128)
    assert meta["engine"] == "BLENDER_WORKBENCH"
    assert (meta["width"], meta["height"]) == (128, 72)  # factory scene is 16:9

    scene = await call_json(client, "get_scene_info")
    assert scene["camera"] == "Camera"
    assert scene["object_count"] == 3
    assert scene["render"]["resolution"] == [1920, 1080]
    assert scene["render"]["engine"] == "BLENDER_EEVEE_NEXT"


async def test_render_preview_through_scene_camera(client):
    meta = await call_image(client, "render_preview", size=64)
    assert meta["view"] == "camera"


async def test_viewport_screenshot_falls_back_headless(client):
    meta = await call_image(client, "get_viewport_screenshot", view="iso", size=96)
    assert "headless" in meta["note"]
