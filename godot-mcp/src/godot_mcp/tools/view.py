"""Tools that return images so the model can see the editor."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Image, MCPServer
from pydantic import Field

from ._common import Godot

SCREENSHOT_TIMEOUT = 30.0


def image_result(reply: dict[str, Any]) -> list[Any]:
    data = base64.b64decode(reply.pop("image_base64"))
    reply.pop("mime_type", None)
    return [Image(data=data, format="png"), json.dumps(reply)]


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool(structured_output=False)  # image + JSON text, not a schema
    async def get_editor_screenshot(
        view: Annotated[
            Literal["auto", "2d", "3d", "editor"],
            Field(
                description="auto picks 2d/3d from the edited scene's root; editor captures "
                "the whole editor window"
            ),
        ] = "auto",
        size: Annotated[
            int, Field(ge=64, le=2048, description="Maximum long edge of the image in pixels")
        ] = 768,
    ) -> list[Any]:
        """Capture the editor's 2D or 3D viewport (or the whole editor window) as an image,
        to check a scene visually. Switches the editor to that main screen. Needs an
        editor with a window (not --headless)."""
        reply = await godot.call(
            "get_editor_screenshot", timeout=SCREENSHOT_TIMEOUT, view=view, size=size
        )
        return image_result(reply)
