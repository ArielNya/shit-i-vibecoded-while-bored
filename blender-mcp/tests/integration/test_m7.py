"""M7: animation, sculpt-style helpers, geometry nodes, several Blender instances."""

import os
import subprocess
import sys

import pytest

from blender_mcp import protocol

pytestmark = pytest.mark.anyio


def approx(values, expected, tol=1e-3):
    return all(abs(a - b) <= tol for a, b in zip(values, expected, strict=True))


# --- animation -----------------------------------------------------------------------------


async def test_keyframes_roundtrip(call, call_error):
    await call("create_primitive", type="cube", name="Mover")
    await call("set_keyframe", object="Mover", frame=1, value=[0, 0, 0])
    await call("set_keyframe", object="Mover", frame=48, value=[4, 0, 0], interpolation="LINEAR")
    result = await call(
        "set_keyframe", object="Mover", frame=48, property="rotation", value=[0, 0, 90]
    )
    assert result["keyframed_frames"] == [1.0, 48.0]

    keys = await call("list_keyframes", object="Mover")
    loc_x = next(c for c in keys["channels"] if c["property"] == "location" and c["index"] == 0)
    assert loc_x["keys"][0][:2] == [1.0, 0.0]
    assert loc_x["keys"][1] == [48.0, 4.0, "LINEAR"]
    rot_z = next(c for c in keys["channels"] if c["property"] == "rotation" and c["index"] == 2)
    assert rot_z["keys"][-1][1] == 90.0  # degrees in, degrees out

    # Values follow the animation when the frame changes.
    await call("set_frame_range", start=1, end=48, fps=24, current=24)
    info = await call("get_object_info", name="Mover")
    assert 0 < info["location"][0] < 4

    await call("set_keyframe", object="Mover", frame=10, property="hide_render", value=True)
    assert "no object property" in await call_error(
        "set_keyframe", object="Mover", property="data.lens"
    )
    cleared = await call("clear_animation", object="Mover")
    assert cleared["cleared"] is True
    assert (await call("list_keyframes", object="Mover"))["channels"] == []
    await call("delete_objects", names=["Mover"])


async def test_frame_range_validation(call, call_error):
    scene = await call("set_frame_range", start=10, end=20)
    assert (scene["start"], scene["end"]) == (10, 20)
    assert "end must be" in await call_error("set_frame_range", start=30, end=20)
    await call("set_frame_range", start=1, end=250)


# --- sculpt-style helpers ------------------------------------------------------------------


async def test_remesh_smooth_noise(call, call_error):
    await call("create_primitive", type="cube", name="Clay")
    remeshed = await call("remesh", name="Clay", voxel_size=0.1)
    assert remeshed["faces"] > 1000
    info = await call("get_object_info", name="Clay")
    assert info["mesh"]["is_manifold"] is True
    assert "limit" in await call_error("remesh", name="Clay", voxel_size=0.0005)

    corner = {
        "position": [
            {"axis": "x", "min": 0.97},
            {"axis": "y", "min": 0.97},
            {"axis": "z", "min": 0.97},
        ]
    }
    assert (await call("select_elements", name="Clay", type="verts", select=corner))["count"]
    await call("smooth_vertices", name="Clay", iterations=10)
    # Smoothing rounds the corners in: nothing is left near the (1, 1, 1) corner.
    assert "matched no" in await call_error(
        "select_elements", name="Clay", type="verts", select=corner
    )
    after = (await call("get_object_info", name="Clay"))["dimensions"]

    await call("add_noise", name="Clay", strength=0.3, scale=2, seed=7)
    noisy = (await call("get_object_info", name="Clay"))["dimensions"]
    assert noisy != after
    await call("delete_objects", names=["Clay"])


async def test_noise_is_deterministic_per_seed(call):
    dims = []
    for name, seed in (("RockA", 3), ("RockB", 3), ("RockC", 4)):
        await call("create_primitive", type="ico_sphere", name=name, subdivisions=4)
        await call("add_noise", name=name, strength=0.4, seed=seed)
        dims.append((await call("get_object_info", name=name))["dimensions"])
    assert dims[0] == dims[1] and dims[0] != dims[2]
    await call("delete_objects", names=["RockA", "RockB", "RockC"])


# --- geometry nodes ------------------------------------------------------------------------


async def test_find_node_types(call):
    found = await call("find_node_types", query="ico sphere")
    assert "GeometryNodeMeshIcoSphere" in [t["type"] for t in found["types"]]
    found = await call("find_node_types", query="distribute points")
    assert "GeometryNodeDistributePointsOnFaces" in [t["type"] for t in found["types"]]


