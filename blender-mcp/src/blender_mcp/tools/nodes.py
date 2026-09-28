"""Geometry Nodes."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel, ConfigDict, Field

from ._common import Blender


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Unique name, used in links")
    type: str = Field(description="Node type id, e.g. GeometryNodeMeshIcoSphere")
    inputs: dict[str, Any] | None = Field(
        None,
        description="Input socket values by socket name (or 'Name#1' for the second "
        "socket with that name, or index). Objects/materials/collections by name.",
    )
    properties: dict[str, Any] | None = Field(
        None, description="Node settings (not sockets), e.g. {'data_type': 'FLOAT_VECTOR'}"
    )
    location: list[float] | None = None


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def find_node_types(
        query: Annotated[str, Field(description="Words to search, e.g. 'distribute points'")],
    ) -> dict[str, Any]:
        """Search Geometry Nodes node types by name; returns the type ids to use in
        build_geometry_nodes."""
        return await blender.call("find_node_types", query=query)

    @mcp.tool()
    async def build_geometry_nodes(
        object: str,
        ctx: Context,
        nodes: list[NodeSpec],
        links: Annotated[
            list[Annotated[list[str], Field(min_length=2, max_length=2)]],
            Field(
                description="[from, to] pairs like ['Group Input.Geometry', "
                "'Distribute.Mesh']. 'Group Input' / 'Group Output' exist already and "
                "carry the object's geometry in and out."
            ),
        ],
        group_name: str | None = None,
        replace: Annotated[
            bool, Field(description="Replace this tool's previous node setup on the object")
        ] = True,
    ) -> dict[str, Any]:
        """Build a Geometry Nodes setup on an object as a modifier. Returns every node's
        sockets (names, types, values) and the evaluated vertex/face count, so you can
        check it worked and fix links. Example (scatter spheres on a surface):
        nodes Distribute=GeometryNodeDistributePointsOnFaces {Density: 20},
        Ball=GeometryNodeMeshIcoSphere {Radius: 0.05}, Inst=GeometryNodeInstanceOnPoints,
        Join=GeometryNodeJoinGeometry; links Group Input.Geometry→Distribute.Mesh,
        Distribute.Points→Inst.Points, Ball.Mesh→Inst.Instance, Inst.Instances→Join.Geometry,
        Group Input.Geometry→Join.Geometry, Join.Geometry→Group Output.Geometry."""
        return await blender.call(
            "build_geometry_nodes", timeout=120, progress=ctx, object=object,
            nodes=[n.model_dump(exclude_none=True) for n in nodes], links=links,
            group_name=group_name, replace=replace,
        )  # fmt: skip

    @mcp.tool()
    async def get_geometry_nodes(object: str) -> dict[str, Any]:
        """Show an object's Geometry Nodes setups: nodes, socket values and links."""
        return await blender.call("get_geometry_nodes", object=object)
