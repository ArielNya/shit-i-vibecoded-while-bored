"""Command handlers. Each takes the request params dict and returns JSON-able data.

Handlers always run on Blender's main thread, so they may use bpy freely.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import bpy

from . import editing, materials, modifiers, objects, render, scene, undo


def ping(params: dict[str, Any]) -> dict[str, Any]:
    # Goes through the main-thread queue like every other handler, so a reply proves
    # Blender's event loop is actually draining requests.
    return {"pong": True}


def _fresh(fn: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
    """Evaluate pending changes first so bounds/matrices/dimensions aren't stale.

    Blender only re-evaluates the depsgraph on redraw or when asked; headless (and
    between our calls) nothing asks, so a previous edit may not be reflected yet.
    """

    @functools.wraps(fn)
    def wrapper(params: dict[str, Any]) -> Any:
        bpy.context.view_layer.update()
        return fn(params)

    return wrapper


_HANDLERS = {
    "ping": ping,
    "get_scene_info": scene.get_scene_info,
    "list_objects": objects.list_objects,
    "get_object_info": objects.get_object_info,
    "get_mesh_data": objects.get_mesh_data,
    "list_materials": materials.list_materials,
    "get_material_info": materials.get_material_info,
    "get_viewport_screenshot": render.get_viewport_screenshot,
    "render_preview": render.render_preview,
    # M2: editing
    "create_primitive": editing.create_primitive,
    "transform_object": editing.transform_object,
    "apply_transform": editing.apply_transform,
    "duplicate_object": editing.duplicate_object,
    "delete_objects": editing.delete_objects,
    "rename_object": editing.rename_object,
    "set_parent": editing.set_parent,
    "create_collection": editing.create_collection,
    "move_to_collection": editing.move_to_collection,
    "join_objects": editing.join_objects,
    "separate_mesh": editing.separate_mesh,
    "boolean": editing.boolean,
    "add_modifier": modifiers.add_modifier,
    "set_modifier_params": modifiers.set_modifier_params,
    "remove_modifier": modifiers.remove_modifier,
    "apply_modifier": modifiers.apply_modifier,
    "move_modifier": modifiers.move_modifier,
    "undo": undo.undo,
    "redo": undo.redo,
}

HANDLERS = {name: _fresh(fn) for name, fn in _HANDLERS.items()}
