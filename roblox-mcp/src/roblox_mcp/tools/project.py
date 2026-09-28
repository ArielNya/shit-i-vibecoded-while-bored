"""Project-level tools: what kind of project this is and what's installed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from .. import __version__

# The CLIs later tools shell out to; normally pinned in the game project's rokit.toml.
TOOLCHAIN = ["rokit", "rojo", "luau-lsp", "selene", "stylua", "lune"]


def tool_version(name: str) -> str | None:
    try:
        out = subprocess.run(
            [name, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[0] if line else None


def studio_mcp_path() -> str | None:
    """Where Studio installs its built-in MCP server launcher on this machine."""
    if sys.platform == "win32":
        candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Roblox" / "mcp.bat"]
    elif sys.platform == "darwin":
        app = "RobloxStudio.app/Contents/MacOS/StudioMCP"
        candidates = [Path("/Applications") / app, Path.home() / "Applications" / app]
    else:
        return None  # Studio doesn't run on Linux
    return next((str(p) for p in candidates if p.is_file()), None)


def find_project_file(root: Path) -> Path | None:
    default = root / "default.project.json"
    if default.is_file():
        return default
    return next(iter(sorted(root.glob("*.project.json"))), None)


def summarize_tree(node: dict, depth: int = 3) -> dict[str, Any]:
    """Rojo's tree without the noise: each instance's class and synced path."""
    out: dict[str, Any] = {}
    for name, child in node.items():
        if name.startswith("$") or not isinstance(child, dict):
            continue
        entry = {k[1:]: child[k] for k in ("$className", "$path") if k in child}
        if depth > 1 and (sub := summarize_tree(child, depth - 1)):
            entry["children"] = sub
        out[name] = entry
    return out


def project_info(root: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"server_version": __version__, "root": str(root)}
    project_file = find_project_file(root)
    if project_file is None:
        info["mode"] = "studio"
    else:
        info["mode"] = "rojo"
        info["project_file"] = project_file.name
        try:
            project = json.loads(project_file.read_text(encoding="utf-8"))
            info["name"] = project.get("name")
            info["tree"] = summarize_tree(project.get("tree", {}))
        except (OSError, ValueError) as e:
            info["project_error"] = f"can't read {project_file.name}: {e}"
    info["toolchain"] = {name: tool_version(name) for name in TOOLCHAIN}
    info["open_cloud"] = {
        "api_key": bool(os.environ.get("ROBLOX_API_KEY")),
        "universe_id": os.environ.get("ROBLOX_UNIVERSE_ID"),
        "place_id": os.environ.get("ROBLOX_PLACE_ID"),
    }
    info["studio_mcp"] = studio_mcp_path()
    return info


def register(mcp: MCPServer, root: Path) -> None:
    @mcp.tool()
    def get_project_info() -> dict[str, Any]:
        """Overview of the Roblox game project on disk: mode ("rojo" when a
        *.project.json exists, so code lives in files; else "studio"), the Rojo tree,
        installed toolchain versions (null = missing), Open Cloud settings, and the
        path of Studio's built-in MCP server on this machine. Start here."""
        return project_info(root)
