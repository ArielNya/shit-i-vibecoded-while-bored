"""M6 without an editor: validate_project, run_tests (GUT and GdUnit4), exports and the
docs tools, all through a headless Godot. No editor runs in this module."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from mcp import Client

from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.server import create_server

from .conftest import _free_port

pytestmark = pytest.mark.anyio

# Pinned so a framework release can't break the tests; bump deliberately.
FRAMEWORKS = {"gut": ("bitwes/Gut", "v9.7.1"), "gdUnit4": ("MikeSchulze/gdUnit4", "v6.2.1")}

PRESETS = """[preset.0]

name="Linux"
platform="Linux"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter="addons/godot_mcp/*"
export_path="build/demo.x86_64"

[preset.0.options]

binary_format/embed_pck=false
"""

GUT_TEST = """extends GutTest

func test_player_speed() -> void:
\tassert_eq(Player.new().speed, 200.0)

func test_wrong_on_purpose() -> void:
\tassert_eq(2 * 2, 5, "multiplication")
"""

GDUNIT_TEST = """extends GdUnitTestSuite

func test_adds() -> void:
\tassert_int(1 + 1).is_equal(2)

func test_fails_on_purpose() -> void:
\tassert_int(2 * 2).is_equal(5)
"""


def framework_cache() -> Path:
    return Path(os.environ.get("GODOT_MCP_TEST_FRAMEWORKS", "~/.cache/godot-mcp/frameworks"))


def install_framework(name: str, project: Path) -> None:
    """Copies addons/<name> from a cached clone of the pinned release (cloned on first use)."""
    repo, tag = FRAMEWORKS[name]
    clone = framework_cache().expanduser() / f"{name}-{tag}"
    if not (clone / "addons" / name).is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(clone, ignore_errors=True)
        try:
            subprocess.run(
                ["git", "clone", "-q", "--depth", "1", "--branch", tag,
                 f"https://github.com/{repo}", str(clone)],
                check=True, timeout=300, capture_output=True,
            )  # fmt: skip
        except (subprocess.SubprocessError, OSError) as exc:
            pytest.skip(f"could not fetch {repo} {tag}: {exc}")
    shutil.copytree(
        clone / "addons" / name, project / "addons" / name, ignore=shutil.ignore_patterns("test")
    )


@pytest.fixture(scope="module")
def godot_bin():
    if not os.environ.get("GODOT_BIN"):
        pytest.skip("set GODOT_BIN to a Godot 4.7+ editor binary to run integration tests")


@pytest.fixture
def no_editor(godot_bin, project_dir, tmp_path, monkeypatch):
    """Server settings for a project with no editor open: nothing listens on the port."""
    exports = tmp_path / "exports"
    exports.mkdir()
    monkeypatch.setenv("GODOT_MCP_PROJECT", str(project_dir))
    monkeypatch.setenv("GODOT_MCP_EXPORT_DIRS", str(exports))
    return {"project": project_dir, "exports": exports}


@pytest.fixture
async def call_tool(no_editor):
    """await call_tool("tool", ...) -> (is_error, parsed JSON or error text)."""
    bridge = GodotBridge(BridgeConfig(port=_free_port(), timeout=5, token="unused"))
    async with Client(create_server(bridge)) as client:

        async def call(tool, **args):
            result = await client.call_tool(tool, args)
            text = result.content[0].text
            return result.is_error, (text if result.is_error else json.loads(text))

        yield call
    await bridge.close()


async def ok(call_tool, tool, **args):
    is_error, value = await call_tool(tool, **args)
    assert not is_error, value
    return value


async def test_docs_without_an_editor(call_tool):
    timer = await ok(call_tool, "get_class_docs", class_name="Timer")
    assert timer["kind"] == "native" and "No editor connected" in timer["note"]
    assert "start(time_sec: float = -1) -> void" in timer["methods"]
    member = await ok(call_tool, "get_class_docs", class_name="Timer", member="queue_free")
    assert member["signatures"] == ["queue_free() -> void"]  # inherited from Node
    player = await ok(call_tool, "get_class_docs", class_name="Player")  # a project class
    assert player["kind"] == "script" and player["path"] == "res://scripts/player.gd"
    found = await ok(call_tool, "search_docs", query="move slide")
    assert {"kind": "method", "class": "CharacterBody2D", "name": "move_and_slide"}.items() <= (
        found["results"][0].items()
    )
    is_error, text = await call_tool("get_class_docs", class_name="KinematicBody2D")
    assert is_error and "CharacterBody2D" in text


async def test_validate_project(call_tool, no_editor):
    project = no_editor["project"]
    broken = await ok(call_tool, "validate_project")
    assert not broken["ok"] and broken["checked"]["scripts"] >= 4
    lines = {(e["file"], e.get("line")) for e in broken["errors"]}
    assert ("res://scripts/broken.gd", 4) in lines and ("res://scripts/broken.gd", 5) in lines
    assert all(e["file"] == "res://scripts/broken.gd" for e in broken["errors"])
    assert "hint" in broken

    # A scene pointing at a file that's gone, and an autoload that's gone.
    (project / "scripts" / "broken.gd").unlink()
    (project / "scenes" / "ghost.tscn").write_text(
        '[gd_scene format=3]\n\n[ext_resource type="Script" path="res://scripts/gone.gd" '
        'id="1"]\n\n[node name="Ghost" type="Node"]\nscript = ExtResource("1")\n'
    )
    settings = project / "project.godot"
    original = settings.read_text()
    settings.write_text(original.replace('GameState="*res://scripts/game_state.gd"',
                                         'GameState="*res://scripts/game_state.gd"\n'
                                         'Missing="*res://scripts/missing.gd"'))  # fmt: skip
    missing = await ok(call_tool, "validate_project")
    deps = {(m["file"], m["dependency"]) for m in missing["missing_dependencies"]}
    assert ("res://scenes/ghost.tscn", "res://scripts/gone.gd") in deps
    assert ("res://project.godot", "res://scripts/missing.gd") in deps

    (project / "scenes" / "ghost.tscn").unlink()
    settings.write_text(original)
    clean = await ok(call_tool, "validate_project")
    assert clean["ok"] and clean["errors"] == [] and clean["missing_dependencies"] == []


async def test_run_tests_with_gut_and_gdunit4(call_tool, no_editor):
    project = no_editor["project"]
    is_error, text = await call_tool("run_tests")
    assert is_error and "No test framework" in text

    install_framework("gut", project)
    install_framework("gdUnit4", project)
    (project / "test").mkdir(exist_ok=True)
    (project / "test" / "test_player_gut.gd").write_text(GUT_TEST)
    (project / "test" / "math_gdunit_test.gd").write_text(GDUNIT_TEST)

    gut = await ok(call_tool, "run_tests", framework="gut", path="res://test/test_player_gut.gd")
    assert (gut["framework"], gut["total"], gut["passed"], gut["failed"]) == ("gut", 2, 1, 1)
    assert not gut["ok"]
    [failure] = gut["failures"]
    assert failure["test"] == "test_wrong_on_purpose"
    assert (failure["file"], failure["line"]) == ("res://test/test_player_gut.gd", 7)
    assert "multiplication" in failure["message"]

    only = await ok(call_tool, "run_tests", framework="gut", test_name="player_speed")
    assert only["ok"] and only["total"] == 1

    gdunit = await ok(call_tool, "run_tests", framework="gdunit4")
    assert (gdunit["total"], gdunit["passed"], gdunit["failed"]) == (2, 1, 1)
    [failure] = gdunit["failures"]
    assert failure["test"] == "test_fails_on_purpose"
    assert (failure["file"], failure["line"]) == ("res://test/math_gdunit_test.gd", 7)

    only = await ok(call_tool, "run_tests", framework="gdunit4", test_name="adds")
    assert only["ok"] and only["total"] == 1

    both = await ok(call_tool, "run_tests")  # auto: every installed framework
    assert [r["framework"] for r in both["runs"]] == ["gut", "gdunit4"]
    assert not both["ok"] and both["failed"] == 2


async def test_exports(call_tool, no_editor):
    project, exports = no_editor["project"], no_editor["exports"]
    empty = await ok(call_tool, "list_export_presets")
    assert empty["presets"] == [] and "hint" in empty
    (project / "export_presets.cfg").write_text(PRESETS)
    listed = await ok(call_tool, "list_export_presets")
    assert listed["presets"][0]["name"] == "Linux" and listed["godot_version"].startswith("4.")

    pack = await ok(call_tool, "export_project", preset="Linux", mode="pack")
    assert pack["output"] == str(exports / "demo.pck")
    assert (exports / "demo.pck").stat().st_size > 1000
    assert [f["path"] for f in pack["files"]] == [str(exports / "demo.pck")]

    for args, expected in [
        ({"preset": "Nope"}, "No export preset 'Nope'"),
        ({"preset": "Linux", "output": "/tmp/elsewhere/game.pck", "mode": "pack"}, "outside"),
        ({"preset": "Linux", "output": "game.exe", "mode": "pack"}, ".pck or .zip"),
    ]:
        is_error, text = await call_tool("export_project", **args)
        assert is_error and expected in text, text
    if not listed["templates_installed"]:
        is_error, text = await call_tool("export_project", preset="Linux")
        assert is_error and "export template" in text.lower() and "mode='pack'" in text
