from __future__ import annotations

from typing import Any

import bmesh
import bpy

from .util import degrees, get_object, num, page, rna_props, vec, world_bounds

MAX_OBJECTS = 500
MAX_MESH_ITEMS = 5000
# Above this, skip the bmesh pass that computes manifold/n-gon stats.
TOPOLOGY_STATS_MAX_VERTS = 200_000


def _summary(obj: bpy.types.Object) -> dict[str, Any]:
    return {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "collections": [c.name for c in obj.users_collection],
        "location": vec(obj.location),
        "rotation_deg": degrees(obj.rotation_euler),
        "scale": vec(obj.scale),
        "dimensions": vec(obj.dimensions),
        "visible": obj.visible_get(),
    }


def list_objects(params: dict[str, Any]) -> dict[str, Any]:
    obj_type = params.get("type")
    collection = params.get("collection")
    name_contains = (params.get("name_contains") or "").lower()

    if collection:
        coll = bpy.data.collections.get(collection)
        if coll is None and collection != bpy.context.scene.collection.name:
            raise ValueError(f"No collection named {collection!r}")
        source = coll.all_objects if coll else bpy.context.scene.collection.all_objects
    else:
        source = bpy.context.scene.objects

    objects = [
        obj
        for obj in source
        if (not obj_type or obj.type == obj_type.upper())
        and (not name_contains or name_contains in obj.name.lower())
    ]
    objects.sort(key=lambda o: o.name)
    chunk, meta = page(objects, params.get("offset", 0), params.get("limit", 100), MAX_OBJECTS)
    return {**meta, "objects": [_summary(obj) for obj in chunk]}


def _mesh_stats(obj: bpy.types.Object) -> dict[str, Any]:
    mesh = obj.data
    polys = mesh.polygons
    stats: dict[str, Any] = {
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "faces": len(polys),
        "triangles": sum(len(p.vertices) - 2 for p in polys),
        "tris": sum(1 for p in polys if len(p.vertices) == 3),
        "quads": sum(1 for p in polys if len(p.vertices) == 4),
        "ngons": sum(1 for p in polys if len(p.vertices) > 4),
        "uv_layers": [uv.name for uv in mesh.uv_layers],
        "vertex_groups": [vg.name for vg in obj.vertex_groups],
        "shape_keys": [k.name for k in mesh.shape_keys.key_blocks] if mesh.shape_keys else [],
    }
    if len(mesh.vertices) <= TOPOLOGY_STATS_MAX_VERTS:
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
            stats["non_manifold_edges"] = non_manifold
            stats["is_manifold"] = non_manifold == 0 and len(bm.edges) > 0
            stats["loose_vertices"] = sum(1 for v in bm.verts if not v.link_edges)
        finally:
            bm.free()
    if any(m.show_viewport for m in obj.modifiers):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        eval_mesh = evaluated.to_mesh()
        try:
            stats["with_modifiers"] = {
                "vertices": len(eval_mesh.vertices),
                "faces": len(eval_mesh.polygons),
                "triangles": sum(len(p.vertices) - 2 for p in eval_mesh.polygons),
            }
        finally:
            evaluated.to_mesh_clear()
    return stats


def _data_info(obj: bpy.types.Object) -> dict[str, Any] | None:
    data = obj.data
    if obj.type == "MESH":
        return _mesh_stats(obj)
    if obj.type == "CAMERA":
        return {
            "type": data.type,
            "lens_mm": num(data.lens),
            "ortho_scale": num(data.ortho_scale),
            "clip": [num(data.clip_start), num(data.clip_end)],
            "is_scene_camera": bpy.context.scene.camera == obj,
        }
    if obj.type == "LIGHT":
        info = {"type": data.type, "energy": num(data.energy), "color": vec(data.color)}
        if data.type == "SPOT":
            info["spot_size_deg"] = num(data.spot_size * 57.29578)
        if data.type == "AREA":
            info["size"] = num(data.size)
        return info
    if obj.type == "CURVE":
        return {
            "splines": len(data.splines),
            "dimensions": data.dimensions,
            "bevel_depth": num(data.bevel_depth),
            "extrude": num(data.extrude),
        }
    if obj.type == "EMPTY":
        return {"display_type": obj.empty_display_type, "display_size": num(obj.empty_display_size)}
    return None


def _custom_props(obj: bpy.types.Object) -> dict[str, Any]:
    out = {}
    for key in obj.keys():
        if key.startswith("_"):
            continue
        value = obj[key]
        out[key] = value.to_dict() if hasattr(value, "to_dict") else value
    return out


def get_object_info(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    bounds = world_bounds([obj])
    info: dict[str, Any] = {
        **_summary(obj),
        "data": obj.data.name if obj.data else None,
        "rotation_mode": obj.rotation_mode,
        "world_location": vec(obj.matrix_world.translation),
        "world_bounds": {"min": vec(bounds[0]), "max": vec(bounds[1])} if bounds else None,
        "children": [child.name for child in obj.children],
        "hide_viewport": obj.hide_viewport,
        "hide_render": obj.hide_render,
        "modifiers": [
            {"name": m.name, "type": m.type, "show_viewport": m.show_viewport, **rna_props(m)}
            for m in obj.modifiers
        ],
        "materials": [
            {
                "slot": i,
                "material": slot.material.name if slot.material else None,
                "link": slot.link,
            }
            for i, slot in enumerate(obj.material_slots)
        ],
        "constraints": [
            {
                "name": c.name,
                "type": c.type,
                "target": getattr(getattr(c, "target", None), "name", None),
            }
            for c in obj.constraints
        ],
        "custom_properties": _custom_props(obj),
    }
    data_info = _data_info(obj)
    if data_info is not None:
        info[obj.type.lower()] = data_info
    return info


def get_mesh_data(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    if obj.type != "MESH":
        raise ValueError(f"{obj.name!r} is a {obj.type}, not a MESH")
    space = params.get("space", "local")
    if space not in {"local", "world"}:
        raise ValueError("space must be 'local' or 'world'")
    offset = params.get("offset", 0)
    limit = params.get("limit", 500)

    evaluated = None
    if params.get("evaluated"):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
    else:
        mesh = obj.data
    try:
        matrix = obj.matrix_world if space == "world" else None
        verts, vmeta = page(list(mesh.vertices), offset, limit, MAX_MESH_ITEMS)
        faces, fmeta = page(list(mesh.polygons), offset, limit, MAX_MESH_ITEMS)
        return {
            "name": obj.name,
            "space": space,
            "evaluated": bool(evaluated),
            "vertices": {
                **vmeta,
                "items": [vec(matrix @ v.co) if matrix else vec(v.co) for v in verts],
            },
            "faces": {**fmeta, "items": [list(p.vertices) for p in faces]},
        }
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
