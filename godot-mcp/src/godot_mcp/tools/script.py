"""Reading scripts and checking them for errors."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot, LSPError, ToolError

READ_BATCH = 50
SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def _split(diags: list[dict]) -> tuple[list[str], list[str]]:
    """(errors, warnings) as 'line:col message' strings."""
    errors = [_format(d) for d in diags if d.get("severity", 1) == 1]
    return errors, [_format(d) for d in diags if d.get("severity", 1) == 2]


def _format(diag: dict[str, Any]) -> str:
    start = (diag.get("range") or {}).get("start") or {}
    line = int(start.get("line", 0)) + 1
    col = int(start.get("character", 0)) + 1
    return f"{line}:{col} {diag.get('message', '').strip()}"


def register(mcp: MCPServer, godot: Godot) -> None:
    register_editing(mcp, godot)

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
                file_errors, file_warnings = _split(diags)
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


Line = Annotated[int, Field(ge=1, description="1-based line (as read_script shows)")]
Symbol = Annotated[str, Field(description="The identifier on that line to look up")]
Column = Annotated[int, Field(ge=0, description="1-based column instead of symbol")]

SYMBOL_KINDS = {
    5: "class",
    6: "method",
    7: "property",
    10: "enum",
    12: "function",
    13: "variable",
    14: "constant",
    22: "enum_member",
    23: "struct",
    24: "signal",
}


def register_editing(mcp: MCPServer, godot: Godot) -> None:
    async def fresh_diagnostics(path: str) -> dict[str, Any]:
        """Errors/warnings for a just-written .gd file, so the model sees them at once."""
        if not path.endswith(".gd"):
            return {}
        try:
            text = (await godot.call("read_text_files", paths=[path]))["files"].get(path)
            if text is None:
                return {}
            lsp = await godot.lsp()
            diags = await lsp.diagnostics(path, text)
        except (LSPError, ToolError) as exc:
            return {"diagnostics_unavailable": str(exc)}
        errors, warnings = _split(diags)
        out: dict[str, Any] = {"errors": errors}
        if warnings:
            out["warnings"] = warnings
        return out

    @mcp.tool()
    async def write_script(
        path: Annotated[str, Field(description="res:// path (.gd, .cs, .gdshader, .json, ...)")],
        content: Annotated[str, Field(description="The complete new file content")],
        force: Annotated[
            bool, Field(description="Overwrite even if the file has unsaved edits in Godot")
        ] = False,
    ) -> dict[str, Any]:
        """Create or overwrite a script/shader/text file with the given content, reload it
        in the editor, and return its GDScript errors and warnings. For small changes to
        an existing file prefer edit_script."""
        result = await godot.call("write_script", path=path, content=content, force=force)
        result.update(await fresh_diagnostics(result["path"]))
        return result

    @mcp.tool()
    async def edit_script(
        path: Annotated[str, Field(description="res:// path of an existing file")],
        old_text: Annotated[
            str, Field(description="Exact text to replace (with its indentation; unique)")
        ],
        new_text: Annotated[str, Field(description="Replacement text")],
        replace_all: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Replace an exact snippet in a script (must match once unless replace_all), then
        reload it and return fresh GDScript errors/warnings. GDScript indents with tabs."""
        result = await godot.call(
            "edit_script",
            path=path,
            old_text=old_text,
            new_text=new_text,
            replace_all=replace_all,
            force=force,
        )
        result.update(await fresh_diagnostics(result["path"]))
        return result

    @mcp.tool()
    async def create_script(
        path: Annotated[str, Field(description="New .gd path, e.g. res://scripts/player.gd")],
        extends: Annotated[
            str, Field(description="Base: engine class, class_name or res:// script")
        ] = "Node",
        class_name: Annotated[str, Field(description="Optional global class_name")] = "",
        template: Annotated[
            str, Field(description="'default' (_ready + _process/_physics_process) or 'empty'")
        ] = "default",
        attach_to: Annotated[
            str, Field(description="Node path to attach the new script to (optional)")
        ] = "",
        scene: Annotated[str, Field(description="Scene of attach_to; empty = current")] = "",
    ) -> dict[str, Any]:
        """Create a new GDScript file from a template (Godot 4 syntax), optionally attach it
        to a node. Then fill it in with edit_script/write_script."""
        result = await godot.call(
            "create_script",
            path=path,
            extends=extends,
            class_name=class_name,
            template=template,
            attach_to=attach_to,
            scene=scene,
        )
        result.update(await fresh_diagnostics(result["path"]))
        return result

    @mcp.tool()
    async def attach_script(
        node: Annotated[str, Field(description="Node path from the scene root")],
        path: Annotated[str, Field(description="res:// path of the script")],
        scene: Annotated[str, Field(description="Scene to edit; empty = current")] = "",
    ) -> dict[str, Any]:
        """Attach a script to a node (replacing any script it has). The script must extend
        the node's type or one of its base classes."""
        return await godot.call("attach_script", node=node, path=path, scene=scene)

    @mcp.tool()
    async def detach_script(
        node: Annotated[str, Field(description="Node path from the scene root")],
        scene: Annotated[str, Field(description="Scene to edit; empty = current")] = "",
    ) -> dict[str, Any]:
        """Remove the script from a node (the file is kept)."""
        return await godot.call("detach_script", node=node, scene=scene)

    # --- navigation (GDScript language server) ---------------------------------------

    async def open_all(paths: list[str]) -> dict[str, str]:
        """Send these scripts' current text to the language server; returns path -> text."""
        texts: dict[str, str] = {}
        lsp = await godot.lsp()
        for i in range(0, len(paths), READ_BATCH):
            batch = (await godot.call("read_text_files", paths=paths[i : i + READ_BATCH]))["files"]
            for res_path, text in batch.items():
                if text is not None:
                    await lsp.open_document(res_path, text)
                    texts[res_path] = text
        return texts

    async def locations(result: Any, texts: dict[str, str]) -> list[dict[str, Any]]:
        lsp = await godot.lsp()
        items = result if isinstance(result, list) else [result] if result else []
        out = []
        for loc in items:
            uri = loc.get("uri") or loc.get("targetUri", "")
            rng = loc.get("range") or loc.get("targetSelectionRange") or {}
            start = rng.get("start", {})
            res_path = lsp.uri_to_res(uri)
            line = int(start.get("line", 0)) + 1
            entry: dict[str, Any] = {
                "path": res_path,
                "line": line,
                "column": int(start.get("character", 0)) + 1,
            }
            text = texts.get(res_path)
            if text is None and res_path.startswith("res://"):
                text = (await godot.call("read_text_files", paths=[res_path]))["files"].get(
                    res_path
                )
            if text is not None:
                lines = text.split("\n")
                if 0 < line <= len(lines):
                    entry["text"] = lines[line - 1].strip()[:200]
            out.append(entry)
        return out

    async def position(path: str, line: int, symbol: str, column: int) -> tuple[str, dict]:
        texts = await open_all([path])
        res_path = next(iter(texts), None)
        if res_path is None:
            raise ToolError(f"No GDScript file at '{path}'.")
        lines = texts[res_path].split("\n")
        if not 0 < line <= len(lines):
            raise ToolError(f"{res_path} has {len(lines)} lines; line {line} is out of range.")
        text = lines[line - 1]
        if column <= 0:
            if not symbol:
                raise ToolError("Pass `symbol` (the name on that line) or `column`.")
            idx = _find_word(text, symbol)
            if idx < 0:
                raise ToolError(f"'{symbol}' is not on line {line} of {res_path}: {text.strip()}")
            column = idx + 1
        lsp = await godot.lsp()
        return res_path, {
            "textDocument": {"uri": lsp.res_to_uri(res_path)},
            "position": {"line": line - 1, "character": column - 1},
        }

    @mcp.tool()
    async def get_definition(
        path: Annotated[str, Field(description="res:// path of a .gd file")],
        line: Line,
        symbol: Symbol = "",
        column: Column = 0,
    ) -> dict[str, Any]:
        """Where a variable, function, class or signal used in a GDScript is defined
        (file and line). Engine API has no source here: use get_class_docs for it."""
        try:
            await open_all(await _all_scripts(godot))
            _, params = await position(path, line, symbol, column)
            lsp = await godot.lsp()
            result = await lsp.request("textDocument/definition", params)
        except LSPError as exc:
            raise ToolError(str(exc)) from exc
        found = await locations(result, {})
        if not found:
            return {
                "definitions": [],
                "note": "No definition in the project (engine API? try "
                "get_class_docs), or the name isn't resolvable here.",
            }
        return {"definitions": found}

    @mcp.tool()
    async def get_references(
        path: Annotated[str, Field(description="res:// path of a .gd file")],
        line: Line,
        symbol: Symbol = "",
        column: Column = 0,
        include_declaration: bool = True,
    ) -> dict[str, Any]:
        """Every place in the project's GDScript files that uses the symbol at that
        position (e.g. before renaming a function)."""
        try:
            texts = await open_all(await _all_scripts(godot))
            _, params = await position(path, line, symbol, column)
            params["context"] = {"includeDeclaration": include_declaration}
            lsp = await godot.lsp()
            result = await lsp.request("textDocument/references", params, timeout=30.0)
        except LSPError as exc:
            raise ToolError(str(exc)) from exc
        return {"references": await locations(result, texts)}

    @mcp.tool()
    async def find_symbol(
        name: Annotated[str, Field(description="Name (or part of it) to look for")],
        path: Annotated[str, Field(description="A .gd file or folder; empty = project")] = "",
        kind: Annotated[
            str,
            Field(description="Only this kind: class, method, variable, constant, signal, enum"),
        ] = "",
    ) -> dict[str, Any]:
        """Find where functions, variables, constants, signals, enums and classes are
        declared in the project's GDScript files, with their signature and line."""
        target = path.strip() or "res://"
        paths = [target] if target.endswith(".gd") else await _all_scripts(godot, target)
        try:
            texts = await open_all(paths[:MAX_SYMBOL_FILES])
            lsp = await godot.lsp()
            wanted = name.lower()
            results: list[dict[str, Any]] = []
            for res_path in texts:
                symbols = await lsp.request(
                    "textDocument/documentSymbol",
                    {"textDocument": {"uri": lsp.res_to_uri(res_path)}},
                )
                for sym, parent in _flatten(symbols or []):
                    sym_kind = SYMBOL_KINDS.get(sym.get("kind"), str(sym.get("kind")))
                    if (
                        kind
                        and sym_kind != kind
                        and not (kind == "method" and sym_kind == "function")
                    ):
                        continue
                    if wanted not in sym.get("name", "").lower():
                        continue
                    start = (sym.get("selectionRange") or sym.get("range") or {}).get("start", {})
                    entry = {
                        "name": sym["name"],
                        "kind": sym_kind,
                        "detail": sym.get("detail", ""),
                        "path": res_path,
                        "line": int(start.get("line", 0)) + 1,
                    }
                    if parent:
                        entry["in"] = parent
                    results.append(entry)
        except LSPError as exc:
            raise ToolError(str(exc)) from exc
        results.sort(key=lambda r: (r["name"].lower() != wanted, r["path"], r["line"]))
        out: dict[str, Any] = {"results": results[:200], "files_searched": len(texts)}
        if len(paths) > MAX_SYMBOL_FILES:
            out["truncated"] = f"Searched the first {MAX_SYMBOL_FILES} files; pass a folder."
        return out


MAX_SYMBOL_FILES = 500


async def _all_scripts(godot: Godot, path: str = "res://") -> list[str]:
    return (await godot.call("list_script_files", path=path))["files"]


def _flatten(symbols: list[dict], parent: str = "", depth: int = 0):
    for sym in symbols:
        yield sym, parent
        # The file-level class's members count as top-level; deeper ones name their class.
        child_parent = "" if depth == 0 and sym.get("kind") == 5 else sym.get("name", "")
        yield from _flatten(sym.get("children") or [], child_parent, depth + 1)


def _find_word(line: str, word: str) -> int:
    import re

    m = re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", line)
    return m.start() if m else -1
