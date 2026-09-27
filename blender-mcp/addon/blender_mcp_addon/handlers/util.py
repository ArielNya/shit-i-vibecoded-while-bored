"""Helpers shared by handlers: lookups, value conversion, bounds."""

from __future__ import annotations

import math
from typing import Any

import bpy
from mathutils import Vector

PRECISION = 4


def num(value: float) -> float:
    return round(float(value), PRECISION)


def vec(values) -> list[float]:
    return [num(v) for v in values]


def degrees(euler) -> list[float]:
    return [num(math.degrees(a)) for a in euler]


def get_object(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        names = sorted(o.name for o in bpy.context.scene.objects)
        hint = ", ".join(names[:20]) + (" …" if len(names) > 20 else "")
        raise ValueError(f"No object named {name!r}. Objects in scene: {hint or '(none)'}")
    return obj


def get_material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        names = sorted(m.name for m in bpy.data.materials)
        raise ValueError(f"No material named {name!r}. Materials: {', '.join(names) or '(none)'}")
    return mat


def page(items: list, offset: int, limit: int, max_limit: int) -> tuple[list, dict[str, Any]]:
    """Slice items and describe the slice so the model knows whether to ask for more."""
    if offset < 0 or limit < 1:
        raise ValueError("offset must be >= 0 and limit >= 1")
    limit = min(limit, max_limit)
    chunk = items[offset : offset + limit]
    meta = {"total": len(items), "offset": offset, "returned": len(chunk)}
    if offset + len(chunk) < len(items):
        meta["next_offset"] = offset + len(chunk)
    return chunk, meta


def rna_value(value: Any) -> Any:
    """Convert an RNA property value to something JSON-friendly and compact."""
    if isinstance(value, bool | int | str) or value is None:
        return value
    if isinstance(value, float):
        return num(value)
    if isinstance(value, bpy.types.ID):
        return value.name
    if hasattr(value, "__len__") and len(value) <= 16:
        try:
            return [rna_value(v) for v in value]
        except TypeError:
            pass
    return str(value)


SKIP_PROPS = {"rna_type", "name", "type", "bl_rna"}


def rna_props(struct: Any, skip: set[str] = frozenset()) -> dict[str, Any]:
    """Simple (non-collection) properties of an RNA struct, e.g. a modifier's settings."""
    out: dict[str, Any] = {}
    for prop in struct.bl_rna.properties:
        ident = prop.identifier
        if ident in SKIP_PROPS or ident in skip or prop.type == "COLLECTION":
            continue
        if prop.type == "POINTER" and not isinstance(getattr(struct, ident, None), bpy.types.ID):
            continue
        try:
            out[ident] = rna_value(getattr(struct, ident))
        except (AttributeError, TypeError):
            continue
    return out


def world_bounds(objects) -> tuple[Vector, Vector] | None:
    """Axis-aligned world-space bounds of the given objects' bounding boxes."""
    corners = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        if obj.type not in {"CAMERA", "LIGHT", "LIGHT_PROBE", "SPEAKER"}
        for corner in obj.bound_box
    ]
    if not corners:
        return None
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return lo, hi
