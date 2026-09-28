"""The toolchain tools against the real pinned binaries (install them with
scripts/install_toolchain.py and point ROBLOX_MCP_BIN_DIR at the folder)."""

import shutil
from pathlib import Path

import pytest

from roblox_mcp import toolchain
from roblox_mcp.tools import code, project

missing = [t for t in ("rojo", "luau-lsp", "stylua") if toolchain.find(t) is None]
pytestmark = pytest.mark.skipif(bool(missing), reason=f"not installed: {missing}")

SAMPLE = Path(__file__).parent.parent / "fixtures" / "sample_game"

BROKEN = """--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Damage = require(ReplicatedStorage.Shared.Damage)
local hp: number = "full"
wait(1)
Players.PlayerAdded:Connect(function(player) print(player.Nmae, Damage.aply(1, 2)) end)
game:GetService("ChangeHistoryService"):TryBeginRecording("x")
return nil
"""


@pytest.fixture
def game(tmp_path):
    shutil.copytree(SAMPLE, tmp_path / "game")
    return tmp_path / "game"


def test_clean_project_checks_clean(game):
    result = code.check(game, "")
    assert result["checked"] == ["src/shared", "src/server"]
    assert (result["errors"], result["warnings"]) == (0, 0), result


def test_check_finds_what_studio_would(game):
    (game / "src/server/Broken.luau").write_text(BROKEN)
    result = code.check(game, "")
    text = "\n".join(result["problems"])
    for expected in [
        "src/server/Broken.luau:5:20 error TypeError: Expected this to be 'number'",
        "error TypeError: Key 'Nmae' not found in external type 'Player'",
        "Key 'aply' not found",  # resolved through the Rojo sourcemap
        "Key 'TryBeginRecording' not found",  # plugin-only API in game code
        "warning DeprecatedApi: Function 'wait' is deprecated, use 'task.wait'",
    ]:
        assert expected in text, text
    assert result["problems"][0].split(" ")[1] == "error"  # errors first


def test_format(game):
    (game / "src/server/Broken.luau").write_text(BROKEN)
    assert code.format_files(game, "", True)["unformatted"] == ["src/server/Broken.luau"]
    assert code.format_files(game, "src/server", False)["formatted"] == ["src/server/Broken.luau"]
    assert code.format_files(game, "", True)["unformatted"] == []


def test_new_project_builds_and_checks_clean(tmp_path):
    project.create_project(tmp_path, "arena")
    assert code.check(tmp_path, "")["problems"] == []
    assert code.format_files(tmp_path, "", True)["unformatted"] == []
    built = project.build(tmp_path, "")
    assert built["output"] == "build/arena.rbxl" and built["bytes"] > 500


def test_sync_start_status_stop(game):
    serve = project.RojoServe()
    try:
        started = project.sync(game, serve, "start", 34871)
        assert started["serving"] and started["project"] == "sample_game"
        assert started["rojo_version"] == "7.7.0" and started["started_by_us"]
        with pytest.raises(RuntimeError, match="already in use"):
            project.sync(game, project.RojoServe(), "start", 34871)
    finally:
        stopped = project.sync(game, serve, "stop", 0)
    assert not stopped["serving"]


@pytest.mark.skipif(toolchain.find("selene") is None, reason="selene not installed")
def test_selene_runs_when_the_project_has_a_config(game):
    (game / "selene.toml").write_text('std = "luau"\n')  # "roblox" needs a download
    (game / "src/shared/Shadow.luau").write_text("local x = 1\nlocal x = 2\nprint(x)\nreturn nil\n")
    text = "\n".join(code.check(game, "src/shared")["problems"])
    assert "src/shared/Shadow.luau:2:7 warning selene::shadowing" in text
