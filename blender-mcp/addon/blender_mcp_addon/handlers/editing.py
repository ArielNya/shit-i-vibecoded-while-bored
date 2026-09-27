"""Object-level editing: create, transform, duplicate, delete, organize, join, booleans.

Uses bpy.data / bmesh rather than bpy.ops wherever possible, so behaviour doesn't
depend on UI context (which differs between timers, GUI and --background).
"""

from __future__ import annotations

import math
from typing import Any

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from .objects import _summary
from .undo import mutation, window_override
from .util import get_object

MESH_PRIMITIVES = {
    "cube", "plane", "grid", "circle", "uv_sphere", "ico_sphere",
    "cylinder", "cone", "torus", "monkey",
}  # fmt: skip
OTHER_PRIMITIVES = {"empty", "camera", "light"}
DEFAULT_NAMES = {
    "uv_sphere": "Sphere", "ico_sphere": "Icosphere", "monkey": "Suzanne",
}  # fmt: skip
MAX_SEGMENTS = 512
MAX_PARTS = 256


def _vec3(value: Any, name: str) -> Vector:
    if isinstance(value, int | float):
        return Vector((value, value, value))
    if isinstance(value, str) or not hasattr(value, "__len__") or len(value) != 3:
        raise ValueError(f"{name} must be a number or a list of 3 numbers")
    return Vector([float(v) for v in value])


def _rotation(value: Any) -> Euler:
    return Euler([math.radians(a) for a in _vec3(value, "rotation")])


def _count(params: dict[str, Any], key: str, default: int, minimum: int = 3) -> int:
    value = int(params.get(key, default))
    if not minimum <= value <= MAX_SEGMENTS:
        raise ValueError(f"{key} must be between {minimum} and {MAX_SEGMENTS}")
    return value


def _target_collection(name: str | None) -> bpy.types.Collection:
    if not name:
        return bpy.context.view_layer.active_layer_collection.collection
    if name == bpy.context.scene.collection.name:
        return bpy.context.scene.collection
    coll = bpy.data.collections.get(name)
    if coll is None:
        raise ValueError(f"No collection named {name!r} (create it with create_collection)")
    return coll


def _make_active(obj: bpy.types.Object) -> None:
    view_layer = bpy.context.view_layer
    for other in view_layer.objects:
        if other.select_get():
            other.select_set(False)
    if view_layer.objects.get(obj.name) is not None:
        obj.select_set(True)
        view_layer.objects.active = obj


def _torus(bm: bmesh.types.BMesh, major: float, minor: float, seg: int, ring: int) -> None:
    grid = []
    for i in range(seg):
        u = 2 * math.pi * i / seg
        row = []
        for j in range(ring):
            v = 2 * math.pi * j / ring
            r = major + minor * math.cos(v)
            row.append(bm.verts.new((r * math.cos(u), r * math.sin(u), minor * math.sin(v))))
        grid.append(row)
    for i in range(seg):
        for j in range(ring):
            a, b = grid[i][j], grid[(i + 1) % seg][j]
            c, d = grid[(i + 1) % seg][(j + 1) % ring], grid[i][(j + 1) % ring]
            bm.faces.new((a, b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _build_mesh(kind: str, p: dict[str, Any], name: str) -> bpy.types.Mesh:
    size = float(p.get("size", 2.0))
    radius = float(p.get("radius", 1.0))
    depth = float(p.get("depth", 2.0))
    bm = bmesh.new()
    try:
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=size, calc_uvs=True)
        elif kind == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2, calc_uvs=True)
        elif kind == "grid":
            bmesh.ops.create_grid(
                bm,
                x_segments=_count(p, "x_segments", 10, 1),
                y_segments=_count(p, "y_segments", 10, 1),
                size=size / 2,
                calc_uvs=True,
            )
        elif kind == "circle":
            bmesh.ops.create_circle(
                bm,
                cap_ends=bool(p.get("fill", False)),
                segments=_count(p, "segments", 32),
                radius=radius,
                calc_uvs=True,
            )
        elif kind == "uv_sphere":
            bmesh.ops.create_uvsphere(
                bm,
                u_segments=_count(p, "segments", 32),
                v_segments=_count(p, "rings", 16),
                radius=radius,
                calc_uvs=True,
            )
        elif kind == "ico_sphere":
            subdivisions = int(p.get("subdivisions", 2))
            if not 1 <= subdivisions <= 7:
                raise ValueError("subdivisions must be between 1 and 7")
            bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=radius, calc_uvs=True)
        elif kind in {"cylinder", "cone"}:
            top = radius if kind == "cylinder" else float(p.get("radius_top", 0.0))
            bmesh.ops.create_cone(
                bm,
                cap_ends=True,
                cap_tris=False,
                segments=_count(p, "segments", 32),
                radius1=radius,
                radius2=top,
                depth=depth,
                calc_uvs=True,
            )
        elif kind == "torus":
            _torus(
                bm,
                float(p.get("major_radius", 1.0)),
                float(p.get("minor_radius", 0.25)),
                _count(p, "segments", 48),
                _count(p, "rings", 12),
            )
        elif kind == "monkey":
            bmesh.ops.create_monkey(bm)
            bmesh.ops.scale(bm, vec=(size / 2,) * 3, verts=bm.verts)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if p.get("shade_smooth"):
        mesh.shade_smooth()
    return mesh


