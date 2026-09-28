"""M8: reference sheets, rigging, and the low-poly character skill end to end."""

import struct
import zlib

import pytest

pytestmark = pytest.mark.anyio

H = 1.6
LANDMARKS = {
    "hips": [0, 0, 0.74], "chest": [0, 0, 1.0], "neck": [0, 0, 1.2], "head": [0, 0, 1.26],
    "head_top": [0, 0, H], "shoulder": [0.19, 0, 1.08], "elbow": [0.41, 0, 1.08],
    "wrist": [0.63, 0, 1.08], "hand_tip": [0.75, 0, 1.08], "hip_joint": [0.09, 0, 0.70],
    "knee": [0.09, 0, 0.39], "ankle": [0.09, 0, 0.10], "ball": [0.09, -0.08, 0.03],
    "toe": [0.09, -0.17, 0.03],
}  # fmt: skip


def write_png(path, width, height, figure):
    """A grey sheet with a dark figure box: rows figure[0]..figure[1], cols [2]..[3]."""
    top, bottom, left, right = figure
    rows = b"".join(
        b"\x00"
        + bytes(
            60 if top <= y < bottom and left <= x < right else 200
            for x in range(width)
            for _ in range(3)
        )
        for y in range(height)
    )

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )  # fmt: skip


def approx(values, expected, tol=1e-3):
    return all(abs(a - b) <= tol for a, b in zip(values, expected, strict=True))


# --- reference images ------------------------------------------------------------------------


async def test_reference_images_sit_at_true_scale(call, call_image, call_error, workspace):
    write_png(workspace / "front.png", 100, 200, (20, 180, 30, 70))
    write_png(workspace / "side.png", 100, 200, (20, 180, 40, 60))
    front = await call(
        "add_reference_image", path="front.png", view="front", character_height=H,
        pixel_top=20, pixel_bottom=180, pixel_center=50,
    )  # fmt: skip
    assert front["image"] == {"file": "front.png", "width": 100, "height": 200}
    assert front["world_per_pixel"] == pytest.approx(H / 160)
    assert front["covers"]["height"] == pytest.approx(200 * H / 160)

    verts = (await call("get_mesh_data", name=front["name"]))["vertices"]["items"]
    # Feet row (180) on z=0: the plane spans 20 px below the ground to 20 px above the head.
    assert min(v[2] for v in verts) == pytest.approx(-20 * H / 160, abs=1e-3)
    assert max(v[2] for v in verts) == pytest.approx(H + 20 * H / 160, abs=1e-3)
    assert min(v[0] for v in verts) == pytest.approx(-50 * H / 160, abs=1e-3)
    assert all(v[1] > 0 for v in verts)  # behind a character facing -Y

    side = await call(
        "add_reference_image", path="side.png", view="side", character_height=H,
        pixel_top=20, pixel_bottom=180, pixel_center=50,
    )  # fmt: skip
    side_verts = (await call("get_mesh_data", name=side["name"]))["vertices"]["items"]
    assert all(v[0] < 0 for v in side_verts)  # seen from the right view, behind is -X

    # Re-adding by name replaces instead of stacking.
    await call("add_reference_image", path="front.png", view="front", character_height=H)
    names = [o["name"] for o in (await call("list_objects"))["objects"]]
    assert names.count("Ref front") == 1

    await call_image("render_preview", view="front", ortho=True, textures=True, xray=True, size=128)

    hidden = await call("set_visibility", names=["Ref front", "Ref side"], viewport=False)
    assert len(hidden["objects"]) == 2
    await call_error("add_reference_image", path="../outside.png", match="workspace")


# --- armatures -------------------------------------------------------------------------------


