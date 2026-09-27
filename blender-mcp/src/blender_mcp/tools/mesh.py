"""Mesh-level editing: extrude, inset, bevel, cuts, element transforms, raw meshes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict, Field

from ._common import Blender

EDIT_TIMEOUT = 120.0

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]


class PositionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: Literal["x", "y", "z"]
    min: float | None = None
    max: float | None = None


class Select(BaseModel):
    """Which mesh elements to act on. All given criteria must match (AND)."""

    model_config = ConfigDict(extra="forbid")
    all: bool | None = Field(None, description="Every element")
    indices: list[int] | None = Field(None, description="Explicit element indices")
    normal: Vec3 | None = Field(
        None, description="Facing this direction, e.g. [0,0,1] = up (faces/verts/edges)"
    )
    max_angle: float | None = Field(
        None, description="Degrees of tolerance for `normal` (default 30)"
    )
    position: PositionFilter | list[PositionFilter] | None = Field(
        None, description="Element centers within min/max along an axis"
    )
    material: int | str | None = Field(None, description="Faces using this slot index or name")
    boundary: bool | None = Field(None, description="On (true) / not on (false) an open edge")
    sharp_angle: float | None = Field(
        None, description="Edges whose faces meet at >= this many degrees"
    )
    space: Literal["local", "world"] | None = Field(
        None, description="Coordinates for normal/position (default local)"
    )


def _spec(select: Select | None) -> dict[str, Any] | None:
    return None if select is None else select.model_dump(exclude_none=True)


ElementType = Literal["faces", "edges", "verts"]
Name = Annotated[str, Field(description="Exact name of a MESH object")]

SELECT_HELP = (
    " `select` picks elements statelessly, e.g. {'normal': [0,0,1], 'max_angle': 10} "
    "(faces pointing up), {'position': {'axis': 'z', 'min': 0.9}}, {'indices': [3, 4]}, "
    "{'all': true}. Returned indices stay valid until the next topology change."
)


def register(mcp: MCPServer, blender: Blender) -> None:
    async def edit(method: str, **params: Any) -> Any:
        return await blender.call(method, timeout=EDIT_TIMEOUT, **params)

    @mcp.tool(
        description="Preview which faces/edges/verts a selection matches: indices, and "
        "centers/normals when there are few." + SELECT_HELP
    )
    async def select_elements(
        name: Name, select: Select, type: ElementType = "faces"
    ) -> dict[str, Any]:
        return await blender.call("select_elements", name=name, select=_spec(select), type=type)

    @mcp.tool(
        description="Extrude faces along their average normal (region) or each along its "
        "own normal (individual). Negative distance pushes inward. Returns the new cap "
        "faces' indices, ready to extrude/inset again." + SELECT_HELP
    )
    async def extrude(
        name: Name,
        select: Select,
        distance: float = 1.0,
        mode: Literal["region", "individual"] = "region",
        direction: Annotated[
            Vec3 | None, Field(description="region mode: extrude along this instead")
        ] = None,
    ) -> dict[str, Any]:
        return await edit(
            "extrude", name=name, select=_spec(select), distance=distance, mode=mode,
            direction=direction,
        )  # fmt: skip

    @mcp.tool(
        description="Inset faces: make a smaller face inside each (or the region), with "
        "an optional depth (negative = recess). Returns the inner faces." + SELECT_HELP
    )
    async def inset(
        name: Name,
        select: Select,
        thickness: Annotated[float, Field(gt=0)] = 0.1,
        depth: float = 0.0,
        individual: bool = False,
    ) -> dict[str, Any]:
        return await edit(
            "inset", name=name, select=_spec(select), thickness=thickness, depth=depth,
            individual=individual,
        )  # fmt: skip

    @mcp.tool(
        description="Bevel edges (or the edges of selected faces/verts) with a width and "
        "segments. Tip: {'sharp_angle': 30} selects hard edges." + SELECT_HELP
    )
    async def bevel(
        name: Name,
        select: Select,
        width: Annotated[float, Field(gt=0)] = 0.1,
        segments: Annotated[int, Field(ge=1, le=100)] = 1,
        profile: Annotated[float, Field(ge=0, le=1, description="0.5 = round")] = 0.5,
        type: ElementType = "edges",
    ) -> dict[str, Any]:
        return await edit(
            "bevel", name=name, select=_spec(select), width=width, segments=segments,
            profile=profile, type=type,
        )  # fmt: skip

    @mcp.tool(description="Subdivide the edges of selected faces (default: all)." + SELECT_HELP)
    async def subdivide(
        name: Name,
        select: Select | None = None,
        cuts: Annotated[int, Field(ge=1, le=100)] = 1,
        smooth: Annotated[float, Field(ge=0, le=1)] = 0.0,
        type: ElementType = "faces",
    ) -> dict[str, Any]:
        return await edit(
            "subdivide", name=name, select=_spec(select), cuts=cuts, smooth=smooth, type=type
        )

    @mcp.tool(
        description="Loop cut: add edge loops across the strip of quads that crosses the "
        "first selected edge (e.g. pick a vertical edge to cut horizontally)." + SELECT_HELP
    )
    async def loop_cut(
        name: Name, select: Select, cuts: Annotated[int, Field(ge=1, le=100)] = 1
    ) -> dict[str, Any]:
        return await edit("loop_cut", name=name, select=_spec(select), cuts=cuts)

    @mcp.tool()
    async def bisect(
        name: Name,
        point: Vec3 = [0.0, 0.0, 0.0],  # noqa: B006 - pydantic copies defaults
        normal: Vec3 = [0.0, 0.0, 1.0],  # noqa: B006
        keep: Annotated[
            Literal["both", "above", "below"],
            Field(description="above = the side the normal points to"),
        ] = "both",
        fill: Annotated[bool, Field(description="Cap the cut when discarding a side")] = False,
        space: Literal["local", "world"] = "local",
    ) -> dict[str, Any]:
        """Cut the mesh with a plane: add an edge loop along it, or throw one side away
        (e.g. keep='above' with normal [1,0,0] keeps the +X half for mirroring)."""
        return await edit(
            "bisect", name=name, point=point, normal=normal, keep=keep, fill=fill, space=space
        )

    @mcp.tool(description="Delete mesh elements." + SELECT_HELP)
    async def delete_elements(
        name: Name,
        select: Select,
        type: Annotated[
            Literal["verts", "edges", "faces", "only_faces"],
            Field(description="only_faces keeps the edges/verts (leaves a hole)"),
        ] = "faces",
    ) -> dict[str, Any]:
        return await edit("delete_elements", name=name, select=_spec(select), type=type)

    @mcp.tool()
    async def merge_by_distance(
        name: Name, distance: Annotated[float, Field(ge=0)] = 0.0001
    ) -> dict[str, Any]:
        """Weld vertices closer than `distance` (fixes seams after joins/imports)."""
        return await edit("merge_by_distance", name=name, distance=distance)

    @mcp.tool()
    async def recalc_normals(name: Name, inside: bool = False) -> dict[str, Any]:
        """Make face normals consistent (pointing outside, or inside)."""
        return await edit("recalc_normals", name=name, inside=inside)

    @mcp.tool()
    async def shade(
        name: Name,
        smooth: bool = True,
        auto_smooth_angle: Annotated[
            float | None,
            Field(ge=0, le=180, description="Keep edges sharper than this hard (degrees)"),
        ] = None,
    ) -> dict[str, Any]:
        """Smooth or flat shading; with auto_smooth_angle, smooth but keep hard edges."""
        return await edit("shade", name=name, smooth=smooth, auto_smooth_angle=auto_smooth_angle)

    @mcp.tool(
        description="Move/rotate/scale selected elements' vertices (local space) about a "
        "pivot — e.g. scale the top faces by 0.5 to taper, or translate them up. Order: "
        "scale, rotate, translate." + SELECT_HELP
    )
    async def transform_elements(
        name: Name,
        select: Select,
        translate: Vec3 | None = None,
        rotation: Annotated[Vec3 | None, Field(description="Euler XYZ degrees")] = None,
        scale: Vec3 | float | None = None,
        pivot: Annotated[
            Literal["median", "bounds_center", "origin"] | Vec3 | None,
            Field(description="Default: median of the selected vertices"),
        ] = None,
        type: ElementType = "faces",
    ) -> dict[str, Any]:
        return await edit(
            "transform_elements", name=name, select=_spec(select), translate=translate,
            rotation=rotation, scale=scale, pivot=pivot, type=type,
        )  # fmt: skip

    @mcp.tool()
    async def create_mesh_from_data(
        vertices: Annotated[list[Vec3], Field(min_length=1)],
        faces: Annotated[
            list[list[int]] | None,
            Field(description="Vertex index lists, counter-clockwise seen from outside"),
        ] = None,
        edges: list[list[int]] | None = None,
        name: str | None = None,
        location: Vec3 | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        """Build a new mesh object from raw vertices and faces (for shapes no primitive
        covers). Invalid geometry is repaired and reported."""
        return await edit(
            "create_mesh_from_data", vertices=vertices, faces=faces, edges=edges, name=name,
            location=location, collection=collection,
        )  # fmt: skip
