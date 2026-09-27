"""Command handlers. Each takes the request params dict and returns JSON-able data.

Handlers always run on Blender's main thread, so they may use bpy freely.
"""

from __future__ import annotations

from typing import Any

from . import scene


def ping(params: dict[str, Any]) -> dict[str, Any]:
    # Goes through the main-thread queue like every other handler, so a reply proves
    # Blender's event loop is actually draining requests.
    return {"pong": True}


HANDLERS = {
    "ping": ping,
    "get_scene_info": scene.get_scene_info,
}
