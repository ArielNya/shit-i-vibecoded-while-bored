"""Game-ready output: UV seams and unwrapping, baking high-poly detail, validation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from ._common import Blender
from .mesh import SELECT_HELP, Select, _spec

BAKE_TIMEOUT = 600.0


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool(
        description="Mark (or clear) UV seams on edges — where the UV layout is cut before "
        "unwrap(method='seams'). Hide them where they won't be seen: inner arms/legs, under "
        "the hair line, around hands and feet, down the back. Tip: {'sharp_angle': 60} for "
        "hard-surface borders. type='faces' marks the border edges of each selected face."
        + SELECT_HELP
    )
    async def mark_seams(
        name: str,
        select: Select,
        clear: bool = False,
        type: Literal["edges", "faces"] = "edges",
    ) -> dict[str, Any]:
        return await blender.call(
            "mark_seams", name=name, select=_spec(select), clear=clear, type=type
        )

    @mcp.tool()
    async def uv_unwrap(
        ctx: Context,
        name: str,
        method: Annotated[
            Literal["smart", "seams", "cube"],
            Field(
                description="smart: automatic islands by angle (props, quick results). seams: "
                "unwrap along marked seams (characters; fewer, cleaner islands). cube: box "
                "projection, islands overlap (tiling materials only)"
            ),
        ] = "smart",
        select: Annotated[
            Select | None, Field(description="Faces to unwrap (default: all)")
        ] = None,
        angle_limit: Annotated[float, Field(gt=0, le=89, description="smart only")] = 66.0,
        island_margin: Annotated[float, Field(ge=0, le=0.2)] = 0.02,
        cube_size: Annotated[float, Field(gt=0, description="cube only")] = 1.0,
    ) -> dict[str, Any]:
        """Create UVs so the mesh can take textures and bakes. Reports islands, coverage
        of the 0-1 square (0.6-0.8 is well packed; >1 means overlaps), faces outside it,
        and seams."""
        return await blender.call(
            "uv_unwrap", progress=ctx, name=name, method=method, select=_spec(select),
            angle_limit=angle_limit, island_margin=island_margin, cube_size=cube_size,
        )  # fmt: skip

    @mcp.tool()
    async def get_uv_info(name: str) -> dict[str, Any]:
        """UV islands, 0-1 coverage, overlap and faces outside 0-1, and seam count."""
        return await blender.call("get_uv_info", name=name)

    @mcp.tool()
    async def bake_maps(
        ctx: Context,
        low: Annotated[str, Field(description="The game mesh (needs UVs, see uv_unwrap)")],
        high: Annotated[
            list[str] | None,
            Field(description="Detailed meshes overlapping it, to bake from (normal needs it)"),
        ] = None,
        maps: Annotated[
            list[Literal["normal", "ao", "color", "roughness"]], Field(min_length=1)
        ] = ["normal"],  # noqa: B006 - pydantic copies defaults
        size: Annotated[int, Field(ge=16, le=8192, description="Pixels, square")] = 1024,
        cage_extrusion: Annotated[
            float,
            Field(
                ge=0,
                description="How far rays start outside the low mesh; about the largest gap "
                "between low and high (too small: holes, too big: bleeding)",
            ),
        ] = 0.02,
        max_ray_distance: Annotated[float, Field(ge=0, description="0 = unlimited")] = 0.0,
        margin: Annotated[int, Field(ge=0, le=64, description="Pixels bled past islands")] = 8,
        samples: Annotated[int, Field(ge=1, le=4096)] = 16,
        folder: Annotated[str, Field(description="Workspace folder for the PNGs")] = "bakes",
        wire: Annotated[
            bool, Field(description="Hook normal/color/roughness into the low material")
        ] = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Bake detail from high-poly meshes onto the low-poly one with Cycles, save PNGs
        (<folder>/<low>_<map>.png) and plug them into the low mesh's material. The classic
        game pipeline: sculpt/subdivide a high version, keep a light low version, bake."""
        return await blender.call(
            "bake_maps", timeout=BAKE_TIMEOUT, progress=ctx, low=low, high=high, maps=maps,
            size=size, cage_extrusion=cage_extrusion, max_ray_distance=max_ray_distance,
            margin=margin, samples=samples, folder=folder, wire=wire, overwrite=overwrite,
        )  # fmt: skip

    @mcp.tool()
    async def check_game_ready(
        name: str,
        kind: Annotated[
            Literal["character", "prop", "part"],
            Field(
                description="character: also feet on z=0, centred on x=0, X symmetry; holes, "
                "n-gons and hidden joined faces fail. prop: those are warnings. part: a "
                "piece of a character that isn't the body (eyes, hat, weapon): no "
                "placement or symmetry checks, but skinning is checked"
            ),
        ] = "character",
        max_triangles: Annotated[int | None, Field(ge=1, description="Budget")] = None,
        max_influences: Annotated[int, Field(ge=1, le=8)] = 4,
        symmetric: Annotated[bool, Field(description="Expect X symmetry")] = True,
        expect_rig: Annotated[bool, Field(description="Fail if not skinned")] = False,
    ) -> dict[str, Any]:
        """One-call validation for games/animation: applied transforms, placement,
        n-gons, holes, loose/doubled vertices, inverted normals, triangle budget, UVs,
        material count, and (if skinned) unweighted vertices, influence count and bone
        sides. Problems come with world positions to aim a selection at. Returns ok,
        fails, warnings and key stats — run it instead of many separate inspections."""
        return await blender.call(
            "check_game_ready", name=name, kind=kind, max_triangles=max_triangles,
            max_influences=max_influences, symmetric=symmetric, expect_rig=expect_rig,
        )  # fmt: skip
