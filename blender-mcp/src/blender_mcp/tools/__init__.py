"""MCP tool definitions, grouped by area. Each module exposes register(mcp, blender)."""

from . import edit, files, inspection, look, mesh, view

MODULES = (inspection, view, edit, mesh, look, files)
