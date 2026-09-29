"""The escape hatch: run GDScript in the editor or the running game. Off unless the user
allows it in Godot (MCP dock checkbox), and only with token auth."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot, ToolError


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def execute_gdscript(
        code: Annotated[
            str,
            Field(
                description="GDScript statements (a function body). Variables: scene (edited "
                "scene root / game's current scene), tree (SceneTree), editor "
                "(EditorInterface, editor only). May await; `return` a value to get it back."
            ),
        ],
        target: Annotated[
            Literal["editor", "game"], Field(description="Run in the editor or the running game")
        ] = "editor",
        timeout: Annotated[int, Field(ge=1, le=600, description="Seconds (game only)")] = 30,
    ) -> dict[str, Any]:
        """Run GDScript code for things the other tools can't do. Returns the printed
        output and the returned value; errors come with lines of `code`. Editor changes
        made this way are not undoable, and an endless loop freezes Godot. Prefer the
        structured tools. Off unless the user enables it in Godot's MCP dock."""
        result = await godot.call_with(
            "execute_gdscript",
            {"code": code, "target": target, "timeout": timeout},
            timeout=timeout + 10,
        )
        if not result.get("ok"):
            detail = {k: result[k] for k in ("stage", "errors", "output") if result.get(k)}
            raise ToolError("The code failed:\n" + json.dumps(detail, indent=1))
        return {"result": result.get("result"), "output": result.get("output", [])}
