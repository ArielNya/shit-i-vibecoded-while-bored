"""Ship & test: validate the whole project, run GUT / GdUnit4 tests, export presets. These
run a headless Godot, so they work with or without the editor open."""

from __future__ import annotations

import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ..headless import Headless, HeadlessError, output_errors
from ._common import Godot, ToolError

GUT = "res://addons/gut/gut_cmdln.gd"
GDUNIT = "res://addons/gdUnit4/bin/GdUnitCmdTool.gd"
GDUNIT_REPORTS = ".godot/godot_mcp/gdunit"
GUT_XML = ".godot/godot_mcp/gut.xml"
MAX_FAILURES = 50


def export_dirs() -> list[Path]:
    """Folders export_project may write to: --export-dir / GODOT_MCP_EXPORT_DIRS
    (os.pathsep separated), else the server's working directory."""
    raw = os.environ.get("GODOT_MCP_EXPORT_DIRS", "")
    dirs = [Path(d).expanduser() for d in raw.split(os.pathsep) if d.strip()]
    return [d.resolve() for d in (dirs or [Path.cwd()])]


# --- export presets ---------------------------------------------------------------------


def _cfg_value(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    try:
        return int(raw)
    except ValueError:
        return raw


def read_presets(project: Path) -> list[dict[str, Any]]:
    """The presets in export_presets.cfg (Godot ConfigFile syntax)."""
    cfg = project / "export_presets.cfg"
    if not cfg.is_file():
        return []
    sections: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
        elif current is not None and "=" in line and not line.startswith(";"):
            key, _, value = line.partition("=")
            current[key.strip()] = _cfg_value(value)
    presets = []
    for name, values in sections.items():
        if re.fullmatch(r"preset\.\d+", name):
            presets.append(
                {
                    "name": values.get("name", ""),
                    "platform": values.get("platform", ""),
                    "runnable": values.get("runnable", False),
                    "export_path": values.get("export_path", ""),
                    "export_filter": values.get("export_filter", ""),
                }
            )
    return presets


def templates_dir(version: str) -> Path:
    """Where the editor looks for export templates of `version` (e.g. 4.7.2.stable)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Godot"
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/Godot"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "godot"
    return base / "export_templates" / version


def _allowed_output(output: str, preset: dict[str, Any], mode: str) -> Path:
    allowed = export_dirs()
    if not output:
        name = Path(str(preset.get("export_path") or "")).name or "game"
        output = str(Path(name).with_suffix(".pck")) if mode == "pack" else name
    path = Path(output).expanduser()
    if not path.is_absolute():
        path = allowed[0] / path
    path = path.resolve()
    if not any(d == path.parent or d in path.parents for d in allowed):
        raise ToolError(
            f"'{output}' is outside the folders export_project may write to "
            f"({', '.join(map(str, allowed))}). Start the server with --export-dir <folder> "
            "(or GODOT_MCP_EXPORT_DIRS) to allow another one."
        )
    if mode == "pack" and path.suffix not in (".pck", ".zip"):
        raise ToolError("A pack export's output must end in .pck or .zip.")
    return path


# --- tests ------------------------------------------------------------------------------


def _frameworks(project: Path, wanted: str) -> list[str]:
    installed = [
        name
        for name, script in (("gut", GUT), ("gdunit4", GDUNIT))
        if (project / script.removeprefix("res://")).is_file()
    ]
    if wanted != "auto":
        if wanted not in installed:
            raise ToolError(f"{wanted} isn't installed in this project (addons/).")
        return [wanted]
    if not installed:
        raise ToolError(
            "No test framework found: install GUT (addons/gut) or GdUnit4 (addons/gdUnit4) "
            "from the Asset Library, then write tests in res://test."
        )
    return installed


def _res_to_os(project: Path, res_path: str) -> Path:
    return project / res_path.removeprefix("res://")


def _test_path(project: Path, path: str) -> str:
    if path:
        res = path if path.startswith("res://") else "res://" + path.lstrip("/")
        if ".." in res.split("/") or not _res_to_os(project, res).exists():
            raise ToolError(f"No test folder or file '{res}' in the project.")
        return res.rstrip("/") if res != "res://" else res
    for candidate in ("res://test", "res://tests"):
        if _res_to_os(project, candidate).is_dir():
            return candidate
    raise ToolError("No res://test or res://tests folder; pass `path` to the tests.")


def _test_files(project: Path, res_path: str) -> list[Path]:
    root = _res_to_os(project, res_path)
    return [root] if root.is_file() else sorted(root.rglob("*.gd"))


def _gdunit_ignores(project: Path, res_path: str, test_name: str) -> list[str]:
    """GdUnit4 can't select tests by name, only ignore them: ignore the others."""
    args = []
    for file in _test_files(project, res_path):
        text = file.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(r"^func\s+(test_\w+)", text, re.MULTILINE):
            if test_name not in name:
                args += ["-i", f"{file.stem}:{name}"]
    return args


LOCATION = re.compile(r"(res://[^\s:'\"]+\.gd):(\d+)")
GUT_LINE = re.compile(r"at line (\d+)")


def parse_junit(xml_text: str, framework: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failures: list[dict[str, Any]] = []
    suites: list[str] = []
    for suite in root.iter("testsuite"):
        suites.append(suite.get("name", ""))
        for case in suite.iter("testcase"):
            problem = case.find("failure")
            kind = "failed"
            if problem is None:
                problem = case.find("error")
                kind = "errors"
            if problem is None:
                skipped = case.find("skipped") is not None or case.get("status") == "pending"
                counts["skipped" if skipped else "passed"] += 1
                continue
            counts[kind] += 1
            text = "\n".join(
                part.strip() for part in (problem.text or "", problem.get("message", "")) if part
            )
            entry: dict[str, Any] = {
                "test": case.get("name", ""),
                "suite": suite.get("name", ""),
                "message": (problem.text or problem.get("message") or "").strip()[:2000],
            }
            if kind == "errors":
                entry["error"] = True
            if match := LOCATION.search(text):
                entry["file"], entry["line"] = match.group(1), int(match.group(2))
            elif framework == "gut":
                entry["file"] = "res://" + case.get("classname", "").removeprefix("res://")
                if match := GUT_LINE.search(text):
                    entry["line"] = int(match.group(1))
            failures.append(entry)
    total = sum(counts.values())
    return {"total": total, **counts, "suites": len(suites), "failures": failures}


def register(mcp: MCPServer, godot: Godot) -> None:
    headless: Headless = godot.headless

    async def target() -> tuple[list[str], Path, bool]:
        try:
            return await headless.target()
        except HeadlessError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool()
    async def validate_project(
        include_addons: Annotated[
            bool, Field(description="Also check res://addons (third-party plugins)")
        ] = False,
    ) -> dict[str, Any]:
        """Check the whole project without running it: every script is compiled and
        every scene/resource loaded, and references to missing files are listed (also the
        main scene and autoloads). Errors come with file:line. Works without the editor."""
        try:
            result = await headless.request(
                "validate_project", {"include_addons": include_addons}, timeout=600
            )
        except HeadlessError as exc:
            raise ToolError(str(exc)) from exc
        if not result.get("ok"):
            result["hint"] = (
                "Fix the listed errors, then validate again. get_diagnostics (editor) also "
                "shows warnings."
            )
        return result

    @mcp.tool()
    async def list_export_presets() -> dict[str, Any]:
        """The project's export presets (Project > Export) and whether this Godot
        version's export templates are installed (release/debug exports need them; pack
        exports don't)."""
        command, project, _ = await target()
        presets = read_presets(project)
        out: dict[str, Any] = {"project": str(project), "presets": presets}
        version = await headless.version(command)
        if version:
            folder = templates_dir(version)
            out["godot_version"] = version
            out["templates_installed"] = folder.is_dir() and any(folder.iterdir())
            out["templates_dir"] = str(folder)
        if not presets:
            out["hint"] = (
                "No export presets: add them in the editor (Project > Export), which saves "
                "export_presets.cfg."
            )
        out["export_dirs"] = [str(d) for d in export_dirs()]
        return out

    @mcp.tool()
    async def export_project(
        preset: Annotated[str, Field(description="Export preset name (see list_export_presets)")],
        output: Annotated[
            str,
            Field(
                description="Output file, inside the server's export folders (default: its "
                "working directory); default: the preset's file name"
            ),
        ] = "",
        mode: Annotated[
            Literal["release", "debug", "pack"],
            Field(
                description="release/debug build (needs export templates), or just the "
                "game data as a .pck/.zip"
            ),
        ] = "release",  # fmt: skip
    ) -> dict[str, Any]:
        """Export the project with a preset, from the saved files on disk (save scenes
        first). Returns the files written, or the export errors."""
        command, project, editor = await target()
        presets = read_presets(project)
        match = next((p for p in presets if p["name"] == preset), None)
        if match is None:
            names = ", ".join(repr(p["name"]) for p in presets) or "none"
            raise ToolError(f"No export preset '{preset}' (presets: {names}).")
        path = _allowed_output(output, match, mode)
        path.parent.mkdir(parents=True, exist_ok=True)
        project_root = project.resolve()
        if project_root in path.parents:  # keep exported files out of the project's imports
            top = project_root / path.relative_to(project_root).parts[0]
            if top != path and not (top / ".gdignore").exists():
                (top / ".gdignore").touch()
        before = {f: f.stat().st_mtime for f in path.parent.iterdir() if f.is_file()}
        try:
            if editor:  # the export imports by itself; with an editor open, let it do that
                await headless.ensure_imported(command, project, editor)
            result = await headless.run(
                command, project, [f"--export-{mode}", preset, str(path)], timeout=900
            )
        except HeadlessError as exc:
            raise ToolError(str(exc)) from exc
        written = [
            f
            for f in sorted(path.parent.iterdir())
            if f.is_file() and f.name != ".gdignore" and before.get(f) != f.stat().st_mtime
        ]
        errors = output_errors(result.output)
        # Judge by the file, not the exit code: Godot sometimes crashes while quitting
        # after a finished export (seen with GUT installed).
        failed = any(e.startswith(("Project export for preset", "Cannot export")) for e in errors)
        if failed or path not in written:
            detail = "\n".join(errors) or result.output[-2000:]
            hint = ""
            if "export template" in detail.lower():
                hint = (
                    "\nInstall the export templates (Editor > Manage Export Templates), or "
                    "use mode='pack' for just the game data."
                )
            raise ToolError(f"Export with preset '{preset}' failed:\n{detail}{hint}")
        out: dict[str, Any] = {
            "preset": preset,
            "mode": mode,
            "output": str(path),
            "files": [{"path": str(f), "bytes": f.stat().st_size} for f in written],
            "seconds": result.seconds,
        }
        if errors:
            out["errors_logged"] = errors
        if result.code != 0:
            out["warning"] = f"Godot exited with code {result.code} after writing the export."
        return out

    @mcp.tool()
    async def run_tests(
        path: Annotated[
            str, Field(description="Test folder or file (res://...); default res://test(s)")
        ] = "",
        test_name: Annotated[str, Field(description="Only tests whose name contains this")] = "",
        framework: Annotated[
            Literal["auto", "gut", "gdunit4"],
            Field(description="Which installed framework; auto = every one installed"),
        ] = "auto",
        timeout: Annotated[int, Field(ge=10, le=3600, description="Seconds")] = 300,
    ) -> dict[str, Any]:
        """Run the project's unit tests (GUT or GdUnit4) in a headless Godot. Returns
        pass/fail counts and each failure with its message and file:line."""
        command, project, editor = await target()
        frameworks = _frameworks(project, framework)
        res_path = _test_path(project, path)
        try:
            await headless.ensure_imported(command, project, editor)
        except HeadlessError as exc:
            raise ToolError(str(exc)) from exc
        runs = []
        for fw in frameworks:
            runs.append(await _run_framework(command, project, fw, res_path, test_name, timeout))
        if len(runs) == 1:
            return runs[0]
        return {
            "ok": all(r["ok"] for r in runs),
            "total": sum(r["total"] for r in runs),
            "failed": sum(r["failed"] + r["errors"] for r in runs),
            "runs": runs,
        }

    async def _run_framework(
        command: list[str], project: Path, fw: str, res_path: str, test_name: str, timeout: int
    ) -> dict[str, Any]:
        if fw == "gut":
            xml = project / GUT_XML
            xml.parent.mkdir(parents=True, exist_ok=True)
            xml.unlink(missing_ok=True)
            is_file = _res_to_os(project, res_path).is_file()
            args = ["-s", GUT, "-gexit", "-gdisable_colors", f"-gjunit_xml_file={xml}"]
            args += (
                [f"-gtest={res_path}"] if is_file else [f"-gdir={res_path}", "-ginclude_subdirs"]
            )
            if test_name:
                args.append(f"-gunit_test_name={test_name}")
        else:
            reports = project / GDUNIT_REPORTS
            shutil.rmtree(reports, ignore_errors=True)
            args = ["-s", GDUNIT, "-a", res_path, "--ignoreHeadlessMode", "-c",
                    "-rd", GDUNIT_REPORTS]  # fmt: skip
            if test_name:
                args += _gdunit_ignores(project, res_path, test_name)
        try:
            result = await headless.run(command, project, args, timeout=timeout)
        except HeadlessError as exc:
            raise ToolError(f"{fw}: {exc}") from exc
        if fw == "gut":
            report = xml if xml.is_file() else None
        else:
            found = sorted((project / GDUNIT_REPORTS).glob("report_*/results.xml"))
            report = found[-1] if found else None
        engine_errors = output_errors(result.output)
        if report is None:
            raise ToolError(
                f"{fw} produced no results (exit code {result.code}):\n"
                + ("\n".join(engine_errors) or result.output[-3000:])
            )
        summary = parse_junit(report.read_text(encoding="utf-8", errors="replace"), fw)
        failures = summary.pop("failures")
        out: dict[str, Any] = {
            "framework": fw,
            "path": res_path,
            "ok": summary["total"] > 0 and summary["failed"] == 0 and summary["errors"] == 0,
            **summary,
            "failures": failures[:MAX_FAILURES],
            "seconds": result.seconds,
        }
        if len(failures) > MAX_FAILURES:
            out["failures_truncated"] = len(failures)
        if summary["total"] == 0:
            out["note"] = "No tests ran. Check the path and test naming (test_*.gd for GUT)."
        if engine_errors and (not out["ok"]):
            out["engine_errors"] = engine_errors
        return out
