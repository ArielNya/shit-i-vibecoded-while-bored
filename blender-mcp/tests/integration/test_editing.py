"""M2 editing tools against real Blender. Runs in its own Blender process (module-scoped
fixture), separate from the read-only tests. Tests use their own object names so they
don't depend on each other."""

import pytest

pytestmark = pytest.mark.anyio


def approx(values, expected, tol=1e-3):
    return all(abs(a - b) <= tol for a, b in zip(values, expected, strict=True))


@pytest.mark.parametrize(
    ("args", "name", "dimensions"),
    [
        ({"type": "cube", "size": 1}, "Cube", [1, 1, 1]),
        ({"type": "plane"}, "Plane", [2, 2, 0]),
        ({"type": "grid", "size": 4, "x_segments": 3, "y_segments": 3}, "Grid", [4, 4, 0]),
        ({"type": "circle", "radius": 0.5, "fill": True}, "Circle", [1, 1, 0]),
        ({"type": "uv_sphere", "radius": 0.5}, "Sphere", [1, 1, 1]),
        ({"type": "ico_sphere", "subdivisions": 3}, "Icosphere", None),
        ({"type": "cylinder", "radius": 0.5, "depth": 3}, "Cylinder", [1, 1, 3]),
        ({"type": "cone", "radius": 1, "depth": 2}, "Cone", [2, 2, 2]),
        ({"type": "torus", "major_radius": 1, "minor_radius": 0.25}, "Torus", [2.5, 2.5, 0.5]),
        ({"type": "monkey"}, "Suzanne", None),
    ],
)
async def test_create_mesh_primitives(call, args, name, dimensions):
    obj = await call("create_primitive", **args, location=[0, 0, 10])
    assert obj["name"].startswith(name)
    assert obj["type"] == "MESH"
    assert obj["location"] == [0.0, 0.0, 10.0]
    if dimensions:
        assert approx(obj["dimensions"], dimensions), obj["dimensions"]
    info = await call("get_object_info", name=obj["name"])
    assert info["mesh"]["faces"] > 0
    await call("delete_objects", names=[obj["name"]])


async def test_create_other_primitives(call):
    empty = await call("create_primitive", type="empty", name="Anchor")
    assert empty["type"] == "EMPTY"
    sun = await call("create_primitive", type="light", light_type="SUN", energy=2, name="Sun")
    assert (await call("get_object_info", name=sun["name"]))["light"]["type"] == "SUN"
    cam = await call("create_primitive", type="camera", name="Cam2", lens=35, rotation=[90, 0, 0])
    assert cam["rotation_deg"] == [90.0, 0.0, 0.0]
    info = await call("get_object_info", name="Cam2")
    assert info["camera"]["lens_mm"] == 35.0
    assert info["camera"]["is_scene_camera"] is False  # scene already had a camera
    await call("delete_objects", names=["Anchor", "Sun", "Cam2"])


async def test_name_clash_returns_actual_name(call):
    first = await call("create_primitive", type="cube", name="Box")
    second = await call("create_primitive", type="cube", name="Box")
    assert first["name"] == "Box" and second["name"] == "Box.001"
    await call("delete_objects", names=["Box", "Box.001"])


async def test_transform_set_delta_dimensions(call):
    await call("create_primitive", type="cube", name="T")
    obj = await call("transform_object", name="T", location=[1, 2, 3], rotation=[0, 0, 45])
    assert obj["location"] == [1.0, 2.0, 3.0] and obj["rotation_deg"] == [0.0, 0.0, 45.0]
    obj = await call(
        "transform_object", name="T", location=[1, 0, 0], rotation=[0, 0, 45], scale=2,
        mode="delta",
    )  # fmt: skip
    assert obj["location"] == [2.0, 2.0, 3.0]
    assert obj["rotation_deg"] == [0.0, 0.0, 90.0]
    assert obj["scale"] == [2.0, 2.0, 2.0]
    obj = await call("transform_object", name="T", dimensions=[1, 2, 3])
    assert approx(obj["dimensions"], [1, 2, 3])
    await call("delete_objects", names=["T"])


async def test_apply_transform(call):
    await call("create_primitive", type="cube", name="Scaled", scale=[2, 1, 1])
    obj = await call("apply_transform", name="Scaled")
    assert obj["scale"] == [1.0, 1.0, 1.0]
    assert approx(obj["dimensions"], [4, 2, 2])
    await call("delete_objects", names=["Scaled"])


