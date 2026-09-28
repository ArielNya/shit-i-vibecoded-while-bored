"""M0/M1 tools against Blender's untouched factory scene (read-only tests)."""

import pytest

pytestmark = pytest.mark.anyio


async def test_ping_and_scene_info(call):
    ping = await call("ping")
    assert ping["pong"] is True
    assert ping["blender_version"]

    scene = await call("get_scene_info")
    assert scene["object_count"] == 3
    assert scene["objects_by_type"] == {"MESH": 1, "CAMERA": 1, "LIGHT": 1}
    assert scene["camera"] == "Camera"
    assert scene["collections"]["children"][0]["name"] == "Collection"


async def test_list_objects(call, call_image, call_error):
    everything = await call("list_objects")
    assert [o["name"] for o in everything["objects"]] == ["Camera", "Cube", "Light"]
    assert everything["total"] == 3 and "next_offset" not in everything

    meshes = await call("list_objects", type="MESH")
    assert [o["name"] for o in meshes["objects"]] == ["Cube"]
    assert meshes["objects"][0]["dimensions"] == [2.0, 2.0, 2.0]

    first = await call("list_objects", limit=2)
    assert first["returned"] == 2 and first["next_offset"] == 2


async def test_get_object_info(call, call_image, call_error):
    cube = await call("get_object_info", name="Cube")
    mesh = cube["mesh"]
    assert (mesh["vertices"], mesh["edges"], mesh["faces"]) == (8, 12, 6)
    assert mesh["quads"] == 6 and mesh["is_manifold"] is True
    assert cube["materials"] == [{"slot": 0, "material": "Material", "link": "DATA"}]
    assert cube["world_bounds"] == {"min": [-1.0, -1.0, -1.0], "max": [1.0, 1.0, 1.0]}

    camera = await call("get_object_info", name="Camera")
    assert camera["camera"]["is_scene_camera"] is True

    light = await call("get_object_info", name="Light")
    assert light["light"]["type"] == "POINT"


async def test_get_object_info_unknown_name_lists_objects(call, call_image, call_error):
    text = await call_error("get_object_info", name="Nope")
    assert "No object named 'Nope'" in text
    assert "Cube" in text


async def test_get_mesh_data(call, call_image, call_error):
    data = await call("get_mesh_data", name="Cube", space="world")
    assert data["vertices"]["total"] == 8 and len(data["vertices"]["items"]) == 8
    assert all(abs(c) == 1.0 for v in data["vertices"]["items"] for c in v)
    assert data["faces"]["total"] == 6
    assert all(len(face) == 4 for face in data["faces"]["items"])

    window = await call("get_mesh_data", name="Cube", limit=3, offset=3)
    assert len(window["vertices"]["items"]) == 3 and window["vertices"]["next_offset"] == 6


async def test_materials(call, call_image, call_error):
    listed = await call("list_materials")
    material = next(m for m in listed["materials"] if m["name"] == "Material")
    assert material["objects"] == ["Cube"]

    info = await call("get_material_info", name="Material")
    assert "Base Color" in info["principled_bsdf"]
    assert any("Principled BSDF" in link for link in info["links"])


async def test_render_preview_restores_scene(call, call_image, call_error):
    meta = await call_image("render_preview", view="front", size=128)
    assert meta["engine"] == "BLENDER_WORKBENCH"
    assert (meta["width"], meta["height"]) == (128, 72)  # factory scene is 16:9

    scene = await call("get_scene_info")
    assert scene["camera"] == "Camera"
    assert scene["object_count"] == 3
    assert scene["render"]["resolution"] == [1920, 1080]
    assert scene["render"]["engine"] == "BLENDER_EEVEE_NEXT"


async def test_render_preview_through_scene_camera(call, call_image, call_error):
    meta = await call_image("render_preview", size=64)
    assert meta["view"] == "camera"


async def test_viewport_screenshot_falls_back_headless(call, call_image, call_error):
    meta = await call_image("get_viewport_screenshot", view="iso", size=96)
    assert "headless" in meta["note"]


async def test_execute_python_disabled_by_default(call, call_image, call_error):
    text = await call_error("execute_python", code="result = 1")
    assert "disabled" in text and "Allow arbitrary Python" in text
    assert (await call("ping"))["python_enabled"] is False


async def test_connection_needs_the_token(blender_port):
    """This module's Blender uses the token file; a client without it is refused."""
    from blender_mcp.bridge import BlenderBridge, BlenderCommandError, BridgeConfig

    bridge = BlenderBridge(BridgeConfig(port=blender_port, token="not-the-token"))
    with pytest.raises(BlenderCommandError, match="invalid token"):
        await bridge.call("ping")
