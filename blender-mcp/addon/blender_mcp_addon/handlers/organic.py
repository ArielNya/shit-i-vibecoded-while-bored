"""Sculpt-style helpers for organic shapes: remesh, smoothing, noise displacement."""

from __future__ import annotations

from typing import Any

import bmesh
from mathutils import Vector, noise

from .editing import _apply_modifier
from .mesh_edit import MAX_RESULT_FACES, _edit, _mesh_object, _stats, select
from .undo import mutation


@mutation("remesh")
def remesh(params: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the mesh as an even voxel grid (or quad-ish for SMOOTH/SHARP) — good
    before sculpt-style edits, or to fuse overlapping parts into one shell."""
    obj = _mesh_object(params["name"])
    voxel_size = float(params.get("voxel_size", 0.05))
    if voxel_size <= 0:
        raise ValueError("voxel_size must be > 0")
    dims = obj.dimensions
    estimate = 2 * sum(a * b for a, b in ((dims.x, dims.y), (dims.y, dims.z), (dims.x, dims.z)))
    estimate = int(estimate / (voxel_size**2))
    if estimate > MAX_RESULT_FACES:
        raise ValueError(
            f"voxel_size {voxel_size} would make ~{estimate:,} faces (limit "
            f"{MAX_RESULT_FACES:,}); use a larger voxel_size"
        )
    mod = obj.modifiers.new("MCP Remesh", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel_size
    mod.use_smooth_shade = bool(params.get("smooth_shade", True))
    # Move it first so it applies to the base mesh, then bake it in.
    obj.modifiers.move(len(obj.modifiers) - 1, 0)
    try:
        _apply_modifier(obj, mod.name)
    except Exception:
        if obj.modifiers.get(mod.name):
            obj.modifiers.remove(mod)
        raise
    return {"name": obj.name, **_stats(obj)}


@mutation("smooth vertices")
def smooth_vertices(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    factor = float(params.get("factor", 0.5))
    iterations = int(params.get("iterations", 5))
    if not 0 < factor <= 1 or not 1 <= iterations <= 200:
        raise ValueError("factor must be in (0, 1] and iterations in 1..200")
    with _edit(obj) as bm:
        verts = select(bm, obj, params.get("select") or {"all": True}, "verts")
        for _ in range(iterations):
            bmesh.ops.smooth_vert(
                bm, verts=verts, factor=factor,
                use_axis_x=True, use_axis_y=True, use_axis_z=True,
            )  # fmt: skip
    return {"name": obj.name, "vertices_smoothed": len(verts), **_stats(obj)}


@mutation("add noise")
def add_noise(params: dict[str, Any]) -> dict[str, Any]:
    """Push vertices along their normals by fractal noise: rocks, terrain, bark."""
    obj = _mesh_object(params["name"])
    strength = float(params.get("strength", 0.2))
    scale = float(params.get("scale", 1.0))
    detail = int(params.get("detail", 4))
    seed = int(params.get("seed", 0))
    if scale <= 0 or not 1 <= detail <= 8:
        raise ValueError("scale must be > 0 and detail between 1 and 8")
    offset = Vector((seed * 17.31, seed * 3.77, seed * 11.13))
    with _edit(obj) as bm:
        verts = select(bm, obj, params.get("select") or {"all": True}, "verts")
        bm.normal_update()
        moves = []
        for v in verts:
            sample = noise.fractal(v.co * scale + offset, 1.0, 2.0, detail)
            moves.append((v, v.normal * (sample * strength)))
        for v, delta in moves:  # compute all first so earlier moves don't bias later ones
            v.co += delta
    return {"name": obj.name, "vertices_moved": len(verts), **_stats(obj)}
