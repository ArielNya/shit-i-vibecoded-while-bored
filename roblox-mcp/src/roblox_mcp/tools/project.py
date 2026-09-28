"""Project-level tools: what kind of project this is, what's installed, creating a Rojo
project, building place files, and Rojo's live sync server."""

from __future__ import annotations

import atexit
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import __version__, toolchain

# Everything get_project_info reports on: the pinned tools plus rokit and (optional) selene.
TOOLCHAIN = ["rokit", *toolchain.PINS, "selene"]
ROJO_PORT = 34872  # Rojo's default, what its Studio plugin connects to


def tool_version(name: str) -> str | None:
    exe = toolchain.find(name)
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=5, check=False
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


def inside(root: Path, relative: str) -> Path:
    """A path under the project root; refuses anything that resolves outside it."""
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"'{relative}' is outside the project folder")
    return path


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


# --- init_project ------------------------------------------------------------------------

ENTRY = """\
--!strict
-- {side} entry point ({where}). Require each {side_lower} module in this folder, then
-- start it, e.g.:
--   local Rounds = require(script.Rounds)
--   Rounds.start()
"""


def template(name: str) -> dict[str, str]:
    """Roblox's recommended structure (creator-docs scripting/locations.md): one server
    entry, one client entry as a Client-RunContext Script in ReplicatedStorage, shared
    modules. The world (Workspace, Lighting, ...) is left to the place file."""
    project = {
        "name": name,
        "emitLegacyScripts": False,
        "tree": {
            "$className": "DataModel",
            "ReplicatedStorage": {
                "Shared": {"$path": "src/shared"},
                "Client": {"$path": "src/client"},
            },
            "ServerScriptService": {"Server": {"$path": "src/server"}},
        },
    }
    pins = "\n".join(f'{tool} = "{pin}"' for tool, pin in toolchain.PINS.items())
    return {
        "default.project.json": json.dumps(project, indent=2) + "\n",
        "src/server/init.server.luau": ENTRY.format(
            side="Server", side_lower="server", where="ServerScriptService.Server"
        ),
        "src/client/init.client.luau": ENTRY.format(
            side="Client", side_lower="client", where="ReplicatedStorage.Client"
        ),
        "src/shared/Config.luau": "--!strict\n-- Values both server and client read.\n"
        "local Config = {}\n\nreturn Config\n",
        "rokit.toml": f"[tools]\n{pins}\n",
        ".luaurc": json.dumps({"languageMode": "strict"}, indent=2) + "\n",
        ".gitignore": "build/\nsourcemap.json\n",
    }


