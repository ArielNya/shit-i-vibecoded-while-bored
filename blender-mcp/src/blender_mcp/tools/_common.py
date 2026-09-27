from __future__ import annotations

from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ..bridge import BlenderBridge, BlenderCommandError, BlenderConnectionError


class Blender:
    """What tool modules use to reach Blender: bridge calls with MCP-friendly errors."""

    def __init__(self, bridge: BlenderBridge):
        self.bridge = bridge

    async def call(self, method: str, timeout: float | None = None, **params: Any) -> Any:
        params = {key: value for key, value in params.items() if value is not None}
        try:
            return await self.bridge.call(method, params, timeout=timeout)
        except BlenderConnectionError as exc:
            raise ToolError(str(exc)) from exc
        except BlenderCommandError as exc:
            detail = f"\n{exc.data}" if exc.data else ""
            raise ToolError(f"Blender error: {exc}{detail}") from exc
