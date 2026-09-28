"""Run the game from the editor, watch it, and drive it (the runtime bridge).

The editor starts the game; the plugin's McpRuntime autoload inside the game answers
over Godot's own editor<->game debugger connection.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot
from .project import parse_value
from .view import image_result

LiveNode = Annotated[
    str,
    Field(
        description="Node path in the running game, relative to the current scene ('.' = "
        "its root) or absolute ('/root/GameState')"
    ),
]


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def run_project(
        scene: Annotated[
            str,
            Field(
                description="Empty = main scene; 'current' = the scene open in the editor; "
                "or a res:// .tscn"
            ),
        ] = "",
        display: Annotated[
            Literal["auto", "headless", "window"],
            Field(
                description="auto: headless if the editor has no display, else a window "
                "(needed for get_game_screenshot)"
            ),
        ] = "auto",
        break_on_errors: Annotated[
            bool, Field(description="Pause at script errors/breakpoints like a human debug run")
        ] = False,
        allow_unsaved: Annotated[
            bool, Field(description="Run even if the scene has unsaved edits (runs the old file)")
        ] = False,
    ) -> dict[str, Any]:
        """Run the game from the editor (like pressing Play) and wait until it's up. Stops
        a game that is already running. Script errors are logged and the game keeps
        going; read them with get_runtime_errors."""
        return await godot.call(
            "run_project",
            timeout=60,
            scene=scene,
            display=display,
            break_on_errors=break_on_errors,
            allow_unsaved=allow_unsaved,
        )

    @mcp.tool()
    async def stop_project() -> dict[str, Any]:
        """Stop the running game."""
        return await godot.call("stop_project", timeout=20)

    @mcp.tool()
    async def get_run_status() -> dict[str, Any]:
        """Whether the game is running, which scene, for how long, current frame and FPS,
        and how many errors/warnings it has logged so far."""
        return await godot.call("get_run_status")

    @mcp.tool()
    async def get_output(
        since: Annotated[
            int,
            Field(
                ge=0, description="Only entries after this cursor (next_since of the previous call)"
            ),
        ] = 0,
        levels: Annotated[
            list[str],
            Field(
                description="Only these levels: stdout, stderr, warning, error, "
                "script_error, shader_error"
            ),
        ] = [],  # noqa: B006
        limit: Annotated[int, Field(ge=1, le=2000)] = 200,
    ) -> dict[str, Any]:
        """The game's printed output, warnings and errors (current run, or the last one
        after it stopped), oldest first, with file:line for errors. Pass next_since back
        as `since` to get only what's new."""
        return await godot.call("get_output", since=since, levels=levels, limit=limit)

    @mcp.tool()
    async def get_runtime_errors(
        since: Annotated[int, Field(ge=0, description="Cursor from a previous call")] = 0,
        include_warnings: bool = True,
    ) -> dict[str, Any]:
        """Errors (script errors, push_error, engine errors) and warnings the running game
        logged, grouped with a count, each with file:line and a GDScript backtrace."""
        return await godot.call(
            "get_runtime_errors", since=since, include_warnings=include_warnings
        )

    @mcp.tool(structured_output=False)  # image + JSON text
    async def get_game_screenshot(
        size: Annotated[int, Field(ge=64, le=2048, description="Max long edge in pixels")] = 768,
    ) -> list[Any]:
        """Capture what the running game shows right now. Needs the game to run with a
        window (not headless)."""
        reply = await godot.call("get_game_screenshot", timeout=40, size=size)
        return image_result(reply, godot, "game")

    @mcp.tool()
    async def get_live_tree(
        node: LiveNode = "",
        max_depth: Annotated[int, Field(ge=0, le=64)] = 8,
        max_nodes: Annotated[int, Field(ge=1, le=2000)] = 300,
    ) -> dict[str, Any]:
        """The running game's node tree (like the editor's Remote tab): paths, types,
        global positions, visibility, groups; plus the autoloads."""
        return await godot.call(
            "get_live_tree", node=node, max_depth=max_depth, max_nodes=max_nodes
        )

    @mcp.tool()
    async def get_live_properties(
        node: LiveNode,
        filter: Annotated[str, Field(description="Only properties containing this")] = "",
        include_defaults: bool = False,
    ) -> dict[str, Any]:
        """Current property values of a node in the running game (including script
        variables), e.g. a player's position, velocity or health."""
        return await godot.call(
            "get_live_properties", node=node, filter=filter, include_defaults=include_defaults
        )

    @mcp.tool()
    async def set_live_properties(
        node: LiveNode,
        properties: Annotated[
            dict[str, Any],
            Field(description="Property name -> value (same formats as set_node_properties)"),
        ],
    ) -> dict[str, Any]:
        """Change properties of a node in the running game, e.g. to test a speed value.
        Not saved: edit the scene or script to make it permanent."""
        return await godot.call("set_live_properties", node=node, properties=properties)

    @mcp.tool()
    async def send_input(
        events: Annotated[
            list[dict[str, Any]],
            Field(
                description='Inputs: {"action": "jump"} (input map action, optional '
                '"strength"), {"key": "Space"}, {"mouse_button": "left", "position": [x, y]}, '
                '{"mouse_motion": [x, y]}'
            ),
        ],
        mode: Annotated[
            Literal["tap", "press", "release"],
            Field(
                description="tap: press, hold for `frames`, release. press/release: change "
                "state and return (hold keys while you wait_for)"
            ),
        ] = "tap",
        frames: Annotated[
            int, Field(ge=1, le=3600, description="Physics frames to hold (60 = 1 s)")
        ] = 1,
    ) -> dict[str, Any]:
        """Send input to the running game as if a player pressed it; returns after the
        input is released (tap). Use it to play-test: e.g. hold move_right for 60 frames,
        then check the player's position."""
        return await godot.call(
            "send_input", timeout=60 + frames / 30, events=events, mode=mode, frames=frames
        )

    @mcp.tool()
    async def wait_for(
        until: Annotated[
            Literal["frames", "seconds", "node_exists", "node_gone", "property", "signal"],
            Field(description="What to wait for"),
        ],
        frames: Annotated[int, Field(ge=0, le=36000)] = 0,
        seconds: Annotated[float, Field(ge=0, le=600)] = 0,
        node: Annotated[str, Field(description="Node path for node_*/property/signal")] = "",
        property: Annotated[
            str, Field(description="Property (or component like 'position:x') for property")
        ] = "",
        op: Annotated[
            Literal["==", "!=", "<", "<=", ">", ">="], Field(description="Comparison")
        ] = "==",
        value: Annotated[
            str, Field(description="Value to compare with: JSON or a literal like 'Vector2(1, 2)'")
        ] = "",
        signal: Annotated[str, Field(description="Signal name for until=signal")] = "",
        timeout: Annotated[float, Field(ge=0.1, le=600)] = 10,
    ) -> dict[str, Any]:
        """Let the game run until something happens (checked every physics frame) or the
        timeout passes; returns whether it was met. Examples: until=property node=Player
        property=position:x op=> value=300; until=signal node=Door signal=opened."""
        params: dict[str, Any] = {"timeout": timeout}
        if until == "frames":
            params["frames"] = frames or 1
        elif until == "seconds":
            params["seconds"] = seconds
        elif until in ("node_exists", "node_gone"):
            params[until] = node
        elif until == "property":
            params["property"] = {
                "node": node,
                "property": property,
                "op": op,
                "value": parse_value(value),
            }
        else:
            params["signal"] = {"node": node, "signal": signal}
        wait_seconds = max(timeout, seconds)
        return await godot.call_with("wait_for", params, timeout=wait_seconds + 30)

    @mcp.tool()
    async def get_performance() -> dict[str, Any]:
        """Performance of the running game: FPS, process/physics time per frame, memory,
        object/node/orphan counts, draw calls, active physics bodies."""
        return await godot.call("get_performance")
