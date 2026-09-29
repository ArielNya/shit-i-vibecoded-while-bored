"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import (
    animate,
    edit,
    files,
    gameready,
    inspection,
    instances,
    look,
    mesh,
    nodes,
    python,
    rig,
    roblox,
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
    "gameready": gameready,
    "look": look,
    "files": files,
    "python": python,
    "instances": instances,
    "roblox": roblox,
}