async def test_duplicate_rename_delete(call):
    await call("create_primitive", type="cube", name="Orig", location=[0, 0, 0])
    dup = await call("duplicate_object", name="Orig", new_name="Copy", offset=[3, 0, 0])
    assert dup["name"] == "Copy" and dup["location"] == [3.0, 0.0, 0.0]
    inst = await call("duplicate_object", name="Orig", linked=True)
    orig_info = await call("get_object_info", name="Orig")
    inst_info = await call("get_object_info", name=inst["name"])
    assert inst_info["data"] == orig_info["data"]
    assert (await call("get_object_info", name="Copy"))["data"] != orig_info["data"]

    renamed = await call("rename_object", name="Copy", new_name="Renamed", rename_data=True)
    assert renamed["name"] == "Renamed"
    assert (await call("get_object_info", name="Renamed"))["data"] == "Renamed"

    deleted = await call("delete_objects", names=["Orig", "Renamed", inst["name"]])
    assert sorted(deleted["deleted"]) == sorted(["Orig", "Renamed", inst["name"]])
    listed = await call("list_objects", name_contains="Orig")
    assert listed["total"] == 0


async def test_delete_validates_all_names_first(call, call_error):
    await call("create_primitive", type="cube", name="Keep")
    text = await call_error("delete_objects", names=["Keep", "Missing"])
    assert "Missing" in text
    assert (await call("list_objects", name_contains="Keep"))["total"] == 1
    await call("delete_objects", names=["Keep"])


async def test_parenting_keeps_world_transform(call, call_error):
    await call("create_primitive", type="empty", name="Parent", location=[5, 0, 0])
    await call("create_primitive", type="cube", name="Child", location=[1, 1, 1])
    await call("transform_object", name="Parent", rotation=[0, 0, 90])
    child = await call("set_parent", name="Child", parent="Parent")
    assert child["parent"] == "Parent"
    info = await call("get_object_info", name="Child")
    assert approx(info["world_location"], [1, 1, 1])

    await call("transform_object", name="Parent", location=[6, 0, 0])  # child follows
    assert approx((await call("get_object_info", name="Child"))["world_location"], [2, 1, 1])

    assert "cycle" in await call_error("set_parent", name="Parent", parent="Child")

    child = await call("set_parent", name="Child")  # unparent
    assert child["parent"] is None
    assert approx((await call("get_object_info", name="Child"))["world_location"], [2, 1, 1])
    await call("delete_objects", names=["Parent", "Child"])


async def test_collections(call, call_error):
    coll = await call("create_collection", name="Props")
    assert coll == {"name": "Props", "parent": "Scene Collection"}
    await call("create_primitive", type="cube", name="Crate", collection="Props")
    assert (await call("list_objects", collection="Props"))["total"] == 1
    await call("create_primitive", type="cube", name="Barrel")
    moved = await call("move_to_collection", names=["Barrel"], collection="Props")
    assert moved["collection"] == "Props"
    barrel = await call("get_object_info", name="Barrel")
    assert barrel["collections"] == ["Props"]
    assert "No collection" in await call_error("create_primitive", type="cube", collection="Nope")
    await call("delete_objects", names=["Crate", "Barrel"])


async def test_join_and_separate(call):
    await call("create_primitive", type="cube", name="J1")
    await call("create_primitive", type="cube", name="J2", location=[4, 0, 0])
    joined = await call("join_objects", names=["J1", "J2"])
    assert joined["name"] == "J1"
    assert (await call("get_object_info", name="J1"))["mesh"]["vertices"] == 16
    assert (await call("list_objects", name_contains="J2"))["total"] == 0

    parts = await call("separate_mesh", name="J1")
    assert len(parts["parts"]) == 2
    for name in parts["parts"]:
        assert (await call("get_object_info", name=name))["mesh"]["vertices"] == 8
    await call("delete_objects", names=parts["parts"])


async def test_boolean_difference(call):
    await call("create_primitive", type="cube", name="Block")
    await call("create_primitive", type="cylinder", name="Drill", radius=0.4, depth=4)
    result = await call("boolean", target="Block", cutter="Drill")
    assert result["applied"] is True and result["cutter"] == "hide"
    block = await call("get_object_info", name="Block")
    assert block["modifiers"] == []
    assert block["mesh"]["vertices"] > 8
    assert block["mesh"]["is_manifold"] is True
    drill = await call("get_object_info", name="Drill")
    assert drill["visible"] is False and drill["hide_render"] is True
    await call("delete_objects", names=["Block", "Drill"])


