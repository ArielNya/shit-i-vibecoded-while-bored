"""M3: materials, world, camera/light helpers, and path-restricted file I/O.

Runs in its own Blender process with a temporary workspace folder. The .blend
save/open test runs last because opening a file replaces the scene.
"""

import struct
import zlib

import pytest

pytestmark = pytest.mark.anyio


def write_png(path, width=4, height=4, rgb=(255, 0, 0)):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def approx(values, expected, tol=1e-3):
    return all(abs(a - b) <= tol for a, b in zip(values, expected, strict=True))


# --- materials -------------------------------------------------------------------------


async def test_create_and_update_material(call, call_error):
    mat = await call(
        "create_material", name="Red", base_color=[0.8, 0, 0], metallic=1, roughness=0.2
    )
    bsdf = mat["principled_bsdf"]
    assert bsdf["Base Color"] == [0.8, 0.0, 0.0, 1.0]
    assert bsdf["Metallic"] == 1.0 and bsdf["Roughness"] == 0.2
    assert mat["diffuse_color"] == [0.8, 0.0, 0.0, 1.0]  # Workbench shows the same color

    assert "exists" in await call_error("create_material", name="Red")

    updated = await call("update_material", name="Red", roughness=0.7)
    assert updated["principled_bsdf"]["Roughness"] == 0.7
    assert updated["principled_bsdf"]["Metallic"] == 1.0  # untouched

    glass = await call("create_material", name="Glass", alpha=0.3, transmission=1)
    assert glass["blend"] == "BLENDED"


async def test_assign_material_whole_and_faces(call, call_error):
    await call("create_primitive", type="cube", name="Painted")
    await call("create_material", name="Blue", base_color=[0, 0, 1])
    await call("create_material", name="Yellow", base_color=[1, 1, 0])
    whole = await call("assign_material", object="Painted", material="Blue")
    assert whole["slots"] == ["Blue"]

    part = await call("assign_material", object="Painted", material="Yellow", faces=[0, 1])
    assert part["slots"] == ["Blue", "Yellow"] and part["faces_assigned"] == 2
    info = await call("get_object_info", name="Painted")
    assert [m["material"] for m in info["materials"]] == ["Blue", "Yellow"]

    assert "out of range" in await call_error(
        "assign_material", object="Painted", material="Blue", faces=[6]
    )
    split = await call("separate_mesh", name="Painted", mode="material")
    assert len(split["parts"]) == 2
    await call("delete_objects", names=split["parts"])


async def test_generated_texture(call):
    mat = await call(
        "create_material", name="Checker", generated_texture="CHECKER", texture_scale=4
    )
    assert mat["principled_bsdf"]["Base Color"] == {"linked_from": "MCP Base Color Texture.Color"}
    assert {"TEX_IMAGE", "MAPPING", "TEX_COORD"} <= {n["type"] for n in mat["nodes"]}


async def test_image_texture_from_workspace(call, workspace):
    write_png(workspace / "red.png")
    mat = await call("create_material", name="Img", base_color_texture="red.png")
    assert "linked_from" in mat["principled_bsdf"]["Base Color"]


# --- path policy -------------------------------------------------------------------------


async def test_paths_outside_workspace_are_refused(call_error, workspace, tmp_path_factory):
    outside = write_png(tmp_path_factory.mktemp("outside") / "secret.png")
    text = await call_error("create_material", name="X", base_color_texture=str(outside))
    assert "outside the folders" in text

    text = await call_error("create_material", name="X", base_color_texture="../secret.png")
    assert "outside the folders" in text

    (workspace / "sneaky.png").symlink_to(outside)
    text = await call_error("create_material", name="X", base_color_texture="sneaky.png")
    assert "outside the folders" in text

    text = await call_error("set_world", hdri_path=str(outside))
    assert "outside the folders" in text


async def test_suffix_and_overwrite_rules(call, call_error, workspace):
    await call("create_primitive", type="cube", name="Exp")
    assert "not allowed" in await call_error("export_file", path="evil.sh", objects=["Exp"])
    assert "not allowed" in await call_error("export_file", path="noext", objects=["Exp"])
    await call("export_file", path="once.stl", objects=["Exp"])
    assert "already exists" in await call_error("export_file", path="once.stl", objects=["Exp"])
    await call("export_file", path="once.stl", objects=["Exp"], overwrite=True)
    await call("delete_objects", names=["Exp"])


async def test_list_files(call, workspace):
    (workspace / "models").mkdir()
    write_png(workspace / "tex.png")
    (workspace / "notes.txt").write_text("not listed")
    listing = await call("list_files")
    assert listing["allowed_roots"] == [str(workspace.resolve())]
    assert "models" in listing["folders"]
    names = [f["name"] for f in listing["files"]]
    assert "tex.png" in names and "notes.txt" not in names


