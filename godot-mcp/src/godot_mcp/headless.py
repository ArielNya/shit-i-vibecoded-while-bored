"""Godot without the editor: validation, tests, exports, and API docs when no editor is
connected, by running `godot --headless` in the project.

The binary is --godot-bin / GODOT_BIN, else the connected editor's own, else found on
PATH or in the usual install places. The project is --project / GODOT_MCP_PROJECT, else
the connected editor's, else the nearest folder with a project.godot from the working
directory up.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bridge import GodotBridge, GodotCommandError, GodotConnectionError

OUTPUT_LIMIT = 200_000  # characters of Godot output kept per run
IMPORT_STAMP = ".godot/godot_mcp_import_stamp"


class HeadlessError(Exception):
    """Godot couldn't be found or run, or the run failed."""


@dataclass
class RunResult:
    code: int
    output: str
    seconds: float


def addon_dir() -> Path:
    """This server's copy of the addon (headless/runner.gd lives there): bundled in the
    wheel, or the source checkout's addon/ folder."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "addon", here.parents[1] / "addon" / "addons" / "godot_mcp"):
        if (candidate / "headless" / "runner.gd").is_file():
            return candidate
    raise HeadlessError("godot-mcp's addon files are missing from this installation.")


def _install_candidates() -> list[str]:
    home = Path.home()
    if sys.platform == "darwin":
        patterns = [
            "/Applications/Godot*.app/Contents/MacOS/Godot",
            f"{home}/Applications/Godot*.app/Contents/MacOS/Godot",
            f"{home}/Library/Application Support/Steam/steamapps/common/Godot Engine/"
            "Godot.app/Contents/MacOS/Godot",
        ]
    elif sys.platform == "win32":
        programs = os.environ.get("ProgramFiles", "C:/Program Files")
        patterns = [
            f"{programs}/Godot*/Godot*.exe",
            f"{home}/scoop/apps/godot/current/godot.exe",
            "C:/Program Files (x86)/Steam/steamapps/common/Godot Engine/godot*.exe",
        ]
    else:
        steam = "steamapps/common/Godot Engine/godot*"
        patterns = [
            f"{home}/.local/share/Steam/{steam}",
            f"{home}/.steam/steam/{steam}",
            f"{home}/.local/bin/Godot*",
            "/opt/godot*/Godot*",
            "/opt/godot*/godot*",
        ]
    found: list[str] = []
    for pattern in patterns:
        found += sorted(glob.glob(pattern), reverse=True)  # newest version first
    return [f for f in found if os.path.isfile(f) and os.access(f, os.X_OK)]


def find_godot(editor_executable: str | None = None) -> list[str]:
    """The command that starts Godot (a path, or `flatpak run ...`)."""
    explicit = os.environ.get("GODOT_BIN")
    if explicit:
        path = shutil.which(explicit) or explicit
        if not os.path.isfile(path):
            raise HeadlessError(
                f"GODOT_BIN / --godot-bin points at '{explicit}', which isn't a file."
            )
        return [path]
    if editor_executable and os.path.isfile(editor_executable):
        return [editor_executable]
    for name in ("godot", "godot4", "Godot", "godot-4", "godot.exe"):
        if found := shutil.which(name):
            return [found]
    if candidates := _install_candidates():
        return [candidates[0]]
    flatpak = shutil.which("flatpak")
    for root in ("/var/lib/flatpak", str(Path.home() / ".local/share/flatpak")):
        if flatpak and os.path.isdir(f"{root}/app/org.godotengine.Godot"):
            return [flatpak, "run", "org.godotengine.Godot"]
    raise HeadlessError(
        "Can't find a Godot 4.7+ binary: start the server with --godot-bin <path> (or set "
        "GODOT_BIN), or open the project in the editor with the Godot MCP plugin."
    )


def find_project(editor_project: str | None = None) -> Path:
    explicit = os.environ.get("GODOT_MCP_PROJECT")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_file() and path.name == "project.godot":
            path = path.parent
        if not (path / "project.godot").is_file():
            raise HeadlessError(f"--project / GODOT_MCP_PROJECT: no project.godot in '{path}'.")
        return path
    if editor_project:
        return Path(editor_project).resolve()
    cwd = Path.cwd().resolve()
    for folder in (cwd, *cwd.parents):
        if (folder / "project.godot").is_file():
            return folder
    raise HeadlessError(
        "No Godot project found: the editor isn't connected and there's no project.godot in "
        f"'{cwd}' or above. Start the server with --project <folder> (or GODOT_MCP_PROJECT)."
    )


def output_errors(output: str, limit: int = 20) -> list[str]:
    """The ERROR:/SCRIPT ERROR: messages in Godot's output (with their continuation
    lines, without the C++ `at:` locations)."""
    errors: list[str] = []
    current: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if line.startswith(("ERROR:", "SCRIPT ERROR:", "USER ERROR:")):
            if current:
                errors.append("\n".join(current))
            current = [line.split(":", 1)[1].strip()]
        elif (
            current
            and stripped
            and not stripped.startswith("at:")
            and not line.startswith(("WARNING:", "[", "Godot Engine"))
        ):
            current.append(stripped)
        elif current:
            errors.append("\n".join(current))
            current = []
    if current:
        errors.append("\n".join(current))
    return list(dict.fromkeys(errors))[:limit]


class Headless:
    """Runs Godot for the project the tools work on."""

    def __init__(self, bridge: GodotBridge):
        self.bridge = bridge

    async def editor_info(self) -> dict[str, Any] | None:
        """The connected editor's handshake info, or None if no editor is reachable."""
        try:
            return await self.bridge.ensure_info()
        except GodotConnectionError:
            return None

    async def target(self) -> tuple[list[str], Path, bool]:
        """(godot command, project folder, editor connected)."""
        info = await self.editor_info()
        editor_project = (info or {}).get("project_path")
        project = find_project(editor_project)
        # Only reuse the editor's binary for the editor's own project.
        same = editor_project and Path(editor_project).resolve() == project
        command = find_godot((info or {}).get("executable") if same else None)
        return command, project, bool(same)

    async def run(
        self, command: list[str], project: Path, args: list[str], timeout: float
    ) -> RunResult:
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *command, "--headless", "--path", str(project), *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(project),
            )  # fmt: skip
        except OSError as exc:
            raise HeadlessError(f"Could not start Godot ({command[0]}): {exc}") from exc
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise HeadlessError(f"Godot did not finish within {timeout:.0f}s.") from None
        text = out.decode(errors="replace")
        if len(text) > OUTPUT_LIMIT:
            text = "[… earlier output cut …]\n" + text[-OUTPUT_LIMIT:]
        return RunResult(proc.returncode or 0, text, round(time.monotonic() - start, 2))

    async def version(self, command: list[str]) -> str | None:
        """'4.7.2.stable' (the export templates folder name), or None if unknown."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *command, "--version",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            out, _ = await asyncio.wait_for(proc.communicate(), 30)
        except (OSError, TimeoutError):
            return None
        lines = out.decode(errors="replace").strip().splitlines()
        parts: list[str] = []
        for part in (lines[-1] if lines else "").split("."):
            parts.append(part)
            if not part.isdigit():  # the status: stable, rc1, beta2, ...
                break
        return ".".join(parts) if len(parts) >= 3 and not parts[-1].isdigit() else None

    async def ensure_imported(self, command: list[str], project: Path, editor: bool) -> None:
        """Imports assets and refreshes the class_name cache, without which a headless run
        can't load textures or project classes: the connected editor rescans (files may
        have changed behind its back), else `godot --import` runs if anything changed
        since the last one."""
        if editor:
            try:
                await self.bridge.call("rescan_filesystem", timeout=300)
            except (GodotConnectionError, GodotCommandError) as exc:
                raise HeadlessError(f"The editor could not rescan the project: {exc}") from exc
            return
        stamp = project / IMPORT_STAMP
        if stamp.is_file() and not _changed_since(project, stamp.stat().st_mtime):
            return
        result = await self.run(command, project, ["--import"], timeout=600)
        if result.code != 0 or not (project / ".godot").is_dir():
            errors = output_errors(result.output) or [result.output[-2000:]]
            raise HeadlessError("Importing the project failed:\n" + "\n".join(errors))
        stamp.touch()

    async def request(self, method: str, params: dict[str, Any], timeout: float = 120) -> Any:
        """Runs `method` of the addon's headless runner in the project and returns its
        result (the same handlers the editor plugin uses)."""
        command, project, editor = await self.target()
        await self.ensure_imported(command, project, editor)
        runner = addon_dir() / "headless" / "runner.gd"
        with tempfile.TemporaryDirectory(prefix="godot-mcp-") as tmp:
            req, reply = Path(tmp) / "request.json", Path(tmp) / "reply.json"
            req.write_text(json.dumps({"method": method, "params": params}))
            result = await self.run(
                command, project,
                ["-s", str(runner), "--", f"--mcp-request={req}", f"--mcp-reply={reply}"],
                timeout,
            )  # fmt: skip
            if not reply.is_file():
                errors = output_errors(result.output) or [result.output[-2000:]]
                raise HeadlessError(f"Headless Godot failed ({method}):\n" + "\n".join(errors))
            data = json.loads(reply.read_text())
        if "error" in data:
            raise HeadlessError(data["error"].get("message", "failed"))
        return data["result"]


def _changed_since(project: Path, when: float) -> bool:
    """Whether any project file (outside hidden folders) changed after `when`."""
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in (*files, *dirs):
            try:
                if os.stat(os.path.join(root, name)).st_mtime > when:
                    return True
            except OSError:
                continue
    return False
