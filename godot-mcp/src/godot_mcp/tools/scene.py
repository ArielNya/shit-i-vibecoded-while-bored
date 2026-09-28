"""Scene inspection tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot

Scene = Annotated[
    str,
    Field(
        description="res:// path of a .tscn to read from disk; empty = the scene open in the editor"
    ),
]


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def get_scene_tree(
        scene: Scene = "",
        node: Annotated[
            str, Field(description="Only this subtree (path from the scene root, e.g. 'Player')")
        ] = "",
        max_depth: Annotated[int, Field(ge=0, le=64)] = 8,
        max_nodes: Annotated[int, Field(ge=1, le=2000)] = 300,
        include_internal: Annotated[
            bool, Field(description="Also list nodes inside instanced sub-scenes")
        ] = False,
    ) -> dict[str, Any]:
        """The node tree of a scene as a flat list in tree order: path (relative to the
        root, which is '.'), type, attached script, instanced scene, groups, hidden flag.
        Like the editor's Scene dock."""
        return await godot.call(
            "get_scene_tree",
            scene=scene,
            node=node,
            max_depth=max_depth,
            max_nodes=max_nodes,
            include_internal=include_internal,
        )

    @mcp.tool()
    async def get_node_properties(
        node: Annotated[str, Field(description="Node path from the scene root; '.' = root")],
        scene: Scene = "",
        filter: Annotated[str, Field(description="Only properties whose name contains this")] = "",
        include_defaults: Annotated[
            bool, Field(description="Also list properties still at their default value")
        ] = False,
    ) -> dict[str, Any]:
        """A node's Inspector properties with types and values. By default only values
        that differ from the default (what the Inspector shows as changed). Engine types
        come as GDScript literals, resources as {_type, class, path}."""
        return await godot.call(
            "get_node_properties",
            node=node,
            scene=scene,
            filter=filter,
            include_defaults=include_defaults,
        )
