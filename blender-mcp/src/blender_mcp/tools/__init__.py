"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import edit, inspection, view

MODULES = (inspection, view, edit)