SCATTER_NODES = [
    {
        "name": "Distribute",
        "type": "GeometryNodeDistributePointsOnFaces",
        "inputs": {"Density": 30},
    },
    {"name": "Ball", "type": "GeometryNodeMeshIcoSphere", "inputs": {"Radius": 0.05}},
    {"name": "Inst", "type": "GeometryNodeInstanceOnPoints"},
    {"name": "Real", "type": "GeometryNodeRealizeInstances"},
    {"name": "Join", "type": "GeometryNodeJoinGeometry"},
]
SCATTER_LINKS = [
    ["Group Input.Geometry", "Distribute.Mesh"],
    ["Distribute.Points", "Inst.Points"],
    ["Ball.Mesh", "Inst.Instance"],
    ["Inst.Instances", "Real.Geometry"],
    ["Real.Geometry", "Join.Geometry"],
    ["Group Input.Geometry", "Join.Geometry"],
    ["Join.Geometry", "Group Output.Geometry"],
]


async def test_build_scatter_setup(call, call_image):
    await call("create_primitive", type="plane", name="Ground", size=4)
    built = await call(
        "build_geometry_nodes", object="Ground", nodes=SCATTER_NODES, links=SCATTER_LINKS
    )
    assert built["base_mesh"]["vertices"] == 4
    assert built["evaluated"]["vertices"] > 1000  # hundreds of little spheres
    assert len(built["links"]) == 7
    ball = next(n for n in built["nodes"] if n["name"] == "Ball")
    assert next(i for i in ball["inputs"] if i["name"] == "Radius")["value"] == 0.05

    rebuilt = await call(
        "build_geometry_nodes",
        object="Ground",
        nodes=[{**SCATTER_NODES[0], "inputs": {"Density": 1}}, *SCATTER_NODES[1:]],
        links=SCATTER_LINKS,
    )
    assert rebuilt["evaluated"]["vertices"] < built["evaluated"]["vertices"]
    listed = await call("get_geometry_nodes", object="Ground")
    assert len(listed["node_modifiers"]) == 1  # replaced, not stacked

    await call_image("render_preview", view="iso", size=128, object="Ground")
    await call("delete_objects", names=["Ground"])


async def test_geometry_nodes_errors_leave_nothing_behind(call, call_error):
    await call("create_primitive", type="cube", name="GNErr")
    text = await call_error(
        "build_geometry_nodes", object="GNErr",
        nodes=[{"name": "X", "type": "GeometryNodeNope"}], links=[],
    )  # fmt: skip
    assert "find_node_types" in text
    text = await call_error(
        "build_geometry_nodes", object="GNErr",
        nodes=[{"name": "Ball", "type": "GeometryNodeMeshIcoSphere"}],
        links=[["Ball.Nope", "Group Output.Geometry"]],
    )  # fmt: skip
    assert "no output socket 'Nope'" in text and "Mesh" in text
    assert (await call("get_geometry_nodes", object="GNErr"))["node_modifiers"] == []
    await call("delete_objects", names=["GNErr"])


# --- several Blenders ----------------------------------------------------------------------


async def test_second_blender_takes_next_port(call, blender_port, token_file, blender_command):
    """A second Blender asked for a taken port with --auto-port listens on the next
    one; list_blender_instances finds both, use_blender switches between them."""
    env = {**os.environ, protocol.TOKEN_FILE_ENV: str(token_file)}
    args = ["--", "--port", str(blender_port), "--auto-port", "--no-auth"]
    proc = subprocess.Popen(
        [*blender_command, *args], env=env, stdout=subprocess.PIPE, stderr=sys.stderr, text=True
    )
    try:
        second = None
        for line in proc.stdout:
            if line.startswith("BLENDER_MCP_READY"):
                second = int(line.rsplit(":", 1)[1])
                break
        assert second == blender_port + 1

        found = await call("list_blender_instances", first_port=blender_port, count=2)
        ports = {i["port"]: i for i in found["instances"]}
        assert ports[blender_port]["active"] is True and second in ports

        switched = await call("use_blender", port=second)
        assert switched["active_port"] == second
        await call("create_primitive", type="cube", name="OnlyInSecond")
        await call("use_blender", port=blender_port)
        assert (await call("list_objects", name_contains="OnlyInSecond"))["total"] == 0
    finally:
        proc.terminate()
        proc.wait(timeout=10)
