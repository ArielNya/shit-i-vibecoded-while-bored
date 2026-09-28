from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ..bridge import GodotBridge, GodotCommandError, GodotConnectionError
from ..lsp import GDScriptLSP, LSPError


class Godot:
    """What tool modules use to reach the editor: bridge calls with MCP-friendly errors,
    plus a lazily created client for the editor's GDScript language server."""

    def __init__(self, bridge: GodotBridge):
        self.bridge = bridge
        self._lsp: GDScriptLSP | None = None

    async def call(self, method: str, /, timeout: float | None = None, **params: Any) -> Any:
        params = {key: value for key, value in params.items() if value is not None}
        try:
            return await self.bridge.call(method, params, timeout=timeout)
        except GodotConnectionError as exc:
            raise ToolError(str(exc)) from exc
        except GodotCommandError as exc:
            detail = f"\n{exc.data}" if exc.data else ""
            raise ToolError(f"Godot error: {exc}{detail}") from exc

    async def lsp(self) -> GDScriptLSP:
        """The language-server client for the connected editor's project."""
        try:
            info = await self.bridge.ensure_info()
        except GodotConnectionError as exc:
            raise ToolError(str(exc)) from exc
        lsp_info = info.get("lsp") or {}
        host = os.environ.get("GODOT_MCP_LSP_HOST") or lsp_info.get("host") or "127.0.0.1"
        port = int(os.environ.get("GODOT_MCP_LSP_PORT") or lsp_info.get("port") or 6005)
        project = info.get("project_path", "")
        current = self._lsp
        if current is None or (current.host, current.port, current.project_path) != (
            host,
            port,
            project.rstrip("/"),
        ):
            if current is not None:
                await current.close()
            self._lsp = GDScriptLSP(host, port, project)
        return self._lsp


__all__ = ["Godot", "LSPError", "ToolError"]