async def test_import_refuses_references_outside_the_workspace(
    call, call_error, workspace, tmp_path_factory
):
    import json

    outside = write_png(tmp_path_factory.mktemp("elsewhere") / "private.png")
    (workspace / "refs").mkdir(exist_ok=True)

    gltf = {
        "asset": {"version": "2.0"},
        "images": [{"uri": str(outside)}],
        "buffers": [{"uri": "data:application/octet-stream;base64,", "byteLength": 0}],
    }
    (workspace / "refs" / "evil.gltf").write_text(json.dumps(gltf))
    text = await call_error("import_file", path="refs/evil.gltf")
    assert "references files outside" in text and "private.png" in text

    # The same inside a binary .glb (JSON chunk first).
    body = json.dumps(gltf).encode()
    body += b" " * (-len(body) % 4)
    glb = b"glTF" + struct.pack("<II", 2, 20 + len(body)) + struct.pack("<I4s", len(body), b"JSON")
    (workspace / "refs" / "evil.glb").write_bytes(glb + body)
    assert "references files outside" in await call_error("import_file", path="refs/evil.glb")

    (workspace / "refs" / "evil.obj").write_text(f"mtllib {outside.parent / 'x.mtl'}\nv 0 0 0\n")
    assert "references files outside" in await call_error("import_file", path="refs/evil.obj")

    (workspace / "refs" / "local.mtl").write_text(f"newmtl m\nmap_Kd -s 1 1 1 {outside}\n")
    (workspace / "refs" / "sneaky.obj").write_text(
        "mtllib local.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nusemtl m\nf 1 2 3\n"
    )
    text = await call_error("import_file", path="refs/sneaky.obj")
    assert "private.png" in text


async def test_gltf_with_local_texture_still_imports(call, workspace):
    await call("create_primitive", type="cube", name="LocalTex")
    await call("create_material", name="LocalTexMat", base_color_texture="red.png")
    await call("assign_material", object="LocalTex", material="LocalTexMat")
    await call("export_file", path="sep/local.gltf", objects=["LocalTex"])
    await call("delete_objects", names=["LocalTex"])
    imported = await call("import_file", path="sep/local.gltf")
    assert imported["count"] == 1 and "removed_external_files" not in imported
    await call("delete_objects", names=imported["objects"])


# --- world, camera, lights ----------------------------------------------------------------


async def test_world(call):
    world = await call("set_world", color=[0.1, 0.2, 0.3], strength=0.5)
    assert world["color"] == [0.1, 0.2, 0.3, 1.0] and world["strength"] == 0.5


async def test_camera_and_light_helpers(call, call_error):
    await call("create_primitive", type="camera", name="Cam", location=[0, -5, 0])
    aimed = await call("look_at", name="Cam", target=[0, 0, 0])
    assert approx(aimed["rotation_deg"], [90, 0, 0])
    await call("set_active_camera", name="Cam")
    assert (await call("get_scene_info"))["camera"] == "Cam"

    lens = await call("set_data_params", name="Cam", params={"lens": 35})
    assert lens["data"]["lens"] == 35.0

    await call("create_primitive", type="light", light_type="SPOT", name="Spot", location=[3, 3, 3])
    spot = await call("set_data_params", name="Spot", params={"spot_size": 30, "energy": 250})
    assert spot["data"]["spot_size"] == 30.0 and spot["data"]["energy"] == 250.0
    assert "no settable property" in await call_error(
        "set_data_params", name="Spot", params={"power": 1}
    )
    assert "not a CAMERA" in await call_error("set_active_camera", name="Spot")
    await call("look_at", name="Spot", target="Cube")
    await call("delete_objects", names=["Spot"])


# --- the M3 goal: a textured model exported as glTF ---------------------------------------


async def test_textured_gltf_roundtrip(call, workspace):
    await call("create_primitive", type="uv_sphere", name="Planet", shade_smooth=True)
    await call("create_material", name="PlanetSkin", generated_texture="COLOR_GRID", roughness=0.6)
    await call("assign_material", object="Planet", material="PlanetSkin")
    await call("add_modifier", object="Planet", type="SUBSURF", params={"levels": 1})

    exported = await call("export_file", path="out/planet.glb", objects=["Planet"])
    assert exported["objects"] == ["Planet"]
    assert exported["bytes"] > 10_000  # mesh + embedded texture
    assert (workspace / "out" / "planet.glb").is_file()

    await call("delete_objects", names=["Planet"])
    imported = await call("import_file", path="out/planet.glb")
    assert imported["count"] == 1
    info = await call("get_object_info", name=imported["objects"][0])
    assert info["mesh"]["faces"] > 512 * 2  # subdivided on export
    material = await call("get_material_info", name=info["materials"][0]["material"])
    assert "TEX_IMAGE" in {n["type"] for n in material["nodes"]}
    await call("delete_objects", names=imported["objects"])


async def test_export_formats(call, workspace):
    await call("create_primitive", type="torus", name="Donut")
    for suffix in ("obj", "fbx", "stl", "ply", "gltf", "usdc"):
        result = await call("export_file", path=f"fmt/donut.{suffix}", objects=["Donut"])
        assert result["bytes"] > 0, suffix
    imported = await call("import_file", path="fmt/donut.obj")
    assert imported["count"] == 1
    await call("delete_objects", names=["Donut", *imported["objects"]])


# --- .blend files (last: open replaces the scene) ----------------------------------------


async def test_save_and_open_blend(call, call_error, workspace):
    await call("create_primitive", type="cube", name="Saved")
    saved = await call("save_blend", path="scene.blend")
    assert saved["saved"] == str((workspace / "scene.blend").resolve())
    assert "already exists" in await call_error("save_blend", path="scene.blend")

    await call("create_primitive", type="cube", name="Unsaved")
    assert "unsaved changes" in await call_error("open_blend", path="scene.blend")
    opened = await call("open_blend", path="scene.blend", discard_unsaved=True)
    assert opened["objects"] >= 1
    names = [o["name"] for o in (await call("list_objects"))["objects"]]
    assert "Saved" in names and "Unsaved" not in names

    again = await call("save_blend")  # in place, no path needed now
    assert again["saved"].endswith("scene.blend")
