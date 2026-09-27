"""Tools that return images so the model can see the scene."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Image, MCPServer
from pydantic import Field

from ._common import Blender

RENDER_TIMEOUT = 180.0

View = Literal["current", "camera", "front", "back", "left", "right", "top", "bottom", "iso"]
Size = Annotated[int, Field(ge=16, le=2048, description="Long edge of the image in pixels")]
Target = Annotated[
    str | None, Field(description="Frame this object (and its children) instead of everything")
]


def _image_result(reply: dict[str, Any]) -> list[Any]:
    data = base64.b64decode(reply.pop("image_base64"))
    reply.pop("mime_type", None)
    return [Image(data=data, format="png"), json.dumps(reply)]


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool(structured_output=False)  # image + JSON text, not a schema
    async def get_viewport_screenshot(
        view: Annotated[
            View | None,
            Field(
                description="'current' keeps the user's view; others orbit to that angle and "
                "frame the scene (or `object`). Axis views are orthographic."
            ),
        ] = None,
        size: Size = 768,
        shading: Annotated[
            Literal["SOLID", "WIREFRAME", "MATERIAL", "RENDERED"] | None,
            Field(description="Viewport shading mode for this capture (default: as is)"),
        ] = None,
        object: Target = None,
    ) -> list[Any]:
        """Capture the Blender 3D viewport as an image, to check your work visually.
        Fast; the user's view is restored afterwards. In headless Blender this falls
        back to a quick Workbench render."""
        reply = await blender.call(
            "get_viewport_screenshot",
            timeout=RENDER_TIMEOUT,
            view=view,
            size=size,
            shading=shading,
            object=object,
        )
        return _image_result(reply)

    @mcp.tool(structured_output=False)  # image + JSON text, not a schema
    async def render_preview(
        engine: Annotated[
            Literal["workbench", "eevee", "cycles"],
            Field(
                description="workbench: fastest, shows each material's viewport display "
                "color; eevee/cycles: real node materials and lighting, slower"
            ),
        ] = "workbench",
        view: Annotated[
            View | None,
            Field(description="Default: the scene camera if there is one, else 'iso'"),
        ] = None,
        size: Size = 768,
        samples: Annotated[
            int | None, Field(ge=1, le=4096, description="eevee/cycles samples (default 16)")
        ] = None,
        object: Target = None,
    ) -> list[Any]:
        """Render the scene at low resolution and return the image. Scene render
        settings are restored afterwards. Views other than 'camera' use a temporary
        camera that auto-frames the scene (or `object`)."""
        reply = await blender.call(
            "render_preview",
            timeout=RENDER_TIMEOUT,
            engine=engine,
            view=view,
            size=size,
            samples=samples,
            object=object,
        )
        return _image_result(reply)
