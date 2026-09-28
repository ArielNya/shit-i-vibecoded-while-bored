"""Code quality on the project's Luau files: type checking + lints (luau-lsp, optionally
selene) and formatting (StyLua)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import toolchain
from .project import find_project_file, inside

MAX_PROBLEMS = 200
# luau-lsp --formatter=plain: `path [instance path]:line:col-endcol: (W0) Code: message`;
# type errors carry an absolute path plus the instance path, lints a relative one.
PLAIN = re.compile(r"^(?P<path>.+?)(?: \[[^\]]*\])?:(?P<line>\d+):(?P<col>\d+)(?:-\d+)?: "
                   r"\(\w\d+\) (?P<code>\w+): (?P<message>.*)$")  # fmt: skip
ERROR_CODES = {"TypeError", "SyntaxError"}


def targets(root: Path, paths: str) -> list[str]:
    """Explicit comma-separated paths, else every folder the Rojo project syncs, else
    the root."""
    if paths.strip():
        return [str(inside(root, p.strip()).relative_to(root)) for p in paths.split(",")]
    project_file = find_project_file(root)
    found: list[str] = []
    if project_file:

        def walk(node: dict) -> None:
            for key, value in node.items():
                if key == "$path" and isinstance(value, str) and (root / value).exists():
                    found.append(value)
                elif isinstance(value, dict):
                    walk(value)

        walk(json.loads(project_file.read_text(encoding="utf-8")).get("tree", {}))
    return found or ["."]


def relative(root: Path, path: str) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(root)) if p.is_absolute() else path
    except ValueError:
        return path


def luau_lsp(root: Path, files: list[str]) -> tuple[list[dict], list[str]]:
    args = [
        "analyze",
        "--formatter=plain",
        "--flag:LuauSolverV2=true",  # Roblox's current type solver
        f"--definitions=@roblox={toolchain.definitions_path()}",
    ]
    notes = []
    project_file = find_project_file(root)
    if project_file:
        sourcemap = toolchain.run("rojo", ["sourcemap", project_file.name, "-o",
                                           "sourcemap.json"], root)  # fmt: skip
        if sourcemap.code == 0:
            args.append("--sourcemap=sourcemap.json")
        else:
            notes.append("rojo sourcemap failed, so requires between scripts weren't "
                         f"resolved: {sourcemap.stderr.strip()[-300:]}")  # fmt: skip
    result = toolchain.run("luau-lsp", [*args, *files], root, timeout=300)
    problems = []
    for line in result.stdout.splitlines():
        if m := PLAIN.match(line):
            problems.append({
                "file": relative(root, m["path"]),
                "line": int(m["line"]),
                "col": int(m["col"]),
                "severity": "error" if m["code"] in ERROR_CODES else "warning",
                "code": m["code"],
                "message": m["message"],
            })  # fmt: skip
        elif problems and line.startswith("  "):  # continuation of a multi-line message
            problems[-1]["message"] += "\n" + line.strip()
    if result.code != 0 and not problems:
        notes.append(f"luau-lsp exited with {result.code}: {result.stderr.strip()[-500:]}")
    return problems, notes


def selene(root: Path, files: list[str]) -> tuple[list[dict], list[str]]:
    """Only for projects that chose selene (a selene.toml exists)."""
    if not (root / "selene.toml").is_file() or toolchain.find("selene") is None:
        return [], []
    result = toolchain.run("selene", ["--display-style=json2", "--no-summary", *files], root)
    problems = []
    for line in result.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "Diagnostic":
            continue
        label = d.get("primary_label", {})
        span = label.get("span", {})
        problems.append({
            "file": relative(root, label.get("filename", "")),
            "line": span.get("start_line", 0) + 1,
            "col": span.get("start_column", 0) + 1,
            "severity": "error" if d.get("severity") == "Error" else "warning",
            "code": f"selene::{d.get('code')}",
            "message": d.get("message", ""),
        })  # fmt: skip
    notes = []
    if result.code != 0 and not problems:
        notes.append(f"selene failed: {(result.stderr or result.stdout).strip()[-300:]}")
    return problems, notes


def check(root: Path, paths: str) -> dict[str, Any]:
    files = targets(root, paths)
    problems, notes = luau_lsp(root, files)
    more, more_notes = selene(root, files)
    problems += more
    problems.sort(key=lambda p: (p["severity"] != "error", p["file"], p["line"], p["col"]))
    out: dict[str, Any] = {
        "checked": files,
        "errors": sum(p["severity"] == "error" for p in problems),
        "warnings": sum(p["severity"] == "warning" for p in problems),
        "problems": [
            f"{p['file']}:{p['line']}:{p['col']} {p['severity']} {p['code']}: {p['message']}"
            for p in problems[:MAX_PROBLEMS]
        ],
    }
    if len(problems) > MAX_PROBLEMS:
        out["truncated"] = f"showing {MAX_PROBLEMS} of {len(problems)}; pass paths to narrow"
    if notes + more_notes:
        out["notes"] = notes + more_notes
    return out


def format_files(root: Path, paths: str, check_only: bool) -> dict[str, Any]:
    files = targets(root, paths)
    result = toolchain.run("stylua", ["--check", "--output-format=json", *files], root)
    unformatted = []
    for line in result.stdout.splitlines():
        try:
            unformatted.append(relative(root, json.loads(line)["file"]))
        except (ValueError, KeyError):
            continue
    if result.code not in (0, 1) or (result.code == 1 and not unformatted):
        raise RuntimeError(f"stylua failed: {(result.stderr or result.stdout).strip()[-500:]}")
    if check_only or not unformatted:
        return {"checked": files, "unformatted": unformatted}
    result = toolchain.run("stylua", unformatted, root)
    if result.code != 0:
        raise RuntimeError(f"stylua failed: {(result.stderr or result.stdout).strip()[-500:]}")
    return {"checked": files, "formatted": unformatted}


PATHS = Field(description='Comma-separated files or folders in the project (default: '
              'every folder the Rojo project syncs)')  # fmt: skip


def register(mcp: MCPServer, root: Path) -> None:
    @mcp.tool()
    def check_code(paths: Annotated[str, PATHS] = "") -> dict[str, Any]:
        """Type-check and lint the project's Luau files the way Studio will run them:
        luau-lsp with Roblox's types (Studio 0.740 API, the new type solver, requires
        resolved through the Rojo sourcemap), plus selene when the project has a
        selene.toml. Returns file:line:col problems, errors first. Run after every
        code change."""
        return check(root, paths)

    @mcp.tool()
    def format_code(
        paths: Annotated[str, PATHS] = "",
        check_only: Annotated[bool, Field(description="Only list unformatted files")] = False,
    ) -> dict[str, Any]:
        """Format Luau files with StyLua (the project's stylua.toml if any). Returns the
        files it changed, or with check_only the files that need formatting."""
        return format_files(root, paths, check_only)
