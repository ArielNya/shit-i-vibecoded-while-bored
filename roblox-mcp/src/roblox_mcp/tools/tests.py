"""Run `*.spec.luau` specs: locally under Lune (pure Luau modules), or in a real Roblox
server through Open Cloud Luau Execution (anything that needs the engine)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import opencloud, toolchain
from .code import targets
from .project import build

HARNESS = (Path(__file__).resolve().parent.parent / "data" / "test_harness.luau").read_text()
MARKER = "@@ROBLOX_MCP_RESULTS@@"
MAX_FAILURES = 50

LUNE_DRIVER = """
local serde = require("@lune/serde")
local results = {}
for _, path in SPECS do
	local ok, spec = pcall(require, "./" .. path)
	if ok then
		runSpec(path, spec, FILTER, results)
	else
		loadFailed(path, spec, results)
	end
end
print(MARKER .. serde.encode("json", results))
"""

# Server-side in the uploaded place: every ModuleScript named *.spec in these services.
CLOUD_DRIVER = """
local results = {}
local SERVICES = { "ReplicatedStorage", "ReplicatedFirst", "ServerScriptService",
	"ServerStorage", "StarterPlayer", "StarterGui", "Workspace" }
for _, serviceName in SERVICES do
	for _, instance in game:GetService(serviceName):GetDescendants() do
		if instance:IsA("ModuleScript") and string.sub(instance.Name, -5) == ".spec" then
			local ok, spec = pcall(require, instance)
			local name = instance:GetFullName()
			if ok then
				runSpec(name, spec, FILTER, results)
			else
				loadFailed(name, spec, results)
			end
		end
	end
end
return results
"""


def lua_string(text: str) -> str:
    """A Luau string literal (JSON's escapes are valid Luau, minus \\u, so keep UTF-8)."""
    return json.dumps(text, ensure_ascii=False)


def find_specs(root: Path, paths: str) -> list[str]:
    specs = []
    for target in targets(root, paths):
        base = root / target
        files = [base] if base.is_file() else sorted(base.rglob("*.spec.lua*"))
        for f in files:
            if f.suffix in (".luau", ".lua") and f.stem.endswith(".spec"):
                specs.append(str(f.relative_to(root).with_suffix("")))
    return specs


def clean(error: str, root: Path | None) -> str:
    """Drop runner stack traces and the absolute project path from an error."""
    error = error.split("\nstack traceback:")[0].strip()
    return error.replace(f"{root}/", "") if root else error


def summarize(results: list[dict], extra: dict[str, Any], root: Path | None = None) -> dict:
    failures = [r for r in results if not r.get("ok")]
    out: dict[str, Any] = {
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "failures": [
            f"{r['name']}: {clean(str(r.get('error')), root)}" for r in failures[:MAX_FAILURES]
        ],
        **extra,
    }
    if not results:
        out["note"] = "no tests ran: add *.spec.luau files that return function(t) (see "\
            "read_guide('testing'))"  # fmt: skip
    return out


def run_local(root: Path, paths: str, filter_: str) -> dict[str, Any]:
    specs = find_specs(root, paths)
    if not specs:
        return summarize([], {"target": "local"})
    runner = root / f".roblox-mcp-tests-{uuid.uuid4().hex[:8]}.luau"
    spec_list = "{" + ", ".join(lua_string(s) for s in specs) + "}"
    runner.write_text(
        f"{HARNESS}\nlocal SPECS = {spec_list}\nlocal FILTER = {lua_string(filter_)}\n"
        f"local MARKER = {lua_string(MARKER)}\n{LUNE_DRIVER}",
        encoding="utf-8",
    )
    try:
        result = toolchain.run("lune", ["run", runner.name], root, timeout=120)
    finally:
        runner.unlink(missing_ok=True)
    for line in result.stdout.splitlines():
        if line.startswith(MARKER):
            output = [ln for ln in result.stdout.splitlines() if not ln.startswith(MARKER)]
            extra = {"target": "local", "specs": len(specs)}
            if output:
                extra["output"] = output[-50:]
            return summarize(json.loads(line[len(MARKER) :]), extra, root)
    raise RuntimeError(f"the Lune runner crashed:\n{(result.stderr or result.stdout)[-1500:]}")


def run_cloud(root: Path, filter_: str) -> dict[str, Any]:
    env = opencloud.config("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID", "ROBLOX_TEST_PLACE_ID")
    place = env["ROBLOX_TEST_PLACE_ID"]
    if place == os.environ.get("ROBLOX_PLACE_ID"):
        raise opencloud.CloudError("ROBLOX_TEST_PLACE_ID must be a separate place: tests "
                                   "upload a saved version to it")  # fmt: skip
    built = build(root, "build/tests.rbxl")
    version = opencloud.save_place_version(
        env["ROBLOX_UNIVERSE_ID"], place, (root / built["output"]).read_bytes()
    )
    script = f"{HARNESS}\nlocal FILTER = {lua_string(filter_)}\n{CLOUD_DRIVER}"
    task = opencloud.run_luau(env["ROBLOX_UNIVERSE_ID"], place, version, script)
    extra: dict[str, Any] = {"target": "cloud", "place_version": version}
    if task["logs"]:
        extra["output"] = task["logs"][-50:]
    if task["state"] != "COMPLETE" or not task["results"]:
        raise opencloud.CloudError(
            f"cloud run {task['state']}: {task['error']}\n" + "\n".join(task["logs"][-30:])
        )
    return summarize(task["results"][0] or [], extra)


SPEC_PATHS = Field(description="Comma-separated spec files or folders (default: every "
                   "synced folder; local only)")  # fmt: skip
TARGET = Field(description='"local" (Lune: pure Luau, no engine) or "cloud" (a real Roblox '
               'server via Open Cloud)')  # fmt: skip


def register(mcp: MCPServer, root: Path) -> None:
    @mcp.tool()
    def run_tests(
        paths: Annotated[str, SPEC_PATHS] = "",
        target: Annotated[str, TARGET] = "local",
        filter: Annotated[str, Field(description="Only tests whose full name contains this")] = "",
    ) -> dict[str, Any]:
        """Run the project's *.spec.luau specs and return pass/fail counts and each failure
        with its spec line. Local runs are instant but have no Roblox engine (no Instance,
        Vector3, services); cloud runs build the place, upload it as a saved version of
        ROBLOX_TEST_PLACE_ID and run every spec in a headless server."""
        if target == "local":
            return run_local(root, paths, filter)
        if target == "cloud":
            return run_cloud(root, filter)
        raise ValueError('target must be "local" or "cloud"')
