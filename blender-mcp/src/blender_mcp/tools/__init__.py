"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import edit, files, inspection, look, view

MODULES = (inspection, view, edit, look, files)
