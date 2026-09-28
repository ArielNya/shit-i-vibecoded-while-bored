"""Blender side of blender-mcp: listens on localhost and runs commands on the main thread.

bpy-dependent modules are imported inside register() so listener/protocol stay
importable (and testable) outside Blender.
"""

bl_info = {
    "name": "Blender MCP",
    "author": "ArielNya",
    "version": (0, 8, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > MCP",
    "description": "Let AI agents inspect and model in Blender over MCP",
    "category": "Interface",
}


def register():
    from . import ui

    ui.register()


def unregister():
    from . import ui

    ui.unregister()