def create_project(root: Path, name: str) -> dict[str, Any]:
    existing = find_project_file(root)
    created, kept = [], []
    for relative, content in template(name or root.name).items():
        path = root / relative
        if path.exists() or (relative == "default.project.json" and existing):
            kept.append(relative if path.exists() else existing.name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(relative)
    return {"created": created, "kept_existing": kept}


# --- build_place ------------------------------------------------------------------------

FORMATS = (".rbxl", ".rbxlx", ".rbxm", ".rbxmx")


def build(root: Path, output: str) -> dict[str, Any]:
    project_file = find_project_file(root)
    if project_file is None:
        raise ValueError("no *.project.json here: run init_project first")
    if not output:
        try:
            name = json.loads(project_file.read_text(encoding="utf-8")).get("name")
        except ValueError:
            name = None
        output = f"build/{name or root.name}.rbxl"
    target = inside(root, output)
    if target.suffix not in FORMATS:
        raise ValueError(f"output must end in one of {', '.join(FORMATS)}")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = toolchain.run("rojo", ["build", project_file.name, "-o", str(target)], root)
    if result.code != 0:
        raise RuntimeError(f"rojo build failed:\n{(result.stderr or result.stdout).strip()}")
    return {"output": str(target.relative_to(root)), "bytes": target.stat().st_size}


# --- sync_status ------------------------------------------------------------------------


def msgpack_str(data: bytes, key: str) -> str | None:
    """The string value after `key` in Rojo's msgpack /api/rojo reply (fixstr / str8)."""
    i = data.find(key.encode())
    if i < 0:
        return None
    i += len(key)
    if i < len(data) and 0xA0 <= data[i] <= 0xBF:
        n, i = data[i] - 0xA0, i + 1
    elif i + 1 < len(data) and data[i] == 0xD9:
        n, i = data[i + 1], i + 2
    else:
        return None
    return data[i : i + n].decode(errors="replace")


def probe(port: int) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/rojo", timeout=2) as r:
            data = r.read()
    except OSError:
        return None
    return {
        "project": msgpack_str(data, "projectName"),
        "rojo_version": msgpack_str(data, "serverVersion"),
    }


def port_open(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        return True
    except OSError:
        return False


class RojoServe:
    """The `rojo serve` this server started (at most one)."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.port = ROJO_PORT
        atexit.register(self.stop)

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, root: Path, port: int) -> None:
        project_file = find_project_file(root)
        if project_file is None:
            raise ValueError("no *.project.json here: run init_project first")
        exe = toolchain.find("rojo")
        if exe is None:
            raise toolchain.Missing("rojo")
        self.port = port
        self.proc = subprocess.Popen(
            [exe, "serve", project_file.name, "--port", str(port)],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and self.running():
            if probe(port):
                return
            time.sleep(0.2)
        error = self.proc.stderr.read() if not self.running() else "no answer after 15 s"
        self.stop()
        raise RuntimeError(f"rojo serve didn't start: {error.strip()}")

    def stop(self) -> None:
        if self.running():
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


def sync(root: Path, serve: RojoServe, action: str, port: int) -> dict[str, Any]:
    port = port or serve.port
    if action == "start":
        if not serve.running():
            if port_open(port):
                raise RuntimeError(f"port {port} is already in use (another rojo serve?)")
            serve.start(root, port)
    elif action == "stop":
        serve.stop()
    elif action != "status":
        raise ValueError("action must be status, start or stop")
    info = probe(port)
    return {
        "serving": info is not None,
        "port": port,
        "started_by_us": serve.running(),
        **(info or {}),
        "hint": "In Studio, connect the Rojo plugin to this port to sync files."
        if info
        else "Not serving. action=start runs `rojo serve` here.",
    }


def register(mcp: MCPServer, root: Path) -> None:
    serve = RojoServe()

    @mcp.tool()
    def get_project_info() -> dict[str, Any]:
        """Overview of the Roblox game project on disk: mode ("rojo" when a
        *.project.json exists, so code lives in files; else "studio"), the Rojo tree,
        installed toolchain versions (null = missing), Open Cloud settings, and the
        path of Studio's built-in MCP server on this machine. Start here."""
        return project_info(root)

    @mcp.tool()
    def init_project(
        name: Annotated[str, Field(description="Project name (default: folder name)")] = "",
    ) -> dict[str, Any]:
        """Make this folder a Rojo project in Roblox's recommended structure:
        default.project.json (server entry in ServerScriptService, client entry and
        shared modules in ReplicatedStorage), rokit.toml with the pinned toolchain,
        strict .luaurc. Never overwrites existing files."""
        return create_project(root, name)

    @mcp.tool()
    def build_place(
        output: Annotated[
            str,
            Field(
                description="Output path in the project: .rbxl/.rbxlx for a place, "
                ".rbxm/.rbxmx for a model (default build/<project>.rbxl)"
            ),  # fmt: skip
        ] = "",
    ) -> dict[str, Any]:
        """Build the Rojo project into a place or model file with `rojo build`."""
        return build(root, output)

    @mcp.tool()
    def sync_status(
        action: Annotated[str, Field(description="status, start or stop")] = "status",
        port: Annotated[int, Field(description="Rojo port (default 34872)")] = 0,
    ) -> dict[str, Any]:
        """Rojo live sync: is `rojo serve` running for this project, and start or stop
        it. While it runs and Studio's Rojo plugin is connected, file changes reach
        Studio within a second."""
        return sync(root, serve, action, port)
