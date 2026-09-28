from __future__ import annotations

from typing import Any

import bpy

from .editing import _apply_modifier
from .undo import mutation
from .util import get_object, rna_props, set_rna_props


def _modifier_types() -> list[str]:
    return sorted(i.identifier for i in bpy.types.Modifier.bl_rna.properties["type"].enum_items)


def _get_modifier(obj: bpy.types.Object, name: str) -> bpy.types.Modifier:
    mod = obj.modifiers.get(name)
    if mod is None:
        names = [m.name for m in obj.modifiers]
        raise ValueError(f"{obj.name!r} has no modifier {name!r}. Modifiers: {names or '(none)'}")
    return mod


def _describe(mod: bpy.types.Modifier) -> dict[str, Any]:
    return {"name": mod.name, "type": mod.type, **rna_props(mod)}


def _stack(obj: bpy.types.Object) -> list[str]:
    return [f"{m.name} ({m.type})" for m in obj.modifiers]


@mutation("add modifier")
def add_modifier(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    mod_type = params["type"].upper()
    if mod_type not in _modifier_types():
        raise ValueError(
            f"unknown modifier type {mod_type!r}. Types: {', '.join(_modifier_types())}"
        )
    mod = obj.modifiers.new(params.get("name") or mod_type.title().replace("_", " "), mod_type)
    if mod is None:
        raise ValueError(f"a {mod_type} modifier can't be added to a {obj.type}")
    try:
        set_rna_props(mod, params.get("params") or {})
    except ValueError:
        obj.modifiers.remove(mod)  # don't leave a half-configured modifier behind
        raise
    return {"object": obj.name, "modifier": _describe(mod), "stack": _stack(obj)}


@mutation("set modifier params")
def set_modifier_params(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    mod = _get_modifier(obj, params["modifier"])
    set_rna_props(mod, params["params"])
    return {"object": obj.name, "modifier": _describe(mod)}


@mutation("remove modifier")
def remove_modifier(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    obj.modifiers.remove(_get_modifier(obj, params["modifier"]))
    return {"object": obj.name, "stack": _stack(obj)}


@mutation("apply modifier")
def apply_modifier(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    mod = _get_modifier(obj, params["modifier"])
    was_first = obj.modifiers[0] == mod
    _apply_modifier(obj, mod.name)
    result: dict[str, Any] = {"object": obj.name, "stack": _stack(obj)}
    if obj.type == "MESH":
        result["vertices"] = len(obj.data.vertices)
        result["faces"] = len(obj.data.polygons)
    if not was_first:
        result["note"] = (
            "Applied a modifier that wasn't first in the stack; modifiers above it were "
            "ignored for this result."
        )
    return result


@mutation("move modifier")
def move_modifier(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    mod = _get_modifier(obj, params["modifier"])
    index = int(params["index"])
    if not 0 <= index < len(obj.modifiers):
        raise ValueError(f"index must be between 0 and {len(obj.modifiers) - 1}")
    obj.modifiers.move(list(obj.modifiers).index(mod), index)
    return {"object": obj.name, "stack": _stack(obj)}
