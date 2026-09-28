"""Tools that return images so the model can see the editor."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Image, MCPServer
from pydantic import Field

from ._common import Godot

SCREENSHOT_TIMEOUT = 30.0


KEEP_FILES = 20  # saved screenshots per folder; older ones are deleted


def image_result(reply: dict[str, Any], godot: Godot | None = None, kind: str = "shot") -> list:
    """Screenshot reply -> MCP content. GODOT_MCP_IMAGE_MODE (--image-mode):
    inline (default) an image block; file saves a PNG and returns its path, for clients
    that don't pass images to the model; both does both."""
    data = base64.b64decode(reply.pop("image_base64"))
    reply.pop("mime_type", None)
    mode = os.environ.get("GODOT_MCP_IMAGE_MODE", "inline")
    out: list[Any] = []
    if mode in ("file", "both"):
        reply["image_file"] = str(_save(data, godot, kind))
    if mode != "file":
        out.append(Image(data=data, format="png"))
    return [*out, json.dumps(reply)]


def _save(data: bytes, godot: Godot | None, kind: str) -> Path:
    """Next to the project (in .godot/, which Godot keeps out of git and exports) when
    it is on this machine, else in the temp folder."""
    project = ((godot.bridge.server_info or {}) if godot else {}).get("project_path", "")
    folder = (
        Path(project) / ".godot" / "mcp_screenshots"
        if project and Path(project).is_dir()
        else Path(tempfile.gettempdir()) / "godot-mcp-screenshots"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{time.monotonic_ns() % 10**6}.png"
    path.write_bytes(data)
    for old in sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime)[:-KEEP_FILES]:
        old.unlink(missing_ok=True)
    return path


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
        return image_result(reply, godot, "editor")