def _build_other(kind: str, p: dict[str, Any], name: str) -> bpy.types.ID | None:
    if kind == "empty":
        return None
    if kind == "camera":
        cam = bpy.data.cameras.new(name)
        cam.lens = float(p.get("lens", 50.0))
        return cam
    light_type = str(p.get("light_type", "POINT")).upper()
    if light_type not in {"POINT", "SUN", "SPOT", "AREA"}:
        raise ValueError("light_type must be POINT, SUN, SPOT or AREA")
    light = bpy.data.lights.new(name, light_type)
    light.energy = float(p.get("energy", 3.0 if light_type == "SUN" else 1000.0))
    if "color" in p:
        light.color = p["color"]
    return light


@mutation("create primitive")
def create_primitive(params: dict[str, Any]) -> dict[str, Any]:
    kind = params["type"]
    if kind not in MESH_PRIMITIVES | OTHER_PRIMITIVES:
        raise ValueError(f"type must be one of {sorted(MESH_PRIMITIVES | OTHER_PRIMITIVES)}")
    name = params.get("name") or DEFAULT_NAMES.get(kind, kind.title())
    collection = _target_collection(params.get("collection"))
    if kind in MESH_PRIMITIVES:
        data = _build_mesh(kind, params, name)
    else:
        data = _build_other(kind, params, name)
    obj = bpy.data.objects.new(name, data)
    if kind == "empty":
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = float(params.get("size", 1.0))
    obj.location = _vec3(params.get("location", 0), "location")
    obj.rotation_euler = _rotation(params.get("rotation", 0))
    obj.scale = _vec3(params.get("scale", 1), "scale")
    collection.objects.link(obj)
    if kind == "camera" and params.get("set_active_camera", bpy.context.scene.camera is None):
        bpy.context.scene.camera = obj
    _make_active(obj)
    return _summary(obj)