async def test_custom_armature_and_errors(call, call_error):
    result = await call(
        "create_armature", name="Tail",
        bones=[
            {"name": "base", "head": [0, 0, 0], "tail": [0, 0.3, 0]},
            {"name": "tip", "head": [0, 0.3, 0], "tail": [0, 0.6, 0], "parent": "base",
             "connected": True},
        ],
    )  # fmt: skip
    assert [b["name"] for b in result["bones"]] == ["base", "tip"]
    assert result["bones"][1]["parent"] == "base"
    await call_error(
        "create_armature", bones=[{"name": "a", "head": [0, 0, 0], "tail": [0, 0, 1],
                                   "parent": "missing"}], match="missing",
    )  # fmt: skip
    await call_error("pose_bone", armature="Tail", bone="nope", rotation=[1, 0, 0], match="nope")


async def test_humanoid_rig_bends_naturally(call):
    rig = await call("create_humanoid_rig", height=H, landmarks=LANDMARKS, name="Rig")
    assert rig["bone_count"] == 22
    bones = {b["name"]: b for b in rig["bones"]}
    assert approx(bones["forearm.L"]["head"], LANDMARKS["elbow"])
    assert approx(bones["forearm.R"]["head"], [-0.41, 0, 1.08])

    # Knee: +X bends it backward, so the ankle moves to +Y.
    shin = await call("pose_bone", armature="Rig", bone="shin.L", rotation=[60, 0, 0])
    assert shin["tail_world"][1] > 0.1
    # Arms down on both sides with one call, symmetrically.
    await call("pose_bone", armature="Rig", bone="upper_arm.L", rotation=[0, 0, -60], mirror=True)
    arms = {b["name"]: b for b in (await call("get_armature_info", armature="Rig"))["bones"]}
    assert "upper_arm.R" in (await call("get_armature_info", armature="Rig"))["posed_bones"]
    left = (await call("pose_bone", armature="Rig", bone="upper_arm.L"))["tail_world"]
    right = (await call("pose_bone", armature="Rig", bone="upper_arm.R"))["tail_world"]
    assert left[2] < 1.0 and right[2] < 1.0
    assert approx([left[0], left[2]], [-right[0], right[2]])
    assert arms

    reset = await call("reset_pose", armature="Rig")
    assert reset["bones_reset"] == 22
    assert (await call("get_armature_info", armature="Rig"))["posed_bones"] == []


# --- the skill, end to end -------------------------------------------------------------------


