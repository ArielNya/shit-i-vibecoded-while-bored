"""Read-only tools: scene, objects, meshes, materials."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import __version__
from ._common import Blender

ObjectType = Literal[
    "MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME",
    "GPENCIL", "GREASEPENCIL", "ARMATURE", "LATTICE", "EMPTY", "LIGHT", "LIGHT_PROBE",
    "CAMERA", "SPEAKER",
]  # fmt: skip


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def ping() -> dict[str, Any]:
        """Check the connection to Blender. Returns Blender and add-on versions."""
        reply = await blender.call("ping")
        return {
            "connected": True,
            "address": blender.bridge.address,
            "server_version": __version__,
            **(blender.bridge.server_info or {}),
            **reply,
        }

    @mcp.tool()
    async def get_scene_info() -> dict[str, Any]:
        """Summarize the current Blender scene: name, frame range, units, render engine,
        object counts by type, active and selected objects, and the collection tree."""
        return await blender.call("get_scene_info")

    @mcp.tool()
    async def list_objects(
        type: Annotated[ObjectType | None, Field(description="Only objects of this type")] = None,
        collection: Annotated[
            str | None, Field(description="Only objects in this collection (recursive)")
        ] = None,
        name_contains: Annotated[
            str | None, Field(description="Case-insensitive name filter")
        ] = None,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        """List objects in the scene with type, parent, collections, location,
        rotation (degrees), scale, dimensions and visibility. Paginated: if the result
        has `next_offset`, call again with that offset for more."""
        return await blender.call(
            "list_objects",
            type=type,
            collection=collection,
            name_contains=name_contains,
            offset=offset,
            limit=limit,
        )

    @mcp.tool()
    async def get_object_info(
        name: Annotated[str, Field(description="Exact object name")],
    ) -> dict[str, Any]:
        """Full detail for one object: transforms, world bounds, modifiers with their
        settings, material slots, constraints, children, custom properties, plus
        type-specific data (mesh topology stats incl. manifold check and post-modifier
        counts, camera lens, light energy, ...)."""
        return await blender.call("get_object_info", name=name)

    @mcp.tool()
    async def get_mesh_data(
        name: Annotated[str, Field(description="Exact name of a MESH object")],
        space: Annotated[
            Literal["local", "world"], Field(description="Coordinate space for vertices")
        ] = "local",
        evaluated: Annotated[
            bool, Field(description="Use the mesh with modifiers applied")
        ] = False,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=5000)] = 500,
    ) -> dict[str, Any]:
        """Raw vertex positions and faces (as vertex-index lists) of a mesh. The same
        offset/limit window applies to both lists; check `next_offset` in each for more.
        Prefer get_object_info for summaries — use this only for small meshes or when
        exact geometry matters."""
        return await blender.call(
            "get_mesh_data",
            name=name,
            space=space,
            evaluated=evaluated,
            offset=offset,
            limit=limit,
        )

    @mcp.tool()
    async def list_materials() -> dict[str, Any]:
        """List all materials with the objects using them and their main
        Principled BSDF values (base color, metallic, roughness)."""
        return await blender.call("list_materials")

    @mcp.tool()
    async def get_material_info(
        name: Annotated[str, Field(description="Exact material name")],
    ) -> dict[str, Any]:
        """Detail for one material: every Principled BSDF input (value, or which node
        feeds it), plus the node list and links of its node tree."""
        return await blender.call("get_material_info", name=name)
