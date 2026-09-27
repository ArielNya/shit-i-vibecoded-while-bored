"""Command handlers. Each takes the request params dict and returns JSON-able data.

Handlers always run on Blender's main thread, so they may use bpy freely.
"""

from __future__ import annotations

from typing import Any

from . import materials, objects, render, scene


def ping(params: dict[str, Any]) -> dict[str, Any]:
    # Goes through the main-thread queue like every other handler, so a reply proves
    # Blender's event loop is actually draining requests.
    return {"pong": True}


HANDLERS = {
    "ping": ping,
    "get_scene_info": scene.get_scene_info,
    "list_objects": objects.list_objects,
    "get_object_info": objects.get_object_info,
    "get_mesh_data": objects.get_mesh_data,
    "list_materials": materials.list_materials,
    "get_material_info": materials.get_material_info,
    "get_viewport_screenshot": render.get_viewport_screenshot,
    "render_preview": render.render_preview,
}