async def test_lowpoly_character_workflow(call, workspace):
    """The steps from docs/character.md on a simple blocky character."""
    await call("create_primitive", type="cube", name="Body", location=[0, 0, 1.0])
    await call("transform_object", name="Body", dimensions=[0.38, 0.22, 0.40])
    await call("apply_transform", name="Body", location=True)

    async def select(spec, expect):
        found = await call("select_elements", name="Body", select=spec)
        assert found["count"] == expect, spec
        return found["indices"]

    # Two columns cuts so the bottom has three faces: leg, crotch, leg.
    edge = await call(
        "select_elements", name="Body", type="edges",
        select={"position": [{"axis": "y", "max": -0.1}, {"axis": "z", "min": 1.19}]},
    )  # fmt: skip
    await call("loop_cut", name="Body", select={"indices": edge["indices"][:1]}, cuts=2)
    bottom = await select({"normal": [0, 0, -1], "max_angle": 5}, 3)
    centres = (await call("select_elements", name="Body", select={"indices": bottom}))["centers"]
    cap = [i for i, c in zip(bottom, centres, strict=True) if abs(c[0]) > 0.05]
    for d in (0.12, 0.29, 0.27, 0.12):
        cap = (await call("extrude", name="Body", select={"indices": cap}, distance=d))["new_faces"]
    fitted = await call(
        "transform_elements", name="Body", type="verts",
        select={"position": [{"axis": "z", "max": 0.69}, {"axis": "x", "min": 0.001}]},
        size=[0.13, 0.14, None], center=[0.09, 0, None],
    )  # fmt: skip
    assert approx(fitted["bounds"]["size"][:2], [0.13, 0.14])

    chest = {"axis": "z", "min": 0.9, "max": 1.1}  # unbounded, the leg sides match too
    arms = await select({"normal": [1, 0, 0], "max_angle": 5, "position": chest}, 1)
    arms += await select({"normal": [-1, 0, 0], "max_angle": 5, "position": chest}, 1)
    cap = arms
    for d in (0.22, 0.22, 0.12):
        cap = (
            await call(
                "extrude", name="Body", select={"indices": cap}, distance=d, mode="individual"
            )
        )["new_faces"]
    top = await select(
        {
            "normal": [0, 0, 1],
            "max_angle": 5,
            "position": [{"axis": "z", "min": 1.19}, {"axis": "x", "min": -0.05, "max": 0.05}],
        },
        1,
    )
    cap = (await call("extrude", name="Body", select={"indices": top}, distance=0.06))["new_faces"]
    cap = (await call("extrude", name="Body", select={"indices": cap}, distance=0.34))["new_faces"]
    await call("transform_elements", name="Body", select={"indices": cap}, size=[0.3, 0.28, None])

    info = await call("get_object_info", name="Body")
    assert info["mesh"]["is_manifold"] and info["mesh"]["ngons"] == 0
    assert info["dimensions"][2] == pytest.approx(H, abs=0.01)

    await call("create_material", name="Skin", base_color=[0.95, 0.75, 0.6])
    await call("assign_material", object="Body", material="Skin")

    await call("create_humanoid_rig", height=H, landmarks=LANDMARKS, name="Rig")
    bound = await call("bind_to_armature", armature="Rig", meshes=["Body"])
    summary = bound["meshes"][0]
    assert summary["unweighted_vertices"] == 0
    assert summary["vertices_per_bone"]["head"] > 0
    assert summary["vertices_per_bone"]["shin.L"] > 0

    fixed = await call(
        "set_vertex_weights", mesh="Body", group="head", weight=1.0,
        select={"position": {"axis": "z", "min": 1.3}},
    )  # fmt: skip
    assert fixed["vertices"] > 0

    # The skinned mesh follows the bones: bending the left knee moves only the left foot back.
    async def world_verts():
        data = await call("get_mesh_data", name="Body", space="world", evaluated=True)
        return data["vertices"]["items"]

    rest = await world_verts()
    soles = [i for i, v in enumerate(rest) if v[2] < 0.05]
    left = [i for i in soles if rest[i][0] > 0]
    right = [i for i in soles if rest[i][0] < 0]
    await call("pose_bone", armature="Rig", bone="shin.L", rotation=[70, 0, 0])
    bent = await world_verts()
    assert min(bent[i][1] - rest[i][1] for i in left) > 0.15  # foot swung back
    assert all(approx(bent[i], rest[i]) for i in right)  # other leg untouched
    await call("reset_pose", armature="Rig")

    # Pose and keyframe: a leg swing that the exported file carries.
    for frame, swing in ((1, 30), (13, -30)):
        await call(
            "pose_bone", armature="Rig", bone="thigh.L", rotation=[-swing, 0, 0], frame=frame
        )
    keys = await call("list_keyframes", object="Rig")
    assert any("thigh.L" in c["property"] for c in keys["channels"])
    await call("reset_pose", armature="Rig")

    exported = await call("export_file", path="character.glb", objects=["Rig"])
    assert set(exported["objects"]) == {"Body", "Rig"}
    await call("delete_objects", names=["Body", "Rig"])
    imported = await call("import_file", path="character.glb")
    by_name = {o: await call("get_object_info", name=o) for o in imported["objects"]}
    assert any(i["type"] == "ARMATURE" for i in by_name.values())
    skinned = [i for i in by_name.values() if i["type"] == "MESH" and i.get("modifiers")]
    assert any(m["type"] == "ARMATURE" for i in skinned for m in i["modifiers"])
