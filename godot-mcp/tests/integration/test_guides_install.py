"""M7: every ```gdscript block in the guides and skills compiles in the real engine, and
`godot-mcp install-addon` turns a blank project into one the plugin serves."""

import os
import queue
import re
import subprocess
import sys
import threading

import pytest

from godot_mcp.tools.guides import all_guides

from .test_build import call_tool, godot_bin, install_framework, no_editor, ok  # noqa: F401

pytestmark = pytest.mark.anyio

BLOCK = re.compile(r"```gdscript\n(.*?)```", re.DOTALL)
PRELOADED_SCENE = re.compile(r'preload\("(res://[^"]+\.tscn)"\)')
STUB_SCENE = '[gd_scene format=3]\n\n[node name="Stub" type="Node2D"]\n'


def snippets() -> dict[str, str]:
    out = {}
    for guide in all_guides().values():
        for i, code in enumerate(BLOCK.findall(guide.text)):
            out[f"{guide.name.replace('-', '_')}_{i}"] = code
    return out


async def test_every_gdscript_block_compiles(call_tool, no_editor):  # noqa: F811
    project = no_editor["project"]
    code = snippets()
    assert len(code) >= 20
    if any("GutTest" in c for c in code.values()):
        install_framework("gut", project)
    if any("GdUnitTestSuite" in c for c in code.values()):
        install_framework("gdUnit4", project)
    folder = project / "guide_snippets"
    folder.mkdir()
    for name, source in code.items():
        (folder / f"{name}.gd").write_text(source)
        for scene in PRELOADED_SCENE.findall(source):  # the guides preload scenes they tell
            target = project / scene.removeprefix("res://")  # you to create; stub them
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(STUB_SCENE)
    result = await ok(call_tool, "validate_project")
    errors = [e for e in result["errors"] if e["file"].startswith("res://guide_snippets/")]
    assert errors == [], errors


def test_install_addon_into_a_blank_project(godot_bin, tmp_path):  # noqa: F811
    project = tmp_path / "blank game"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n\n[application]\n\nconfig/name="Blank"\n'
        'config/features=PackedStringArray("4.7")\n'
    )
    installed = subprocess.run(
        [sys.executable, "-m", "godot_mcp.server", "install-addon", str(project)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert "Installed the plugin" in installed.stdout
    assert "res://addons/godot_mcp/plugin.cfg" in (project / "project.godot").read_text()

    # A fresh editor on it loads the plugin, which starts listening.
    env = {**os.environ, "GODOT_MCP_TOKEN_FILE": str(tmp_path / "token")}
    proc = subprocess.Popen(
        [os.environ["GODOT_BIN"], "--headless", "--editor", "--path", str(project),
         "--", "--mcp-port=0"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )  # fmt: skip
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in proc.stdout], daemon=True).start()
    seen = []
    try:
        while True:
            line = lines.get(timeout=120)
            seen.append(line)
            if line.startswith("godot-mcp: listening on"):
                break
    except queue.Empty:
        pytest.fail("the plugin never started:\n" + "".join(seen))
    finally:
        proc.kill()
        proc.wait()
    assert (project / "addons" / "godot_mcp" / "plugin.cfg").is_file()
