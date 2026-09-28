"""M3: run the game from a headless editor and observe/drive it."""

import os
import subprocess

import pytest

pytestmark = pytest.mark.anyio

NOISY = """extends Node

signal ticked

var counter := 0


func _ready() -> void:
\tprint("hello from the game")
\tpush_warning("careful now")


func _physics_process(_delta: float) -> void:
\tcounter += 1
\tif counter == 30:
\t\tticked.emit()
\t\tvar items: Array = []
\t\tprint(items[3])
"""


@pytest.fixture
async def stopped(call):
    yield
    await call("stop_project")


async def test_run_status_and_stop(call, call_error, stopped):
    status = await call("get_run_status")
    assert status["running"] is False
    run = await call("run_project")
    assert run["running"] is True and run["headless"] is True
    assert run["scene"] == "res://scenes/main.tscn" and run["pid"] > 0
    status = await call("get_run_status")
    assert status["running"] and status["runtime_connected"] and status["frame"] >= 0
    tree = await call("get_live_tree", max_depth=1)
    assert [n["path"] for n in tree["nodes"]] == [".", "Player", "Background", "HUD"]
    assert "GameState" in tree["autoloads"]

    # Running again restarts the game.
    again = await call("run_project")
    assert again["running"] and again["run"] == run["run"] + 1

    stop = await call("stop_project")
    assert stop["stopped"] is True
    assert (await call("get_run_status"))["running"] is False
    assert "not running" in await call_error("get_live_tree")
    assert (await call("stop_project"))["stopped"] is False


async def test_output_errors_and_signals(call, stopped):
    await call("write_script", path="res://t/noisy.gd", content=NOISY)
    await call("new_scene", path="res://t/noisy.tscn", root_type="Node")
    await call("attach_script", node=".", path="res://t/noisy.gd")
    await call("save_scene")

    run = await call("run_project", scene="res://t/noisy.tscn")
    assert run["running"]
    fired = await call("wait_for", until="signal", node=".", signal="ticked", timeout=5)
    assert fired["met"] is True
    await call("wait_for", until="frames", frames=5)

    output = await call("get_output")
    messages = [e["message"] for e in output["entries"]]
    assert "hello from the game" in messages
    levels = {e["level"] for e in output["entries"]}
    assert {"stdout", "warning"} <= levels

    errors = await call("get_runtime_errors")
    assert len(errors["errors"]) == 1
    err = errors["errors"][0]
    assert err["at"] == "res://t/noisy.gd:18"  # the print(items[3]) line
    assert "index" in err["message"].lower() or "out of bounds" in err["message"].lower()
    assert err["backtrace"][0].startswith("res://t/noisy.gd:18")
    assert [w["message"] for w in errors["warnings"]] == ["careful now"]

    # Cursors: nothing new since the last call.
    later = await call("get_runtime_errors", since=errors["next_since"])
    assert later["errors"] == [] and later["warnings"] == []
    only_stdout = await call("get_output", levels=["stdout"])
    assert all(e["level"] == "stdout" for e in only_stdout["entries"])

    # The log survives the game ending.
    await call("stop_project")
    assert (await call("get_runtime_errors"))["errors"][0]["at"] == "res://t/noisy.gd:18"


async def test_input_live_properties_and_wait(call, call_error, stopped):
    await call("run_project", scene="res://scenes/main.tscn")
    start = await call("get_live_properties", node="Player", filter="position")
    x0 = float(start["properties"][0]["value"].removeprefix("Vector2(").split(",")[0])

    # Hold right (ui_right is what player.gd reads) for half a second: speed 250 px/s.
    await call("send_input", events=[{"action": "ui_right"}], frames=30)
    moved = await call("get_live_properties", node="Player", filter="position")
    x1 = float(moved["properties"][0]["value"].removeprefix("Vector2(").split(",")[0])
    assert 90 < x1 - x0 < 160

    # press / wait / release: the player keeps moving until released.
    await call("set_live_properties", node="Player", properties={"speed": 600})
    await call("send_input", events=[{"action": "ui_right"}], mode="press")
    reached = await call(
        "wait_for", until="property", node="Player", property="position:x", op=">",
        value=str(x1 + 200), timeout=5,
    )  # fmt: skip
    assert reached["met"] is True and reached["value"] > x1 + 200
    await call("send_input", events=[{"action": "ui_right"}], mode="release")

    never = await call("wait_for", until="node_exists", node="Boss", timeout=0.3)
    assert never["met"] is False and never["waited_seconds"] >= 0.3
    assert (await call("wait_for", until="node_gone", node="Boss", timeout=1))["met"] is True
    assert (await call("wait_for", until="seconds", seconds=0.2))["waited_seconds"] >= 0.2

    perf = await call("get_performance")
    assert perf["nodes"] >= 7 and perf["physics_2d_active"] >= 1

    assert "unknown input action 'fly'" in await call_error(
        "send_input", events=[{"action": "fly"}]
    )
    assert "no property 'sped'" in await call_error(
        "set_live_properties", node="Player", properties={"sped": 1}
    )
    assert "No node 'Nope'" in await call_error("get_live_properties", node="Nope")
    assert "has no signal 'boom'" in await call_error(
        "wait_for", until="signal", node="Player", signal="boom"
    )
    assert "headless" in await call_error("get_game_screenshot")


async def test_run_errors(call, call_error):
    assert "No scene at" in await call_error("run_project", scene="res://nope.tscn")
    assert "no display" in await call_error("run_project", display="window")
    await call("open_scene", path="res://scenes/main.tscn")
    await call("add_node", type="Node", name="Unsaved")
    assert "unsaved changes" in await call_error("run_project", scene="current")
    await call("undo")


async def test_export_leaves_the_runtime_out(project_dir, tmp_path):
    (project_dir / "export_presets.cfg").write_text(
        '[preset.0]\n\nname="Linux"\nplatform="Linux"\nrunnable=true\n'
        'export_filter="all_resources"\nexport_path="build/game.x86_64"\n\n[preset.0.options]\n\n'
    )
    pck = tmp_path / "game.pck"
    subprocess.run(
        [os.environ["GODOT_BIN"], "--headless", "--path", str(project_dir),
         "--export-pack", "Linux", str(pck)],
        capture_output=True, timeout=180, check=True,
    )  # fmt: skip
    data = pck.read_bytes()
    assert b"GameState" in data  # other autoloads are exported as usual
    assert b"McpRuntime" not in data  # ours is not
    assert "McpRuntime" in (project_dir / "project.godot").read_text()  # and it's restored
