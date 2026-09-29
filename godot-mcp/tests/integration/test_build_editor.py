"""M6 with the editor open: the build tools reuse the editor's binary and project, let it
rescan instead of importing a second time, and the exporting Godot doesn't start a second
MCP listener."""

import pytest

from godot_mcp.headless import Headless

from .test_build import GUT_TEST, PRESETS, install_framework

pytestmark = pytest.mark.anyio


async def test_validate_and_docs_use_the_editor(call, project_dir):
    result = await call("validate_project")
    assert {(e["file"], e.get("line")) for e in result["errors"]} >= {
        ("res://scripts/broken.gd", 4),
        ("res://scripts/broken.gd", 5),
    }
    # The editor keeps the caches current, so no `godot --import` ran.
    assert not (project_dir / ".godot" / "godot_mcp_import_stamp").exists()
    docs = await call("get_class_docs", class_name="Timer")
    assert "note" not in docs or "No editor" not in docs["note"]


async def test_tests_installed_behind_the_editors_back(call, project_dir):
    """GUT copied in from outside (not through MCP): the editor rescans before the run, so
    GutTest and the new test file are known."""
    install_framework("gut", project_dir)
    (project_dir / "test").mkdir(exist_ok=True)
    (project_dir / "test" / "test_player_gut.gd").write_text(GUT_TEST)
    result = await call("run_tests", test_name="player_speed")
    assert result["ok"] and result["total"] == 1 and result["framework"] == "gut"


async def test_export_while_the_editor_is_open(call, bridge, project_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GODOT_MCP_EXPORT_DIRS", str(tmp_path))
    (project_dir / "export_presets.cfg").write_text(PRESETS)
    pack = await call("export_project", preset="Linux", mode="pack", output="game.zip")
    assert (tmp_path / "game.zip").stat().st_size > 1000 and pack["output"].endswith("game.zip")

    # The export runs the editor too, with the plugin enabled: it must not start a listener.
    headless = Headless(bridge)
    command, project, editor = await headless.target()
    assert editor and project == project_dir.resolve()
    run = await headless.run(
        command, project, ["--export-pack", "Linux", str(tmp_path / "again.pck")], timeout=300
    )
    assert (tmp_path / "again.pck").exists()
    assert "godot-mcp: listening" not in run.output
