"""--wrap-studio: run Studio's built-in MCP server as a child and serve its tools next to
ours, stepping in only where the two servers can conflict (PLAN §9).

Tool names and schemas come from the child at startup, so new or renamed Roblox tools
pass through without code changes. Argument names aren't hard-coded either: rules find
the value they need by its shape (a `game.` path, a datamodel type, an asset id)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.tools.base import Tool
from mcp_types import CallToolResult, TextContent

from . import compat, toolchain
from .tools.assets import read_manifest
from .tools.project import ROJO_PORT, find_project_file, probe

SYNC_SETTLE_S = 2.0  # Rojo pushes a saved file to Studio well within this
RECORD_WRAP = """\
local __mcpHistory = game:GetService("ChangeHistoryService")
local __mcpRecording = __mcpHistory:TryBeginRecording("MCP: execute_luau")
local __mcpResult = table.pack(pcall(function()
{code}
end))
if __mcpRecording then
	__mcpHistory:FinishRecording(__mcpRecording, if __mcpResult[1]
		then Enum.FinishRecordingOperation.Commit
		else Enum.FinishRecordingOperation.Cancel)
end
if not __mcpResult[1] then
	error(__mcpResult[2], 0)
end
return table.unpack(__mcpResult, 2, __mcpResult.n)
"""


def text(result: CallToolResult) -> str:
    return "\n".join(c.text for c in result.content if isinstance(c, TextContent))


def refusal(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=f"roblox-mcp: {message}")],
                          is_error=True)  # fmt: skip


class Guard:
    """The conflict rules. Each looks at (tool, arguments) and may rewrite the arguments,
    refuse the call, or add a note to the result."""

    def __init__(self, root: Path, studio: Studio):
        self.root = root
        self.studio = studio

    # --- helpers -----------------------------------------------------------------------

    def rojo_owned(self) -> dict[str, str]:
        """Instance path -> file or folder Rojo syncs it from: every script/model file in
        a fresh sourcemap, and every folder mapped with $path (Rojo manages what's inside,
        so a script created there in Studio is lost too)."""
        project_file = find_project_file(self.root)
        if project_file is None or toolchain.find("rojo") is None:
            return {}
        owned: dict[str, str] = {}

        def tree(node: dict, path: str) -> None:
            for name, child in node.items():
                if name.startswith("$") or not isinstance(child, dict):
                    continue
                if isinstance(child.get("$path"), str):
                    owned[f"{path}.{name}"] = child["$path"]
                tree(child, f"{path}.{name}")

        tree(json.loads(project_file.read_text(encoding="utf-8")).get("tree", {}), "game")
        out = toolchain.run("rojo", ["sourcemap", project_file.name], self.root, timeout=30)
        if out.code != 0:
            return owned

        def walk(node: dict, path: str) -> None:
            kinds = (".luau", ".lua", ".model.json", ".rbxm", ".rbxmx")
            scripts = [f for f in node.get("filePaths") or [] if f.endswith(kinds)]
            if scripts:
                owned[path] = scripts[0]
            for child in node.get("children", []):
                walk(child, f"{path}.{child['name']}")

        walk(json.loads(out.stdout), "game")
        return owned

    # --- rules -------------------------------------------------------------------------

    def multi_edit(self, args: dict) -> str | None:
        """Rojo overwrites Studio edits to scripts it syncs: point at the file instead."""
        targets = [v for v in args.values() if isinstance(v, str) and v.startswith("game.")]
        if not targets:
            return None
        synced = self.rojo_owned()
        for target in targets:
            owner = max((p for p in synced if target == p or target.startswith(p + ".")),
                        key=len, default=None)  # fmt: skip
            if owner is None:
                continue
            file = synced[owner]
            if owner == target:
                return (
                    f"{target} is synced by Rojo from {file}; edit that file (then "
                    "check_code). A Studio edit would be overwritten on the next sync."
                )
            folder = str(Path(file).parent) if Path(file).suffix else file
            return (f"{target} would be created inside {owner}, which Rojo syncs from "
                    f"{folder}; create the script as a file there instead.")  # fmt: skip
        return None

    def execute_luau(self, args: dict) -> dict:
        """Make Edit-mode changes one undoable step, unless the code already records."""
        is_edit = any(isinstance(v, str) and v.lower() == "edit" for v in args.values())
        if not is_edit:
            return args
        key = next((k for k in ("code", "script", "source", "luau", "command") if k in args),
                   None)  # fmt: skip
        if key is None or "TryBeginRecording" in args[key]:
            return args
        return {**args, key: RECORD_WRAP.format(code=args[key])}

    async def before_play(self) -> str | None:
        """Play-testing old code is the classic Rojo mistake."""
        if find_project_file(self.root) is None:
            return None
        if probe(ROJO_PORT) is None:
            return ("Rojo isn't serving this project, so Studio may run old code: start it "
                    "with sync_status action=start and connect Studio's Rojo plugin.")  # fmt: skip
        newest = max((p.stat().st_mtime for p in (self.root / "src").rglob("*")
                      if p.is_file()), default=0)  # fmt: skip
        wait = SYNC_SETTLE_S - (time.time() - newest)
        if wait > 0:
            await asyncio.sleep(wait)  # let the last file change reach Studio
        return None

    def insert_asset(self, args: dict) -> tuple[str | None, str | None]:
        manifest = {e["asset_id"]: (f, e) for f, e in read_manifest(self.root).items()}
        for value in args.values():
            try:
                asset_id = int(value)
            except (TypeError, ValueError):
                continue
            if asset_id not in manifest:
                continue
            file, entry = manifest[asset_id]
            state = entry.get("moderation")
            if state == "Rejected":
                return (f"asset {asset_id} ({file}) was rejected by moderation; replace the "
                        "file and upload_asset again."), None  # fmt: skip
            if state and state != "Approved":
                return None, (
                    f"asset {asset_id} ({file}) is still in moderation ({state}); it may not "
                    "load yet. list_uploaded_assets refresh=true re-checks."
                )
        return None, None

    async def studio_id(self, tool: str, args: dict) -> tuple[dict, str | None]:
        """Fill a missing studio_id when it's unambiguous; refuse when it isn't."""
        schema = self.studio.schemas.get(tool, {})
        if "studio_id" not in schema.get("properties", {}) or args.get("studio_id"):
            return args, None
        if "list_roblox_studios" not in self.studio.schemas:
            return args, None
        try:
            studios = json.loads(text(await self.studio.call("list_roblox_studios", {})))
        except ValueError:
            return args, None  # unknown format: let the child report the missing id
        if isinstance(studios, dict):
            studios = next((v for v in studios.values() if isinstance(v, list)), [])
        entries = [s for s in studios if isinstance(s, dict)] if isinstance(studios, list) else []

        def field(entry: dict, *names: str) -> Any:
            return next((entry[n] for n in names if n in entry), None)

        ids = [(field(e, "studio_id", "studioId", "id"), field(e, "place_id", "placeId"))
               for e in entries]  # fmt: skip
        ids = [(s, p) for s, p in ids if s is not None]
        if len(ids) == 1:
            return {**args, "studio_id": ids[0][0]}, None
        wanted = {v for v in (self.studio.place_ids) if v}
        matches = [s for s, p in ids if p is not None and str(p) in wanted]
        if len(matches) == 1:
            return {**args, "studio_id": matches[0]}, None
        if len(ids) > 1:
            listing = ", ".join(f"{s} (place {p})" for s, p in ids)
            return args, (f"several Studio windows are open ({listing}) and none matches this "
                          "project's place id: pass studio_id.")  # fmt: skip
        return args, None

    async def call(self, tool: str, args: dict) -> CallToolResult:
        notes: list[str] = []
        args, problem = await self.studio_id(tool, args)
        if problem:
            return refusal(problem)
        if tool == "multi_edit" and (problem := self.multi_edit(args)):
            return refusal(problem)
        if tool == "execute_luau":
            args = self.execute_luau(args)
        if tool == "start_stop_play" and (note := await self.before_play()):
            notes.append(note)
        if tool == "insert_asset":
            problem, note = self.insert_asset(args)
            if problem:
                return refusal(problem)
            if note:
                notes.append(note)
        result = await self.studio.call(tool, args)
        if notes:
            extra = [TextContent(type="text", text=f"roblox-mcp: {n}") for n in notes]
            result.content = [*result.content, *extra]
        return result


class Studio:
    """The child connection to Studio's built-in MCP server."""

    def __init__(self, command: list[str], place_ids: list[str]):
        self.command = command
        self.place_ids = place_ids
        self.client: Client | None = None
        self.schemas: dict[str, dict] = {}

    async def start(self, stack: AsyncExitStack) -> list[Any]:
        # the full environment: the SDK's default is a filtered subset, and Studio's
        # launcher may need more of it (LOCALAPPDATA, HOME, ...)
        params = StdioServerParameters(command=self.command[0], args=self.command[1:],
                                       env=dict(os.environ))  # fmt: skip
        self.client = await stack.enter_async_context(Client(params))
        tools = (await self.client.list_tools()).tools
        self.schemas = {t.name: t.input_schema for t in tools}
        return tools

    async def call(self, tool: str, args: dict) -> CallToolResult:
        assert self.client is not None
        return await self.client.call_tool(tool, args)


