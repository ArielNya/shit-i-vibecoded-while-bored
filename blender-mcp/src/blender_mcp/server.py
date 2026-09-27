"""MCP server (stdio) exposing Blender tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import __version__, tools
from .bridge import BlenderBridge, BridgeConfig
from .tools._common import Blender

INSTRUCTIONS = """\
Tools for inspecting and editing a live Blender scene. Blender must be running with the
blender-mcp add-on started. Call `ping` first if unsure whether Blender is connected, and
`get_scene_info` to see what's in the scene before changing it. Use
`get_viewport_screenshot` or `render_preview` to look at the result."""


def create_server(bridge: BlenderBridge | None = None) -> MCPServer:
    blender = Blender(bridge or BlenderBridge(BridgeConfig.from_env()))
    mcp = MCPServer("blender", instructions=INSTRUCTIONS, version=__version__)
    for module in tools.MODULES:
        module.register(mcp, blender)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