async def test_modifier_lifecycle(call, call_error):
    await call("create_primitive", type="cube", name="M")
    added = await call(
        "add_modifier", object="M", type="BEVEL",
        params={"width": 0.1, "segments": 3, "limit_method": "ANGLE", "angle_limit": 45},
    )  # fmt: skip
    bevel = added["modifier"]
    assert bevel["width"] == 0.1 and bevel["segments"] == 3
    assert bevel["angle_limit"] == 45.0  # degrees in, degrees out

    await call("add_modifier", object="M", type="SUBSURF", params={"levels": 1})
    moved = await call("move_modifier", object="M", modifier="Subsurf", index=0)
    assert moved["stack"] == ["Subsurf (SUBSURF)", "Bevel (BEVEL)"]

    changed = await call(
        "set_modifier_params", object="M", modifier="Bevel", params={"segments": 1}
    )
    assert changed["modifier"]["segments"] == 1

    info = await call("get_object_info", name="M")
    assert info["mesh"]["with_modifiers"]["vertices"] > 8

    applied = await call("apply_modifier", object="M", modifier="Subsurf")
    assert applied["stack"] == ["Bevel (BEVEL)"] and applied["vertices"] == 26
    assert "note" not in applied

    removed = await call("remove_modifier", object="M", modifier="Bevel")
    assert removed["stack"] == []
    await call("delete_objects", names=["M"])


async def test_modifier_errors_leave_nothing_behind(call, call_error):
    await call("create_primitive", type="cube", name="E")
    text = await call_error("add_modifier", object="E", type="BEVEL", params={"widht": 1})
    assert "no settable property 'widht'" in text and "width" in text
    text = await call_error("add_modifier", object="E", type="BEVEL", params={"limit_method": "X"})
    assert "limit_method" in text
    assert "unknown modifier type" in await call_error("add_modifier", object="E", type="NOPE")
    assert (await call("get_object_info", name="E"))["modifiers"] == []
    await call("delete_objects", names=["E"])


async def test_modifier_object_pointer_by_name(call, call_error):
    await call("create_primitive", type="cube", name="Half", location=[1, 0, 0])
    await call("create_primitive", type="empty", name="MirrorCenter")
    added = await call(
        "add_modifier", object="Half", type="MIRROR", params={"mirror_object": "MirrorCenter"}
    )
    assert added["modifier"]["mirror_object"] == "MirrorCenter"
    text = await call_error(
        "set_modifier_params", object="Half", modifier="Mirror", params={"mirror_object": "Nope"}
    )
    assert "no Object named 'Nope'" in text
    await call("delete_objects", names=["Half", "MirrorCenter"])


async def test_undo_redo(call):
    await call("create_primitive", type="cube", name="Undoable")
    undone = await call("undo")
    assert undone["steps_done"] == 1
    assert "Undoable" not in undone["objects"]
    redone = await call("redo")
    assert "Undoable" in redone["objects"]
    await call("delete_objects", names=["Undoable"])


async def test_build_and_look(call, call_image):
    """A tiny end-to-end modelling session: table with four legs, then render it."""
    top = await call(
        "create_primitive", type="cube", name="TableTop", location=[0, 0, 1], scale=[1.5, 1, 0.05]
    )
    await call("apply_transform", name=top["name"])
    await call("add_modifier", object="TableTop", type="BEVEL", params={"width": 0.02})
    for i, (x, y) in enumerate([(1.3, 0.8), (-1.3, 0.8), (1.3, -0.8), (-1.3, -0.8)]):
        await call(
            "create_primitive", type="cylinder", name=f"Leg{i}", radius=0.05, depth=0.95,
            location=[x, y, 0.475],
        )  # fmt: skip
        await call("set_parent", name=f"Leg{i}", parent="TableTop")
    table = await call("get_object_info", name="TableTop")
    assert len(table["children"]) == 4
    meta = await call_image("render_preview", view="iso", size=256, object="TableTop")
    assert meta["width"] == 256
    await call("delete_objects", names=["TableTop"], delete_children=True)
    assert (await call("list_objects", name_contains="Leg"))["total"] == 0


async def test_file_path_properties_are_refused(call, call_error):
    await call("create_primitive", type="cube", name="P")
    text = await call_error(
        "add_modifier", object="P", type="MESH_CACHE", params={"filepath": "/etc/passwd"}
    )
    assert "file path" in text
    assert (await call("get_object_info", name="P"))["modifiers"] == []
    await call("delete_objects", names=["P"])
