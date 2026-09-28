"""Project-level tools: connection check, overview, files, search, settings, input map."""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import __version__
from ._common import Godot

EVENT_HELP = (
    'Event objects: {"type":"key","key":"W"} (key names like Space, Enter, Left, F1; '
    'optional "ctrl"/"shift"/"alt"/"meta": true, "physical": false for keycode), '
    '{"type":"mouse_button","button":"left"}, {"type":"joypad_button","button":"a"}, '
    '{"type":"joypad_motion","axis":"left_x","direction":-1}.'
)


def parse_value(text: str) -> Any:
    """Tool values arrive as strings (keeps schemas simple for every client): JSON when it
    parses, otherwise the text itself (plain strings, GDScript literals)."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def ping() -> dict[str, Any]:
        """Check the connection to the Godot editor. Returns Godot, plugin and server
        versions and the project path."""
        reply = await godot.call("ping")
        return {
            "connected": True,
            "address": godot.bridge.address,
            "server_version": __version__,
            **(godot.bridge.server_info or {}),
            **reply,
        }

    @mcp.tool()
    async def get_project_info() -> dict[str, Any]:
        """Overview of the open Godot project: name, Godot version, main scene, renderer,
        window size, autoloads, input actions, enabled plugins, C# or not, file counts by
        kind, and editor state (edited/open scenes, selected nodes). Start here."""
        return await godot.call("get_project_info")

    @mcp.tool()
    async def list_files(
        path: Annotated[str, Field(description="Folder to list, e.g. res:// or res://scenes")] = (
            "res://"
        ),
        type: Annotated[
            str,
            Field(
                description="Filter: a kind (scene, script, shader, texture, audio, font, "
                "resource, other) or a class name like PackedScene or Texture2D"
            ),
        ] = "",
        recursive: bool = True,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=1000)] = 200,
    ) -> dict[str, Any]:
        """List project files the editor knows about, with their resource type (and
        class_name for scripts). Paginated: if `next_offset` is present, call again with it.
        Non-resource files (e.g. .md) aren't listed; use search_files for text."""
        return await godot.call(
            "list_files", path=path, type=type, recursive=recursive, offset=offset, limit=limit
        )

    @mcp.tool()
    async def search_files(
        query: Annotated[str, Field(description="Text (or regex) to find")],
        path: Annotated[str, Field(description="Folder or file to search")] = "res://",
        regex: bool = False,
        case_sensitive: bool = False,
        extensions: Annotated[
            list[str],
            Field(description="Only these extensions, e.g. ['gd', 'tscn']. Default: text files"),
        ] = [],  # noqa: B006 - pydantic copies defaults
        max_results: Annotated[int, Field(ge=1, le=1000)] = 100,
    ) -> dict[str, Any]:
        """Search the text of project files (scripts, scenes, resources, shaders, configs)
        and return matching lines with path and line number. Skips hidden folders and
        folders containing a .gdignore."""
        return await godot.call(
            "search_files",
            query=query,
            path=path,
            regex=regex,
            case_sensitive=case_sensitive,
            extensions=[e.lstrip(".").lower() for e in extensions],
            max_results=max_results,
        )

    @mcp.tool()
    async def get_project_settings(
        prefix: Annotated[
            str, Field(description="Only settings starting with this, e.g. 'display/window/'")
        ] = "",
        changed_only: Annotated[
            bool,
            Field(description="Only settings that differ from the engine default"),
        ] = True,
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        """Read project settings (project.godot) with their types and values. Use a prefix
        and changed_only=false to see all settings in a section with their defaults."""
        return await godot.call(
            "get_project_settings",
            prefix=prefix,
            changed_only=changed_only,
            offset=offset,
            limit=limit,
        )

    @mcp.tool()
    async def set_project_setting(
        name: Annotated[
            str, Field(description="Full setting path, e.g. display/window/size/viewport_width")
        ],
        value: Annotated[
            str,
            Field(
                description="New value: JSON ('1280', 'true', '\"text\"'), plain text, or a "
                "GDScript literal ('Vector2(1, 2)', 'Color(1, 0, 0, 1)'); 'null' resets to "
                "the default. For autoload/<Name>: a res:// script or scene path, '' removes it."
            ),
        ],
    ) -> dict[str, Any]:
        """Change one project setting and save project.godot (one undoable editor action).
        Limited to game settings (application/config, application/run, display, physics,
        rendering, audio, gui, layer_names, autoload, ...). Input actions: edit_input_map."""
        return await godot.call(
            "set_project_setting", name=name, value=parse_value(value), value_text=value
        )

    @mcp.tool()
    async def get_input_map(include_builtin: bool = False) -> dict[str, Any]:
        """The project's input actions with their events (keys, mouse and joypad buttons,
        axes) and deadzones. Built-in ui_* actions are hidden unless include_builtin."""
        return await godot.call("get_input_map", include_builtin=include_builtin)

    @mcp.tool()
    async def edit_input_map(
        action: Annotated[str, Field(description="Action name, e.g. 'jump' or 'move_left'")],
        add_events: Annotated[
            list[dict[str, Any]], Field(description="Events to add. " + EVENT_HELP)
        ] = [],  # noqa: B006
        remove_events: Annotated[
            list[dict[str, Any]], Field(description="Events to remove (same format)")
        ] = [],  # noqa: B006
        clear_events: bool = False,
        deadzone: Annotated[
            float, Field(ge=-1, le=1, description="New deadzone (0-1); -1 keeps it")
        ] = -1,
        remove_action: Annotated[bool, Field(description="Delete the whole action")] = False,
    ) -> dict[str, Any]:
        """Create or change an input action (creates it if missing) and save
        project.godot as one undoable editor action. Returns the action's events."""
        return await godot.call(
            "edit_input_map",
            action=action,
            add_events=add_events,
            remove_events=remove_events,
            clear_events=clear_events,
            deadzone=deadzone,
            remove_action=remove_action,
        )
