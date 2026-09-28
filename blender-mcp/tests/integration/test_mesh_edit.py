"""M4: mesh-level editing with selection specs. Own Blender process."""

import pytest

pytestmark = pytest.mark.anyio

UP = {"normal": [0, 0, 1], "max_angle": 5}


def approx(values, expected, tol=1e-3):
    return all(abs(a - b) <= tol for a, b in zip(values, expected, strict=True))


async def mesh(call, name):
    return (await call("get_object_info", name=name))["mesh"]


@pytest.fixture
async def cube(call):
    """A fresh 2x2x2 cube named after the test, deleted afterwards."""
    created = []

    async def make(name, **kwargs):
        obj = await call("create_primitive", type=kwargs.pop("type", "cube"), name=name, **kwargs)
        created.append(obj["name"])
        return obj["name"]

    yield make
    existing = {o["name"] for o in (await call("list_objects"))["objects"]}
    leftovers = [n for n in created if n in existing]
    if leftovers:
        await call("delete_objects", names=leftovers)


async def test_select_elements(call, call_error, cube):
    name = await cube("Sel")
    top = await call("select_elements", name=name, select=UP)
    assert top["count"] == 1 and top["centers"] == [[0.0, 0.0, 1.0]]
    upper = await call(
        "select_elements", name=name, type="verts", select={"position": {"axis": "z", "min": 0.5}}
    )
    assert upper["count"] == 4
    both = await call(
        "select_elements",
        name=name,
        type="edges",
        select={"position": [{"axis": "z", "min": 0.5}, {"axis": "x", "min": 0.5}]},
    )
    assert both["count"] == 1
    assert (await call("select_elements", name=name, type="edges", select={"sharp_angle": 80}))[
        "count"
    ] == 12

    assert "matched no faces" in await call_error(
        "select_elements",
        name=name,
        select={"normal": [0, 0, 1], "position": {"axis": "z", "max": -2}},
    )
    assert "out of range" in await call_error(
        "select_elements", name=name, select={"indices": [99]}
    )
    # Unknown keys are rejected by the schema before reaching Blender.
    assert "extra" in (await call_error("select_elements", name=name, select={"nope": 1})).lower()


async def test_extrude_region_and_chain(call, cube):
    name = await cube("Ext")
    first = await call("extrude", name=name, select=UP, distance=1)
    assert first["count"] == 1 and first["faces"] == 10
    second = await call("extrude", name=name, select={"indices": first["new_faces"]}, distance=0.5)
    info = await mesh(call, name)
    assert (info["vertices"], info["faces"], info["is_manifold"]) == (16, 14, True)
    cap = await call("select_elements", name=name, select={"indices": second["new_faces"]})
    assert cap["centers"] == [[0.0, 0.0, 2.5]]


async def test_extrude_individual_and_inward(call, cube):
    name = await cube("Ind")
    await call("extrude", name=name, select={"all": True}, distance=0.3, mode="individual")
    info = await mesh(call, name)
    assert (info["vertices"], info["faces"], info["is_manifold"]) == (32, 30, True)

    name = await cube("Hollow")
    inner = await call("inset", name=name, select=UP, thickness=0.2)
    pushed = await call(
        "extrude", name=name, select={"indices": inner["inner_faces"]}, distance=-1.5
    )
    info = await mesh(call, name)
    assert info["is_manifold"] is True
    # Indices from before the extrude are stale now; use the ones it returned.
    floor = await call("select_elements", name=name, select={"indices": pushed["new_faces"]})
    assert approx(floor["centers"][0], [0, 0, -0.5])


async def test_bevel_sharp_edges(call, cube):
    name = await cube("Bev")
    result = await call("bevel", name=name, select={"sharp_angle": 60}, width=0.1, segments=3)
    assert result["count"] > 0
    info = await mesh(call, name)
    assert info["is_manifold"] is True and info["vertices"] > 8


async def test_loop_cut_and_subdivide(call, call_error, cube):
    name = await cube("Cut")
    middle = {"axis": "z", "min": -0.1, "max": 0.1}
    vertical = await call(
        "select_elements", name=name, type="edges",
        select={"normal": [1, 0, 0], "max_angle": 50, "position": middle},
    )  # fmt: skip
    cut = await call("loop_cut", name=name, select={"indices": vertical["indices"][:1]}, cuts=2)
    assert cut["ring_edges"] == 4 and cut["vertices"] == 16
    sub = await call("subdivide", name=name, cuts=1)
    assert sub["faces"] > 14

    dense = await cube("Dense", type="uv_sphere", segments=128, rings=64)
    before = (await mesh(call, dense))["faces"]
    assert "limit" in await call_error("subdivide", name=dense, cuts=20)
    assert (await mesh(call, dense))["faces"] == before  # untouched

    ico = await cube("Ico", type="ico_sphere")
    assert "strip of quads" in await call_error("loop_cut", name=ico, select={"indices": [0]})


async def test_bisect_keep_and_fill(call, cube):
    name = await cube("Half", type="uv_sphere")
    await call("bisect", name=name, normal=[1, 0, 0], keep="above", fill=True)
    info = await call("get_object_info", name=name)
    assert info["world_bounds"]["min"][0] >= -1e-4
    assert info["mesh"]["is_manifold"] is True

    ring = await cube("Ring")
    cut = await call("bisect", name=ring, point=[0, 0, 0.5])
    assert cut["cut_edges"] == 4 and cut["vertices"] == 12


