from __future__ import annotations

from collections import Counter
from typing import Any

import bpy

MAX_LISTED = 100


def _collection_tree(collection: bpy.types.Collection) -> dict[str, Any]:
    return {
        "name": collection.name,
        "objects": len(collection.objects),
        "children": [_collection_tree(child) for child in collection.children],
    }


def get_scene_info(params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    objects = list(scene.objects)
    active = view_layer.objects.active
    selected = [obj.name for obj in objects if obj.select_get(view_layer=view_layer)]
    units = scene.unit_settings
    render = scene.render

    info: dict[str, Any] = {
        "scene": scene.name,
        "file": bpy.data.filepath or None,
        "is_dirty": bpy.data.is_dirty,
        "frame": {
            "current": scene.frame_current,
            "start": scene.frame_start,
            "end": scene.frame_end,
        },
        "units": {
            "system": units.system,
            "length_unit": units.length_unit,
            "scale_length": units.scale_length,
        },
        "render": {
            "engine": render.engine,
            "resolution": [render.resolution_x, render.resolution_y],
            "fps": render.fps,
        },
        "camera": scene.camera.name if scene.camera else None,
        "object_count": len(objects),
        "objects_by_type": dict(Counter(obj.type for obj in objects)),
        "active_object": active.name if active else None,
        "selected_objects": selected[:MAX_LISTED],
        "collections": _collection_tree(scene.collection),
    }
    if len(selected) > MAX_LISTED:
        info["selected_objects_truncated"] = len(selected) - MAX_LISTED
    return info
