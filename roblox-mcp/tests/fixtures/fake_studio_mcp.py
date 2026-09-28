"""A stand-in for Studio's built-in MCP server (tool names and required studio_id as
documented in creator-docs studio/mcp.md). Every tool echoes what it received as JSON, so
tests can see exactly what the wrapper forwarded. FAKE_STUDIOS sets the studio list."""

import json
import os
from typing import Any

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Roblox_Studio")


def echo(tool: str, **args: Any) -> str:
    return json.dumps({"tool": tool, "args": args})


@mcp.tool()
def list_roblox_studios() -> str:
    """Lists connected Studio instances."""
    default = [{"studio_id": "s1", "name": "Game", "place_id": 111}]
    return json.dumps(json.loads(os.environ.get("FAKE_STUDIOS", "null")) or default)


@mcp.tool()
def script_read(studio_id: str, path: str) -> str:
    """Reads a script."""
    source = ("--!strict\nlocal Damage = {}\n\nfunction Damage.apply(health: number, "
              "amount: number): number\n\treturn math.max(0, health - amount)\nend\n\n"
              "return Damage\n")  # fmt: skip
    return json.dumps({"tool": "script_read", "args": {"studio_id": studio_id, "path": path},
                       "source": source})  # fmt: skip


@mcp.tool()
def multi_edit(studio_id: str, path: str, edits: list[dict], datamodel_type: str) -> str:
    """Applies edits to a script."""
    return echo("multi_edit", studio_id=studio_id, path=path, edits=edits,
                datamodel_type=datamodel_type)  # fmt: skip


@mcp.tool()
def execute_luau(studio_id: str, code: str, datamodel_type: str) -> str:
    """Runs Luau in Studio."""
    return echo("execute_luau", studio_id=studio_id, code=code, datamodel_type=datamodel_type)


@mcp.tool()
def start_stop_play(studio_id: str, mode: str) -> str:
    """Starts or stops playtesting."""
    return echo("start_stop_play", studio_id=studio_id, mode=mode)


@mcp.tool()
def insert_asset(studio_id: str, asset_id: int) -> str:
    """Inserts an asset by id."""
    return echo("insert_asset", studio_id=studio_id, asset_id=asset_id)


if __name__ == "__main__":
    mcp.run()
