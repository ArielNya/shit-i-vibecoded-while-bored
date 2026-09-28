"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import (
    animate,
    edit,
    files,
    inspection,
    instances,
    look,
    mesh,
    nodes,
    python,
    rig,
    sculpt,
    view,
)

# Toolset names for BLENDER_MCP_TOOLSETS, in registration order.
TOOLSETS = {
    "inspect": inspection,
    "view": view,
    "edit": edit,
    "mesh": mesh,
    "sculpt": sculpt,
    "nodes": nodes,
    "animate": animate,
    "rig": rig,
    "look": look,
    "files": files,
    "python": python,
    "instances": instances,
}
