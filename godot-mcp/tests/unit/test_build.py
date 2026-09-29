"""Build/headless helpers that don't need Godot: JUnit parsing, presets, output errors,
path allowlists, binary and project discovery."""

import os
import stat

import pytest

from godot_mcp.headless import HeadlessError, addon_dir, find_godot, find_project, output_errors
from godot_mcp.tools._common import ToolError
from godot_mcp.tools.build import _allowed_output, parse_junit, read_presets

GUT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="GutTests" failures="1" tests="3" >
  <testsuite name="test/test_math.gd" tests="3" failures="1" skipped="1" >
    <testcase name="test_adds" assertions="1" status="pass" classname="test/test_math.gd"/>
    <testcase name="test_later" assertions="0" status="pending" classname="test/test_math.gd">
      <skipped message="pending"/></testcase>
    <testcase name="test_fails" assertions="1" status="fail" classname="test/test_math.gd">
      <failure message="failed"><![CDATA[[4] expected to equal [5]:  multiplication
            at line 7]]></failure></testcase>
  </testsuite>
</testsuites>"""

GDUNIT_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<testsuites id="x" name="report_1" tests="2" failures="1">
  <testsuite id="0" name="math_test" package="test" tests="2" failures="1" errors="0">
    <testcase name="test_adds" classname="math_test" time="0.010"></testcase>
    <testcase name="test_fails" classname="math_test" time="0.012">
      <failure message="FAILED: res://test/math_test.gd:7" type="FAILURE">
<![CDATA[
Expecting:
 5
 but was
 4
]]></failure></testcase>
  </testsuite>
</testsuites>"""


def test_parse_gut_junit():
    result = parse_junit(GUT_XML, "gut")
    assert (result["total"], result["passed"], result["failed"], result["skipped"]) == (3, 1, 1, 1)
    [failure] = result["failures"]
    assert failure["test"] == "test_fails" and "multiplication" in failure["message"]
    assert (failure["file"], failure["line"]) == ("res://test/test_math.gd", 7)


def test_parse_gdunit_junit():
    result = parse_junit(GDUNIT_XML, "gdunit4")
    assert (result["total"], result["passed"], result["failed"]) == (2, 1, 1)
    [failure] = result["failures"]
    assert (failure["file"], failure["line"]) == ("res://test/math_test.gd", 7)
    assert "but was" in failure["message"]


def test_read_presets(tmp_path):
    assert read_presets(tmp_path) == []
    (tmp_path / "export_presets.cfg").write_text(
        '[preset.0]\n\nname="Linux \\"desktop\\""\nplatform="Linux"\nrunnable=true\n'
        'export_path="build/game.x86_64"\n\n[preset.0.options]\n\nbinary_format/embed_pck=false\n'
        '\n[preset.1]\n\nname="Web"\nplatform="Web"\nrunnable=false\n'
    )
    presets = read_presets(tmp_path)
    assert [p["name"] for p in presets] == ['Linux "desktop"', "Web"]
    assert presets[0]["runnable"] is True and presets[0]["export_path"] == "build/game.x86_64"
    assert "binary_format/embed_pck" not in presets[0]  # options aren't presets


def test_output_errors_keeps_messages_not_locations():
    output = """Godot Engine v4.7.2.stable.official
ERROR: Cannot export project with preset "Linux" due to configuration errors:
No export template found at the expected path:
/x/linux_release.x86_64

   at: _fs_changed (editor/editor_node.cpp:1401)
WARNING: something harmless
     at: somewhere (a.cpp:1)
SCRIPT ERROR: Parse Error: bad
   at: GDScript::reload (res://a.gd:3)
ERROR: Cannot export project with preset "Linux" due to configuration errors:
No export template found at the expected path:
/x/linux_release.x86_64
"""
    assert output_errors(output) == [
        'Cannot export project with preset "Linux" due to configuration errors:\n'
        "No export template found at the expected path:\n/x/linux_release.x86_64",
        "Parse Error: bad",
    ]


def test_export_output_must_stay_in_export_dirs(tmp_path, monkeypatch):
    allowed = tmp_path / "out"
    monkeypatch.setenv("GODOT_MCP_EXPORT_DIRS", str(allowed))
    preset = {"export_path": "build/game.x86_64"}
    assert _allowed_output("", preset, "release") == allowed / "game.x86_64"
    assert _allowed_output("", preset, "pack") == allowed / "game.pck"
    assert _allowed_output("web/index.html", preset, "release") == allowed / "web/index.html"
    for bad in ("../escape.pck", str(tmp_path / "other" / "x.pck")):
        with pytest.raises(ToolError, match="outside"):
            _allowed_output(bad, preset, "pack")
    link = allowed / "link"
    allowed.mkdir()
    link.symlink_to(tmp_path)
    with pytest.raises(ToolError, match="outside"):
        _allowed_output("link/x.pck", preset, "pack")
    with pytest.raises(ToolError, match=r"\.pck or \.zip"):
        _allowed_output("game.exe", preset, "pack")


def test_find_project(tmp_path, monkeypatch):
    monkeypatch.delenv("GODOT_MCP_PROJECT", raising=False)
    project = tmp_path / "game"
    (project / "scenes").mkdir(parents=True)
    (project / "project.godot").write_text("")
    monkeypatch.chdir(project / "scenes")
    assert find_project() == project.resolve()  # found upwards from the working directory
    assert find_project(str(tmp_path)) == tmp_path.resolve()  # the editor's project wins
    monkeypatch.setenv("GODOT_MCP_PROJECT", str(project / "project.godot"))
    assert find_project(str(tmp_path)) == project.resolve()  # an explicit one wins over both
    monkeypatch.setenv("GODOT_MCP_PROJECT", str(tmp_path))
    with pytest.raises(HeadlessError, match="no project.godot"):
        find_project()
    monkeypatch.delenv("GODOT_MCP_PROJECT")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(HeadlessError, match="--project"):
        find_project()


def test_find_godot(tmp_path, monkeypatch):
    binary = tmp_path / "Godot_v4.7.2"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("GODOT_BIN", str(binary))
    assert find_godot("/elsewhere/godot") == [str(binary)]
    monkeypatch.setenv("GODOT_BIN", str(tmp_path / "missing"))
    with pytest.raises(HeadlessError, match="isn't a file"):
        find_godot()
    monkeypatch.delenv("GODOT_BIN")
    assert find_godot(str(binary)) == [str(binary)]  # the connected editor's binary
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("godot_mcp.headless._install_candidates", lambda: [])
    with pytest.raises(HeadlessError, match="--godot-bin"):
        find_godot()


def test_addon_is_found_from_the_source_tree():
    assert (addon_dir() / "headless" / "runner.gd").is_file()
    assert os.path.isfile(addon_dir() / "plugin.cfg")
