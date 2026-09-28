"""MCP tool definitions, grouped by area. Each module exposes register(mcp, godot)."""

from . import docs, edit, project, scene, script, view

# Toolset names for GODOT_MCP_TOOLSETS, in registration order.
TOOLSETS = {
    "project": project,
    "scene": scene,
    "edit": edit,
    "script": script,
    "docs": docs,
    "view": view,
}
