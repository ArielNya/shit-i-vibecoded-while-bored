"""Organic-shape helpers: remesh, smooth, noise."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from ._common import Blender
from .mesh import SELECT_HELP, Select, _spec

TIMEOUT = 300.0


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def remesh(
        name: str,
        ctx: Context,
        voxel_size: Annotated[
            float, Field(gt=0, description="Smaller = more detail and more faces")
        ] = 0.05,
        smooth_shade: bool = True,
    ) -> dict[str, Any]:
        """Rebuild a mesh as an even voxel surface. Fuses overlapping parts into one
        shell and gives uniform topology for smoothing/noise. Refuses sizes that would
        create millions of faces."""
        return await blender.call(
            "remesh", timeout=TIMEOUT, progress=ctx, name=name, voxel_size=voxel_size,
            smooth_shade=smooth_shade,
        )  # fmt: skip

    @mcp.tool(description="Relax vertex positions (like the Smooth brush)." + SELECT_HELP)
    async def smooth_vertices(
        name: str,
        ctx: Context,
        select: Select | None = None,
        factor: Annotated[float, Field(gt=0, le=1)] = 0.5,
        iterations: Annotated[int, Field(ge=1, le=200)] = 5,
    ) -> dict[str, Any]:
        return await blender.call(
            "smooth_vertices", timeout=TIMEOUT, progress=ctx, name=name,
            select=_spec(select), factor=factor, iterations=iterations,
        )  # fmt: skip

    @mcp.tool(
        description="Displace vertices along their normals with fractal noise — rocks, "
        "terrain, bark, lumpy clay. Needs enough vertices (subdivide or remesh first); "
        "`seed` gives a different pattern." + SELECT_HELP
    )
    async def add_noise(
        name: str,
        ctx: Context,
        strength: Annotated[float, Field(description="Max displacement in units")] = 0.2,
        scale: Annotated[float, Field(gt=0, description="Higher = smaller bumps")] = 1.0,
        detail: Annotated[int, Field(ge=1, le=8, description="Noise octaves")] = 4,
        seed: int = 0,
        select: Select | None = None,
    ) -> dict[str, Any]:
        return await blender.call(
            "add_noise", timeout=TIMEOUT, progress=ctx, name=name, strength=strength,
            scale=scale, detail=detail, seed=seed, select=_spec(select),
        )  # fmt: skip
