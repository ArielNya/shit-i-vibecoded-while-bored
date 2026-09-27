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
            value = getattr(struct, ident)
        except AttributeError:
            continue
        if prop.subtype in ANGLE_SUBTYPES:  # the API speaks degrees; see set_rna_props
            value = [math.degrees(v) for v in value] if prop.is_array else math.degrees(value)
        out[ident] = rna_value(value)
    return out


ANGLE_SUBTYPES = {"ANGLE", "EULER"}
# File paths would let a caller point e.g. a Mesh Cache modifier at any local file and
# read it back through get_mesh_data. Refused until there's a path allowlist (PLAN §5).
PATH_SUBTYPES = {"FILE_PATH", "DIR_PATH", "FILE_NAME", "BYTE_STRING"}
POINTER_LOOKUPS = {
    "Object": lambda: bpy.data.objects,
    "Collection": lambda: bpy.data.collections,
    "Material": lambda: bpy.data.materials,
    "Texture": lambda: bpy.data.textures,
    "Image": lambda: bpy.data.images,
    "Curve": lambda: bpy.data.curves,
}


def settable_props(struct: Any) -> list[str]:
    return sorted(
        p.identifier
        for p in struct.bl_rna.properties
        if not p.is_readonly and p.identifier not in SKIP_PROPS and p.type != "COLLECTION"
    )


def set_rna_props(struct: Any, params: dict[str, Any]) -> None:
    """Set properties from JSON values: angles in degrees, ID pointers by name.

    Validates every key before changing anything, so a typo doesn't leave a
    half-applied update.
    """
    props = struct.bl_rna.properties
    kind = struct.bl_rna.identifier
    resolved: list[tuple[str, Any]] = []
    for key, value in params.items():
        prop = props.get(key)
        if prop is None or prop.is_readonly or key in SKIP_PROPS or prop.type == "COLLECTION":
            raise ValueError(
                f"{kind} has no settable property {key!r}. "
                f"Valid: {', '.join(settable_props(struct))}"
            )
        if prop.subtype in PATH_SUBTYPES:
            raise ValueError(f"{kind}.{key} is a file path; setting paths isn't allowed")
        if prop.type == "POINTER":
            if value is not None:
                lookup = POINTER_LOOKUPS.get(prop.fixed_type.identifier)
                if lookup is None:
                    raise ValueError(f"{kind}.{key} can't be set from a name")
                found = lookup().get(value)
                if found is None:
                    raise ValueError(
                        f"{kind}.{key}: no {prop.fixed_type.identifier} named {value!r}"
                    )
                value = found
        elif prop.subtype in ANGLE_SUBTYPES and value is not None:
            value = [math.radians(v) for v in value] if prop.is_array else math.radians(value)
        resolved.append((key, value))
    for key, value in resolved:
        try:
            setattr(struct, key, value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{kind}.{key}: {exc}") from None


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
