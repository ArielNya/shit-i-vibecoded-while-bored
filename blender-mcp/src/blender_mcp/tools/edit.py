"""Tools that change the scene. Each call is one undo step ("MCP: ...") in Blender."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from ._common import Blender

EDIT_TIMEOUT = 120.0

Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
Name = Annotated[str, Field(description="Exact object name")]
Names = Annotated[list[str], Field(min_length=1, description="Exact object names")]
Primitive = Literal[
    "cube", "plane", "grid", "circle", "uv_sphere", "ico_sphere", "cylinder", "cone",
    "torus", "monkey", "empty", "camera", "light",
]  # fmt: skip


def register(mcp: MCPServer, blender: Blender) -> None:
    async def edit(method: str, ctx: Context | None = None, **params: Any) -> Any:
        return await blender.call(method, timeout=EDIT_TIMEOUT, progress=ctx, **params)

    @mcp.tool()
    async def create_primitive(
        type: Primitive,
        name: str | None = None,
        location: Vec3 | None = None,
        rotation: Annotated[Vec3 | None, Field(description="Euler XYZ, degrees")] = None,
        scale: Vec3 | float | None = None,
        collection: Annotated[
            str | None, Field(description="Default: the active collection")
        ] = None,
        size: Annotated[
            float | None, Field(gt=0, description="cube/plane/grid/monkey width (default 2)")
        ] = None,
        radius: Annotated[
            float | None, Field(gt=0, description="sphere/cylinder/cone/circle (default 1)")
        ] = None,
        depth: Annotated[
            float | None, Field(gt=0, description="cylinder/cone height (default 2)")
        ] = None,
        radius_top: Annotated[float | None, Field(ge=0, description="cone tip radius")] = None,
        segments: Annotated[
            int | None, Field(ge=3, le=512, description="around the axis (default 32)")
        ] = None,
        rings: Annotated[int | None, Field(ge=3, le=512, description="uv_sphere/torus")] = None,
        subdivisions: Annotated[int | None, Field(ge=1, le=7, description="ico_sphere")] = None,
        major_radius: Annotated[float | None, Field(gt=0, description="torus")] = None,
        minor_radius: Annotated[float | None, Field(gt=0, description="torus")] = None,
        x_segments: Annotated[int | None, Field(ge=1, le=512, description="grid")] = None,
        y_segments: Annotated[int | None, Field(ge=1, le=512, description="grid")] = None,
        fill: Annotated[bool | None, Field(description="circle: fill with an n-gon")] = None,
        shade_smooth: bool | None = None,
        light_type: Literal["POINT", "SUN", "SPOT", "AREA"] | None = None,
        energy: Annotated[
            float | None, Field(ge=0, description="light watts (sun: strength)")
        ] = None,
        color: Annotated[Vec3 | None, Field(description="light RGB 0-1")] = None,
        lens: Annotated[float | None, Field(gt=0, description="camera focal length mm")] = None,
        set_active_camera: Annotated[
            bool | None, Field(description="camera: make it the scene camera")
        ] = None,
    ) -> dict[str, Any]:
        """Add a mesh primitive, empty, camera or light. Returns the new object's actual
        name (Blender appends .001 etc. on clashes) — use that name afterwards."""
        return await edit(
            "create_primitive",
            type=type, name=name, location=location, rotation=rotation, scale=scale,
            collection=collection, size=size, radius=radius, depth=depth,
            radius_top=radius_top, segments=segments, rings=rings, subdivisions=subdivisions,
            major_radius=major_radius, minor_radius=minor_radius, x_segments=x_segments,
            y_segments=y_segments, fill=fill, shade_smooth=shade_smooth, light_type=light_type,
            energy=energy, color=color, lens=lens, set_active_camera=set_active_camera,
        )  # fmt: skip

    @mcp.tool()
    async def transform_object(
        name: Name,
        location: Vec3 | None = None,
        rotation: Annotated[Vec3 | None, Field(description="Euler XYZ, degrees")] = None,
        scale: Vec3 | float | None = None,
        dimensions: Annotated[
            Vec3 | None, Field(description="Set scale so the bounding box has this size")
        ] = None,
        mode: Annotated[
            Literal["set", "delta"],
            Field(description="delta: add to location/rotation, multiply scale"),
        ] = "set",
    ) -> dict[str, Any]:
        """Move, rotate and/or scale an object."""
        return await edit(
            "transform_object", name=name, location=location, rotation=rotation,
            scale=scale, dimensions=dimensions, mode=mode,
        )  # fmt: skip

    @mcp.tool()
    async def apply_transform(
        name: Name, location: bool = False, rotation: bool = True, scale: bool = True
    ) -> dict[str, Any]:
        """Bake the object's rotation/scale (and optionally location) into its data,
        resetting them to identity. Do this before bevels/booleans on scaled objects."""
        return await edit(
            "apply_transform", name=name, location=location, rotation=rotation, scale=scale
        )

    @mcp.tool()
    async def duplicate_object(
        name: Name,
        new_name: str | None = None,
        offset: Annotated[Vec3 | None, Field(description="Added to the copy's location")] = None,
        linked: Annotated[bool, Field(description="Share mesh data (instance)")] = False,
    ) -> dict[str, Any]:
        """Copy an object (with its modifiers and materials)."""
        return await edit(
            "duplicate_object", name=name, new_name=new_name, offset=offset, linked=linked
        )

    @mcp.tool()
    async def delete_objects(names: Names, delete_children: bool = False) -> dict[str, Any]:
        """Delete objects. Children are kept (unparented) unless delete_children."""
        return await edit("delete_objects", names=names, delete_children=delete_children)

    @mcp.tool()
    async def rename_object(
        name: Name,
        new_name: str,
        rename_data: Annotated[bool, Field(description="Also rename its mesh/data")] = False,
    ) -> dict[str, Any]:
        """Rename an object. Returns the name Blender actually used."""
        return await edit("rename_object", name=name, new_name=new_name, rename_data=rename_data)

    @mcp.tool()
    async def set_parent(
        name: Name,
        parent: Annotated[str | None, Field(description="New parent; omit to unparent")] = None,
        keep_transform: bool = True,
    ) -> dict[str, Any]:
        """Parent an object to another (or clear its parent), keeping its world
        position by default."""
        return await edit("set_parent", name=name, parent=parent, keep_transform=keep_transform)

    @mcp.tool()
    async def create_collection(
        name: str,
        parent: Annotated[str | None, Field(description="Default: the scene collection")] = None,
    ) -> dict[str, Any]:
        """Create a collection for organizing objects."""
        return await edit("create_collection", name=name, parent=parent)

    @mcp.tool()
    async def move_to_collection(names: Names, collection: str) -> dict[str, Any]:
        """Move objects into a collection (removing them from their other collections)."""
        return await edit("move_to_collection", names=names, collection=collection)

    @mcp.tool()
    async def join_objects(
        names: Annotated[list[str], Field(min_length=2)],
        into: Annotated[
            str | None, Field(description="Object that survives (default: first name)")
        ] = None,
    ) -> dict[str, Any]:
        """Join meshes into one object."""
        return await edit("join_objects", names=names, into=into)

    @mcp.tool()
    async def separate_mesh(
        name: Name, mode: Literal["loose", "material"] = "loose"
    ) -> dict[str, Any]:
        """Split a mesh into one object per disconnected part (loose) or per material."""
        return await edit("separate_mesh", name=name, mode=mode)

    @mcp.tool()
    async def boolean(
        ctx: Context,
        target: Annotated[str, Field(description="Object to modify")],
        cutter: Annotated[str, Field(description="Object used as the tool")],
        operation: Literal["DIFFERENCE", "UNION", "INTERSECT"] = "DIFFERENCE",
        solver: Literal["EXACT", "FAST"] = "EXACT",
        apply: Annotated[bool, Field(description="Apply now; false keeps a live modifier")] = True,
        cutter_action: Literal["hide", "delete", "keep"] = "hide",
    ) -> dict[str, Any]:
        """Boolean between two meshes, e.g. cut a hole with DIFFERENCE."""
        return await edit(
            "boolean", ctx=ctx, target=target, cutter=cutter, operation=operation, solver=solver,
            apply=apply, cutter_action=cutter_action,
        )  # fmt: skip

    @mcp.tool()
    async def add_modifier(
        object: Name,
        type: Annotated[
            str,
            Field(
                description="Blender modifier type, e.g. SUBSURF, BEVEL, MIRROR, ARRAY, "
                "SOLIDIFY, BOOLEAN, REMESH, DECIMATE, DISPLACE, WELD, TRIANGULATE, SCREW"
            ),
        ],
        params: Annotated[
            dict[str, Any] | None,
            Field(
                description="Modifier properties by Blender name, e.g. {'levels': 2} for "
                "SUBSURF, {'width': 0.05, 'segments': 3} for BEVEL. Angles in degrees; "
                "object/collection properties take names. Unknown keys error with the "
                "list of valid ones."
            ),
        ] = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Add a modifier to the end of an object's stack. Returns all its settings."""
        return await edit("add_modifier", object=object, type=type, params=params, name=name)

    @mcp.tool()
    async def set_modifier_params(
        object: Name,
        modifier: Annotated[str, Field(description="Modifier name")],
        params: Annotated[dict[str, Any], Field(description="Same format as add_modifier params")],
    ) -> dict[str, Any]:
        """Change settings of an existing modifier."""
        return await edit("set_modifier_params", object=object, modifier=modifier, params=params)

    @mcp.tool()
    async def remove_modifier(object: Name, modifier: str) -> dict[str, Any]:
        """Remove a modifier without applying it."""
        return await edit("remove_modifier", object=object, modifier=modifier)

    @mcp.tool()
    async def apply_modifier(ctx: Context, object: Name, modifier: str) -> dict[str, Any]:
        """Apply a modifier, baking its result into the mesh."""
        return await edit("apply_modifier", ctx=ctx, object=object, modifier=modifier)

    @mcp.tool()
    async def move_modifier(
        object: Name,
        modifier: str,
        index: Annotated[int, Field(ge=0, description="New position, 0 = first")],
    ) -> dict[str, Any]:
        """Reorder a modifier in the stack."""
        return await edit("move_modifier", object=object, modifier=modifier, index=index)

    @mcp.tool()
    async def undo(steps: Annotated[int, Field(ge=1, le=50)] = 1) -> dict[str, Any]:
        """Undo the last change(s) in Blender — including ones the user made."""
        return await edit("undo", steps=steps)

    @mcp.tool()
    async def redo(steps: Annotated[int, Field(ge=1, le=50)] = 1) -> dict[str, Any]:
        """Redo changes undone with `undo`."""
        return await edit("redo", steps=steps)