class ProxyTool(Tool):
    """A child tool: its own schema, calls forwarded through the guard as-is."""

    guard: Any = None

    async def run(self, arguments: dict[str, Any], context: Any, convert_result: bool = False):
        return await self.guard.call(self.name, arguments)


def _placeholder() -> None:
    """Stands in for the function a Tool normally wraps; ProxyTool.run never calls it."""


async def attach(mcp: MCPServer, root: Path, command: list[str], place_ids: list[str],
                 stack: AsyncExitStack) -> int:  # fmt: skip
    """Start the child and register its tools; returns how many."""
    studio = Studio(command, place_ids)
    tools = await asyncio.wait_for(studio.start(stack), timeout=30)
    guard = Guard(root, studio)
    base = Tool.from_function(_placeholder)
    base.fn_metadata.output_schema = None  # results pass through; don't advertise "null"
    manager = mcp._tool_manager
    for tool in tools:
        if manager.get_tool(tool.name):
            print(f"roblox-mcp: Studio tool {tool.name} hidden by ours", file=sys.stderr)
            continue
        manager._tools[tool.name] = ProxyTool(
            **{
                **base.__dict__,
                "name": tool.name,
                "title": tool.title,
                "description": tool.description or tool.name,
                "parameters": compat._clean(tool.input_schema),
            },  # fmt: skip
            guard=guard,
        )
    return len(tools)


def studio_command(value: str | None) -> list[str] | None:
    """--studio-mcp, or where Studio installs its server launcher."""
    import shlex

    from .tools.project import studio_mcp_path

    if value:
        return shlex.split(value)
    found = studio_mcp_path()
    if found is None:
        return None
    return ["cmd.exe", "/c", found] if found.endswith(".bat") else [found]
