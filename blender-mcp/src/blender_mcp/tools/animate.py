"""Keyframe animation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Blender

Value = Annotated[list[float], Field(min_length=3, max_length=3)] | float | bool | int


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def set_keyframe(
        object: str,
        frame: Annotated[float | None, Field(description="Default: the current frame")] = None,
        property: Annotated[
            str,
            Field(
                description="location, rotation (degrees), scale, or a top-level object "
                "property such as hide_render"
            ),
        ] = "location",
        value: Annotated[
            Value | None,
            Field(description="Set this value first; omit to key the current value"),
        ] = None,
        interpolation: Literal["CONSTANT", "LINEAR", "BEZIER"] | None = None,
    ) -> dict[str, Any]:
        """Insert a keyframe, optionally setting the value first. Animate by keying
        the same property at several frames, e.g. location at 1 and 48."""
        return await blender.call(
            "set_keyframe", object=object, frame=frame, property=property, value=value,
            interpolation=interpolation,
        )  # fmt: skip

    @mcp.tool()
    async def list_keyframes(object: str) -> dict[str, Any]:
        """Keyframes of an object: per channel [frame, value, interpolation]; rotation
        values in degrees."""
        return await blender.call("list_keyframes", object=object)

    @mcp.tool()
    async def clear_animation(object: str) -> dict[str, Any]:
        """Remove all keyframes from an object (values stay where they are)."""
        return await blender.call("clear_animation", object=object)

    @mcp.tool()
    async def set_frame_range(
        start: Annotated[int | None, Field(ge=0)] = None,
        end: Annotated[int | None, Field(ge=0)] = None,
        fps: Annotated[int | None, Field(ge=1, le=240)] = None,
        current: Annotated[int | None, Field(description="Jump to this frame")] = None,
    ) -> dict[str, Any]:
        """Set the scene's frame range, frame rate and/or current frame."""
        return await blender.call("set_frame_range", start=start, end=end, fps=fps, current=current)
