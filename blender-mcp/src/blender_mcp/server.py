"""MCP server (stdio) exposing Blender tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__
from .bridge import BlenderBridge, BlenderCommandError, BlenderConnectionError, BridgeConfig

INSTRUCTIONS = """\
Tools for inspecting and editing a live Blender scene. Blender must be running with the
blender-mcp add-on started. Call `ping` first if unsure whether Blender is connected, and
`get_scene_info` to see what's in the scene before changing it."""


def create_server(bridge: BlenderBridge | None = None) -> MCPServer:
    bridge = bridge or BlenderBridge(BridgeConfig.from_env())
    mcp = MCPServer("blender", instructions=INSTRUCTIONS, version=__version__)

    async def call(method: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return await bridge.call(method, params)
        except BlenderConnectionError as exc:
            raise ToolError(str(exc)) from exc
        except BlenderCommandError as exc:
            detail = f"\n{exc.data}" if exc.data else ""
            raise ToolError(f"Blender error: {exc}{detail}") from exc

    @mcp.tool()
    async def ping() -> dict[str, Any]:
        """Check the connection to Blender. Returns Blender and add-on versions."""
        reply = await call("ping")
        return {
            "connected": True,
            "address": bridge.address,
            "server_version": __version__,
            **(bridge.server_info or {}),
            **reply,
        }

    @mcp.tool()
    async def get_scene_info() -> dict[str, Any]:
        """Summarize the current Blender scene: name, frame range, units, render engine,
        object counts by type, active and selected objects, and the collection tree."""
        return await call("get_scene_info")

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
