"""Scene editing: scenes, nodes, properties, signals, groups, undo/redo.

Every change is one undoable editor action ("MCP: <tool>"). Tools act on the scene open
in the editor; passing `scene` opens (or switches to) that scene first.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot

Scene = Annotated[
    str,
    Field(description="res:// path of the scene to edit (opened if needed); empty = current"),
]
NodePath = Annotated[str, Field(description="Node path from the scene root; '.' = root")]
Properties = Annotated[
    dict[str, Any],
    Field(
        description="Property name -> value. Engine types as GDScript literals "
        "('Vector2(10, 20)', 'Color(1, 0, 0, 1)', '#ff0000'), vectors also as [x, y]; enums "
        "by name ('Floating') or number; resources as 'res://...' or new ones as "
        '{"_type": "Resource", "class": "RectangleShape2D", "properties": {"size": '
        '"Vector2(32, 48)"}}; NodePaths as strings.'
    ),
]


def register(mcp: MCPServer, godot: Godot) -> None:
    # --- scenes ---------------------------------------------------------------------

    @mcp.tool()
    async def open_scene(
        path: Annotated[str, Field(description="res:// path of a .tscn")],
    ) -> dict[str, Any]:
        """Open a scene in the editor (or switch to its tab) so editing tools act on it."""
        return await godot.call("open_scene", path=path)

    @mcp.tool()
    async def new_scene(
        path: Annotated[str, Field(description="Where to save it, e.g. res://scenes/level.tscn")],
        root_type: Annotated[
            str,
            Field(
                description="Root node type: Node2D, Node3D, Control, CharacterBody2D, a "
                "project class_name, ..."
            ),
        ] = "Node2D",
        root_name: Annotated[str, Field(description="Default: from the file name")] = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Create a new scene file with a single root node, and open it in the editor."""
        return await godot.call(
            "new_scene", path=path, root_type=root_type, root_name=root_name, overwrite=overwrite
        )

    @mcp.tool()
    async def save_scene(
        scene: Scene = "",
        path: Annotated[str, Field(description="Save as this path instead (save as)")] = "",
        overwrite: Annotated[bool, Field(description="Allow replacing another file")] = False,
    ) -> dict[str, Any]:
        """Save the edited scene to its file (or to `path`). Edits are not written to disk
        until the scene is saved."""
        return await godot.call("save_scene", scene=scene, path=path, overwrite=overwrite)

    @mcp.tool()
    async def close_scene(
        scene: Scene = "",
        discard_changes: Annotated[
            bool, Field(description="Close even with unsaved changes (they are lost)")
        ] = False,
    ) -> dict[str, Any]:
        """Close a scene tab in the editor. Refuses when there are unsaved changes unless
        discard_changes is true."""
        return await godot.call("close_scene", scene=scene, discard_changes=discard_changes)

    # --- nodes ----------------------------------------------------------------------

    @mcp.tool()
    async def add_node(
        parent: Annotated[str, Field(description="Parent node path; '.' = scene root")] = ".",
        type: Annotated[
            str, Field(description="Node type: engine class or project class_name")
        ] = "",
        instance: Annotated[
            str, Field(description="Instead of `type`: a .tscn to instance, e.g. res://player.tscn")
        ] = "",
        name: Annotated[str, Field(description="Node name (default: from the type)")] = "",
        properties: Properties = {},  # noqa: B006
        index: Annotated[int, Field(ge=-1, description="Child position; -1 = last")] = -1,
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Add a node (by type) or an instance of another scene under `parent`, optionally
        setting properties. Returns its actual path (Godot renames on name clashes)."""
        return await godot.call(
            "add_node",
            parent=parent,
            type=type,
            instance=instance,
            name=name,
            properties=properties,
            index=index,
            scene=scene,
        )

    @mcp.tool()
    async def remove_node(node: NodePath, scene: Scene = "") -> dict[str, Any]:
        """Delete a node and its children from the scene."""
        return await godot.call("remove_node", node=node, scene=scene)

    @mcp.tool()
    async def rename_node(
        node: NodePath,
        new_name: Annotated[str, Field(description="New name (unique among siblings)")],
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Rename a node. NodePaths that scripts use to find it are not updated."""
        return await godot.call("rename_node", node=node, new_name=new_name, scene=scene)

    @mcp.tool()
    async def move_node(
        node: NodePath,
        new_parent: Annotated[str, Field(description="New parent path; empty = same")] = "",
        index: Annotated[int, Field(ge=-1, description="Position among siblings; -1 = last")] = -1,
        keep_global_transform: bool = True,
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Reparent a node and/or change its order among its siblings (draw order in 2D)."""
        return await godot.call(
            "move_node",
            node=node,
            new_parent=new_parent,
            index=index,
            keep_global_transform=keep_global_transform,
            scene=scene,
        )

    @mcp.tool()
    async def duplicate_node(
        node: NodePath,
        name: Annotated[str, Field(description="Name for the copy")] = "",
        parent: Annotated[str, Field(description="Put the copy here; empty = same parent")] = "",
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Copy a node with its children, scripts, groups and signal connections."""
        return await godot.call("duplicate_node", node=node, name=name, parent=parent, scene=scene)

    @mcp.tool()
    async def set_node_properties(
        node: NodePath, properties: Properties, scene: Scene = ""
    ) -> dict[str, Any]:
        """Set one or more Inspector properties of a node (one undo step). All values are
        checked first; if any is invalid nothing changes. Returns the resulting values."""
        return await godot.call(
            "set_node_properties", node=node, properties=properties, scene=scene
        )

    # --- signals & groups -------------------------------------------------------------

    @mcp.tool()
    async def list_signals(
        node: NodePath,
        filter: Annotated[str, Field(description="Only signals containing this")] = "",
        scene: Scene = "",
    ) -> dict[str, Any]:
        """A node's signals (with argument types) and the connections saved in the scene,
        outgoing and incoming."""
        return await godot.call("list_signals", node=node, filter=filter, scene=scene)

    @mcp.tool()
    async def connect_signal(
        node: Annotated[str, Field(description="Node that emits the signal")],
        signal: Annotated[str, Field(description="Signal name, e.g. body_entered")],
        target: Annotated[str, Field(description="Node whose method is called")],
        method: Annotated[str, Field(description="Method on the target, e.g. _on_body_entered")],
        deferred: bool = False,
        one_shot: bool = False,
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Connect a signal to a method (saved in the scene, like the editor's Node dock).
        Warns if the target's script doesn't have the method yet."""
        return await godot.call(
            "connect_signal",
            node=node,
            signal=signal,
            target=target,
            method=method,
            deferred=deferred,
            one_shot=one_shot,
            scene=scene,
        )

    @mcp.tool()
    async def disconnect_signal(
        node: str, signal: str, target: str, method: str, scene: Scene = ""
    ) -> dict[str, Any]:
        """Remove a saved signal connection."""
        return await godot.call(
            "disconnect_signal", node=node, signal=signal, target=target, method=method, scene=scene
        )

    @mcp.tool()
    async def set_groups(
        node: NodePath,
        add: list[str] = [],  # noqa: B006
        remove: list[str] = [],  # noqa: B006
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Add the node to groups and/or remove it from groups (saved in the scene)."""
        return await godot.call("set_groups", node=node, add=add, remove=remove, scene=scene)

    @mcp.tool()
    async def save_branch_as_scene(
        node: NodePath,
        path: Annotated[str, Field(description="New .tscn path for the branch")],
        overwrite: bool = False,
        scene: Scene = "",
    ) -> dict[str, Any]:
        """Save a node and its children as a new scene and replace them with an instance
        of it (the editor's 'Save Branch as Scene')."""
        return await godot.call(
            "save_branch_as_scene", node=node, path=path, overwrite=overwrite, scene=scene
        )

    # --- history --------------------------------------------------------------------

    @mcp.tool()
    async def undo(steps: Annotated[int, Field(ge=1, le=50)] = 1) -> dict[str, Any]:
        """Undo the most recent change(s) made through MCP. Stops rather than undoing
        anything a person did in the editor since."""
        return await godot.call("undo", steps=steps)

    @mcp.tool()
    async def redo(steps: Annotated[int, Field(ge=1, le=50)] = 1) -> dict[str, Any]:
        """Redo MCP changes that were undone with `undo`."""
        return await godot.call("redo", steps=steps)
