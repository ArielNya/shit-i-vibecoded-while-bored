"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import edit, files, inspection, look, mesh, view

# Toolset names for BLENDER_MCP_TOOLSETS, in registration order.
TOOLSETS = {
    "inspect": inspection,
    "view": view,
    "edit": edit,
    "mesh": mesh,
    "look": look,
    "files": files,
}