@mutation("transform")
def transform_object(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    delta = params.get("mode", "set") == "delta"
    if "location" in params:
        loc = _vec3(params["location"], "location")
        obj.location = obj.location + loc if delta else loc
    if "rotation" in params:
        rot = _vec3(params["rotation"], "rotation")
        if delta:
            obj.rotation_euler = Euler(
                [a + math.radians(d) for a, d in zip(obj.rotation_euler, rot, strict=True)],
                obj.rotation_euler.order,
            )
        else:
            obj.rotation_euler = _rotation(rot)
    if "scale" in params:
        scale = _vec3(params["scale"], "scale")
        obj.scale = Vector(a * b for a, b in zip(obj.scale, scale, strict=True)) if delta else scale
    if "dimensions" in params:
        bpy.context.view_layer.update()  # dimensions are derived from the evaluated bounds
        obj.dimensions = _vec3(params["dimensions"], "dimensions")
    return _summary(obj)


@mutation("apply transform")
def apply_transform(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    if obj.data is not None and obj.data.users > 1:
        raise ValueError(f"{obj.name!r} shares its data with other objects; can't apply")
    override = {
        **window_override(),
        "object": obj,
        "active_object": obj,
        "selected_objects": [obj],
        "selected_editable_objects": [obj],
    }
    with bpy.context.temp_override(**override):
        bpy.ops.object.transform_apply(
            location=bool(params.get("location", False)),
            rotation=bool(params.get("rotation", True)),
            scale=bool(params.get("scale", True)),
        )
    return _summary(obj)


@mutation("duplicate")
def duplicate_object(params: dict[str, Any]) -> dict[str, Any]:
    src = get_object(params["name"])
    dup = src.copy()
    if src.data is not None and not params.get("linked", False):
        dup.data = src.data.copy()
    if params.get("new_name"):
        dup.name = params["new_name"]
    for coll in src.users_collection:
        coll.objects.link(dup)
    if "offset" in params:
        dup.location = src.location + _vec3(params["offset"], "offset")
    _make_active(dup)
    return _summary(dup)


@mutation("delete")
def delete_objects(params: dict[str, Any]) -> dict[str, Any]:
    names = params["names"]
    if isinstance(names, str):
        names = [names]
    objects = [get_object(n) for n in names]  # validate all first
    doomed = {o.name: o for o in objects}
    if params.get("delete_children"):
        for obj in objects:
            doomed.update({c.name: c for c in obj.children_recursive})
    deleted = sorted(doomed)
    for obj in doomed.values():
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": deleted}


@mutation("rename")
def rename_object(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    obj.name = params["new_name"]
    if params.get("rename_data") and obj.data is not None:
        obj.data.name = obj.name
    return {"name": obj.name, "requested": params["new_name"]}


@mutation("set parent")
def set_parent(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    parent_name = params.get("parent")
    world = obj.matrix_world.copy()
    keep = params.get("keep_transform", True)
    if parent_name:
        parent = get_object(parent_name)
        if parent == obj or parent in obj.children_recursive:
            raise ValueError(f"{parent.name!r} can't be the parent of {obj.name!r} (cycle)")
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted() if keep else Matrix()
    else:
        obj.parent = None
        if keep:
            obj.matrix_world = world
    return _summary(obj)


@mutation("create collection")
def create_collection(params: dict[str, Any]) -> dict[str, Any]:
    parent = _target_collection(params.get("parent") or bpy.context.scene.collection.name)
    coll = bpy.data.collections.new(params["name"])
    parent.children.link(coll)
    return {"name": coll.name, "parent": parent.name}


@mutation("move to collection")
def move_to_collection(params: dict[str, Any]) -> dict[str, Any]:
    names = params["names"]
    if isinstance(names, str):
        names = [names]
    objects = [get_object(n) for n in names]
    target = _target_collection(params["collection"])
    for obj in objects:
        if target not in obj.users_collection:
            target.objects.link(obj)
        for coll in list(obj.users_collection):
            if coll != target:
                coll.objects.unlink(obj)
    return {"moved": [o.name for o in objects], "collection": target.name}


@mutation("join")
def join_objects(params: dict[str, Any]) -> dict[str, Any]:
    names = params["names"]
    if len(names) < 2:
        raise ValueError("need at least two objects to join")
    objects = [get_object(n) for n in names]
    target = get_object(params.get("into") or names[0])
    if target not in objects:
        objects.append(target)
    bad = [o.name for o in objects if o.type != "MESH"]
    if bad:
        raise ValueError(f"only meshes can be joined; not meshes: {bad}")
    override = {
        **window_override(),
        "object": target,
        "active_object": target,
        "selected_objects": objects,
        "selected_editable_objects": objects,
    }
    with bpy.context.temp_override(**override):
        bpy.ops.object.join()
    return _summary(target)


def _components(bm: bmesh.types.BMesh) -> list[set[int]]:
    seen: set[int] = set()
    parts = []
    for start in bm.verts:
        if start.index in seen:
            continue
        stack, part = [start], set()
        while stack:
            v = stack.pop()
            if v.index in part:
                continue
            part.add(v.index)
            stack.extend(e.other_vert(v) for e in v.link_edges if e.other_vert(v).index not in part)
        seen |= part
        parts.append(part)
    return parts


def _keep_only(obj: bpy.types.Object, keep_verts: set[int] | None, keep_mat: int | None) -> None:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        if keep_verts is not None:
            doomed = [v for v in bm.verts if v.index not in keep_verts]
            bmesh.ops.delete(bm, geom=doomed, context="VERTS")
        else:
            doomed = [f for f in bm.faces if f.material_index != keep_mat]
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(obj.data)
    finally:
        bm.free()


@mutation("separate")
def separate_mesh(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    if obj.type != "MESH":
        raise ValueError(f"{obj.name!r} is not a mesh")
    mode = params.get("mode", "loose")
    if mode == "loose":
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            groups: list[Any] = sorted(_components(bm), key=min)
        finally:
            bm.free()
    elif mode == "material":
        groups = sorted({poly.material_index for poly in obj.data.polygons})
    else:
        raise ValueError("mode must be 'loose' or 'material'")
    if len(groups) > MAX_PARTS:
        raise ValueError(f"would create {len(groups)} objects (limit {MAX_PARTS})")
    if len(groups) < 2:
        return {"parts": [obj.name], "note": "nothing to separate"}

    parts = [obj]
    for _ in groups[1:]:
        part = obj.copy()
        part.data = obj.data.copy()
        for coll in obj.users_collection:
            coll.objects.link(part)
        parts.append(part)
    for part, group in zip(parts, groups, strict=True):
        if mode == "loose":
            _keep_only(part, group, None)
        else:
            _keep_only(part, None, group)
    return {"parts": [p.name for p in parts]}


@mutation("boolean")
def boolean(params: dict[str, Any]) -> dict[str, Any]:
    target = get_object(params["target"])
    cutter = get_object(params["cutter"])
    if target.type != "MESH" or cutter.type != "MESH":
        raise ValueError("boolean needs two meshes")
    if target == cutter:
        raise ValueError("target and cutter must differ")
    operation = params.get("operation", "DIFFERENCE").upper()
    if operation not in {"DIFFERENCE", "UNION", "INTERSECT"}:
        raise ValueError("operation must be DIFFERENCE, UNION or INTERSECT")
    applied = bool(params.get("apply", True))
    cutter_action = params.get("cutter_action", "hide")
    if cutter_action not in {"hide", "delete", "keep"}:
        raise ValueError("cutter_action must be hide, delete or keep")
    if cutter_action == "delete" and not applied:
        raise ValueError("can't delete the cutter when apply=false")
    mod = target.modifiers.new(f"Boolean {cutter.name}", "BOOLEAN")
    try:
        mod.operation = operation
        mod.object = cutter
        mod.solver = params.get("solver", "EXACT").upper()
        if applied:
            _apply_modifier(target, mod.name)
    except Exception:
        if target.modifiers.get(mod.name) is not None:
            target.modifiers.remove(mod)
        raise
    if cutter_action == "delete":
        bpy.data.objects.remove(cutter, do_unlink=True)
    elif cutter_action == "hide":
        cutter.hide_set(True)
        cutter.hide_render = True
    return {**_summary(target), "applied": applied, "cutter": cutter_action}


def _apply_modifier(obj: bpy.types.Object, name: str) -> None:
    if obj.data is not None and obj.data.users > 1:
        raise ValueError(f"{obj.name!r} shares its mesh with other objects; can't apply")
    override = {**window_override(), "object": obj, "active_object": obj}
    with bpy.context.temp_override(**override):
        bpy.ops.object.modifier_apply(modifier=name)