async def test_delete_merge_normals(call, cube):
    name = await cube("Del")
    result = await call("delete_elements", name=name, select=UP)
    assert result["deleted"] == 1 and result["faces"] == 5
    assert (await mesh(call, name))["is_manifold"] is False

    name = await cube("Only")
    await call("delete_elements", name=name, select=UP, type="only_faces")
    assert (await mesh(call, name))["vertices"] == 8

    await call("recalc_normals", name=name, inside=True)
    faces = await call("select_elements", name=name, select={"normal": [0, 0, 1], "max_angle": 5})
    assert faces["centers"] == [[0.0, 0.0, -1.0]]  # bottom face now points up (inward)

    await call("create_primitive", type="cube", name="W1")
    await call("create_primitive", type="cube", name="W2", location=[2, 0, 0])
    await call("join_objects", names=["W1", "W2"])
    merged = await call("merge_by_distance", name="W1", distance=0.001)
    assert merged["removed_vertices"] == 4
    await call("delete_objects", names=["W1"])


async def test_transform_elements_taper(call, cube):
    name = await cube("Taper")
    result = await call(
        "transform_elements", name=name, select={"position": {"axis": "z", "min": 0.5}},
        type="verts", scale=0.5,
    )  # fmt: skip
    assert result["moved_vertices"] == 4 and result["pivot"] == [0.0, 0.0, 1.0]
    top = await call(
        "select_elements", name=name, type="verts", select={"position": {"axis": "z", "min": 0.5}}
    )
    assert all(abs(c[0]) == 0.5 for c in top["centers"])

    await call("transform_elements", name=name, select=UP, translate=[0, 0, 1])
    assert approx((await call("get_object_info", name=name))["dimensions"], [2, 2, 3])


async def test_shade(call, cube):
    name = await cube("Smooth", type="uv_sphere")
    assert (await call("shade", name=name, auto_smooth_angle=30))["smooth"] is True
    assert (await call("shade", name=name, smooth=False))["smooth"] is False


async def test_create_mesh_from_data(call, call_error):
    tetra = await call(
        "create_mesh_from_data",
        name="Tetra",
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
        faces=[[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]],
        location=[0, 0, 5],
    )
    assert tetra["faces"] == 4 and tetra["location"] == [0.0, 0.0, 5.0]
    assert (await mesh(call, "Tetra"))["is_manifold"] is True
    assert "0..2" in await call_error(
        "create_mesh_from_data", vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 5]]
    )
    assert "repeats" in await call_error(
        "create_mesh_from_data", vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 1]]
    )
    await call("delete_objects", names=["Tetra"])


async def test_mesh_edits_are_undoable(call, cube):
    name = await cube("Undo")
    await call("extrude", name=name, select=UP, distance=1)
    assert (await mesh(call, name))["vertices"] == 12
    await call("undo")
    assert (await mesh(call, name))["vertices"] == 8


async def test_model_a_mug(call, call_image):
    """The M4 goal: a mug with a handle, built only through tool calls."""
    await call(
        "create_primitive", type="cylinder", name="Mug", radius=0.5, depth=1.2,
        segments=48, location=[0, 0, 0.6],
    )  # fmt: skip
    # Hollow it: inset the top, push the inner face down, leaving a 0.15 floor.
    inner = await call("inset", name="Mug", select=UP, thickness=0.05)
    await call("extrude", name="Mug", select={"indices": inner["inner_faces"]}, distance=-1.05)
    # Round the rim (the sharp edges at the top).
    await call(
        "bevel", name="Mug", width=0.015, segments=2,
        select={"sharp_angle": 45, "position": {"axis": "z", "min": 0.55}},
    )  # fmt: skip

    # Handle: half a torus standing up, its cut ends buried in the wall.
    await call(
        "create_primitive", type="torus", name="Handle", major_radius=0.28, minor_radius=0.05,
        segments=48, rings=12, rotation=[90, 0, 0], location=[0.45, 0, 0.6],
    )  # fmt: skip
    await call("apply_transform", name="Handle", location=True)
    await call(
        "bisect", name="Handle", point=[0.47, 0, 0], normal=[1, 0, 0], keep="above", fill=True
    )
    assert (await mesh(call, "Handle"))["is_manifold"] is True

    await call("boolean", target="Mug", cutter="Handle", operation="UNION", cutter_action="delete")
    await call("shade", name="Mug", auto_smooth_angle=35)
    await call("create_material", name="Ceramic", base_color=[0.85, 0.3, 0.2], roughness=0.3)
    await call("assign_material", object="Mug", material="Ceramic")

    info = await call("get_object_info", name="Mug")
    assert info["mesh"]["is_manifold"] is True
    assert info["world_bounds"]["max"][0] > 0.75  # the handle sticks out
    assert approx(info["world_bounds"]["max"][2:], [1.2], tol=0.01)
    assert (await call("list_objects", name_contains="Handle"))["total"] == 0

    meta = await call_image("render_preview", view="iso", size=256, object="Mug")
    assert meta["width"] == 256
