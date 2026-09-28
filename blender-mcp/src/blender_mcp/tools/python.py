"""execute_python: the escape hatch for anything the dedicated tools don't cover."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from ._common import Blender


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def execute_python(
        ctx: Context,
        code: Annotated[str, Field(min_length=1, max_length=100_000)],
        keep_session: Annotated[
            bool,
            Field(description="Keep variables between calls (a shared namespace)"),
        ] = False,
        reset_session: Annotated[
            bool, Field(description="Clear the shared namespace first")
        ] = False,
        timeout: Annotated[
            float, Field(ge=1, le=600, description="Seconds to wait for Blender")
        ] = 60,
    ) -> dict[str, Any]:
        """Run Python inside Blender, for things the other tools can't do. Prefer the
        dedicated tools: they validate input and give clearer errors.

        Available names: bpy, bmesh, mathutils, Vector, Matrix, Euler, Quaternion, math,
        C (bpy.context), D (bpy.data). Assign `result` to return a value; print() output
        comes back as stdout. The whole run is one undo step. Blender is blocked while
        the code runs, and a timeout does not stop it.

        Disabled unless the user enabled "Allow arbitrary Python" in the add-on
        preferences and set a token."""
        return await blender.call(
            "execute_python",
            progress=ctx,
            timeout=timeout,
            code=code,
            keep_session=keep_session,
            reset_session=reset_session,
        )
