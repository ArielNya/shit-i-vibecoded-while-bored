"""M6 acceptance: with no editor open, an agent checks a project, fixes it, runs its tests
until they pass and exports it — through the server as a client runs it (stdio, flags
only, no Godot on PATH)."""

import json
import os
import sys

import pytest
from mcp import Client, StdioServerParameters

from .conftest import _free_port
from .test_build import PRESETS, install_framework

pytestmark = pytest.mark.anyio

SCORE_TEST = """extends GutTest

func test_score_adds_points() -> void:
\tvar state = load("res://scripts/game_state.gd").new()
\tstate.add_points(3)
\tstate.add_points(4)
\tassert_eq(state.score, 7)
\tstate.free()
"""


async def test_check_fix_test_export_without_an_editor(project_dir, tmp_path):
    if not os.environ.get("GODOT_BIN"):
        pytest.skip("set GODOT_BIN to a Godot 4.7+ editor binary to run integration tests")
    install_framework("gut", project_dir)
    (project_dir / "test").mkdir()
    (project_dir / "test" / "test_score.gd").write_text(SCORE_TEST)
    (project_dir / "export_presets.cfg").write_text(PRESETS)
    exports = tmp_path / "exports"
    args = [
        "-m", "godot_mcp.server",
        "--godot-port", str(_free_port()),  # nothing listens: no editor
        "--godot-bin", os.environ["GODOT_BIN"],
        "--project", str(project_dir),
        "--export-dir", str(exports),
    ]  # fmt: skip
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}  # scrubbed, like some harnesses
    params = StdioServerParameters(command=sys.executable, args=args, env=env)
    async with Client(params) as client:

        async def call(tool, **arguments):
            result = await client.call_tool(tool, arguments)
            assert not result.is_error, result.content[0].text
            return json.loads(result.content[0].text)

        # 1. The project doesn't compile: broken.gd, found with file:line.
        check = await call("validate_project")
        assert not check["ok"]
        assert {e["file"] for e in check["errors"]} == {"res://scripts/broken.gd"}
        (project_dir / "scripts" / "broken.gd").write_text(
            "extends Node\n\nfunc _ready() -> void:\n\tvar count: int = 3\n\tprint(count)\n"
        )
        assert (await call("validate_project"))["ok"]

        # 2. The test fails: GameState has no add_points yet (a runtime error in the test).
        first = await call("run_tests")
        assert not first["ok"] and first["total"] == 1
        game_state = project_dir / "scripts" / "game_state.gd"
        game_state.write_text(
            game_state.read_text() + "\n\nfunc add_points(n: int) -> void:\n\tscore += n\n"
        )
        second = await call("run_tests")
        assert second["ok"] and (second["passed"], second["failed"]) == (1, 0)

        # 3. Ship it.
        shipped = await call("export_project", preset="Linux", mode="pack")
        assert shipped["output"] == str(exports / "demo.pck")
        assert (exports / "demo.pck").stat().st_size > 1000
