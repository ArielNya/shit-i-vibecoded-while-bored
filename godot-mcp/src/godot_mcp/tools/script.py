"""Reading scripts and checking them for errors."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot, LSPError, ToolError

READ_BATCH = 50
SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def _format(diag: dict[str, Any]) -> str:
    start = (diag.get("range") or {}).get("start") or {}
    line = int(start.get("line", 0)) + 1
    col = int(start.get("character", 0)) + 1
    return f"{line}:{col} {diag.get('message', '').strip()}"


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def read_script(
        path: Annotated[str, Field(description="res:// path of a script, shader or text file")],
        start_line: Annotated[int, Field(ge=1)] = 1,
        end_line: Annotated[int, Field(ge=0, description="Last line to include; 0 = end")] = 0,
    ) -> dict[str, Any]:
        """Read a GDScript/C#/shader (or other text) file from the project, with line
        numbers ('  12| code'). Long files come in pages of up to 2000 lines."""
        return await godot.call("read_script", path=path, start_line=start_line, end_line=end_line)

    @mcp.tool()
    async def get_diagnostics(
        path: Annotated[
            str,
            Field(description="A .gd file or a folder; empty = every GDScript in the project"),
        ] = "",
        include_warnings: bool = True,
        max_files: Annotated[int, Field(ge=1, le=2000)] = 300,
    ) -> dict[str, Any]:
        """Check GDScript files for parse/type errors and warnings using the editor's own
        GDScript analyzer (the same messages the script editor shows). Positions are
        line:column, 1-based. Run this after writing or changing scripts."""
        target = path.strip() or "res://"
        if target.lower().endswith(".cs"):
            raise ToolError(
                "Diagnostics for C# come from `dotnet build`, which isn't wired up yet."
            )
        if target.lower().endswith(".gd"):
            files = [target]
        else:
            listing = await godot.call("list_script_files", path=target)
            files = listing["files"]
        truncated = len(files) > max_files
        files = files[:max_files]
        try:
            lsp = await godot.lsp()
        except LSPError as exc:
            raise ToolError(str(exc)) from exc

        problems: list[dict[str, Any]] = []
        missing: list[str] = []
        errors = warnings = 0
        checked = 0
        for i in range(0, len(files), READ_BATCH):
            batch = files[i : i + READ_BATCH]
            texts = (await godot.call("read_text_files", paths=batch))["files"]
            for res_path, text in texts.items():
                if text is None:
                    missing.append(res_path)
                    continue
                try:
                    diags = await lsp.diagnostics(res_path, text)
                except LSPError as exc:
                    raise ToolError(str(exc)) from exc
                checked += 1
                file_errors = [_format(d) for d in diags if d.get("severity", 1) == 1]
                file_warnings = [_format(d) for d in diags if d.get("severity", 1) == 2]
                errors += len(file_errors)
                warnings += len(file_warnings)
                entry: dict[str, Any] = {"path": res_path}
                if file_errors:
                    entry["errors"] = file_errors
                if include_warnings and file_warnings:
                    entry["warnings"] = file_warnings
                if len(entry) > 1:
                    problems.append(entry)

        if len(files) == 1 and missing:
            raise ToolError(f"No GDScript file at '{path}'.")
        result: dict[str, Any] = {
            "files_checked": checked,
            "error_count": errors,
            "warning_count": warnings,
            "files": problems,
        }
        if missing:
            result["not_found"] = missing
        if truncated:
            result["truncated"] = (
                f"Checked the first {max_files} files; raise max_files or pass a folder."
            )
        if not files:
            result["note"] = "No .gd files found there."
        return result
