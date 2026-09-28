"""M2 acceptance: build a small 2D game with a moving player using only MCP tools, then
run the saved scene in a separate Godot process and check the player really moves."""

import os
import re
import subprocess

import pytest

pytestmark = pytest.mark.anyio

CONTROLLER = """extends CharacterBody2D

const SPEED := 200.0
const JUMP_VELOCITY := -400.0


func _physics_process(delta: float) -> void:
\tif not is_on_floor():
\t\tvelocity += get_gravity() * delta
\tif Input.is_action_just_pressed("jump") and is_on_floor():
\t\tvelocity.y = JUMP_VELOCITY
\tvar direction := Input.get_axis("move_left", "move_right")
\tvelocity.x = direction * SPEED
\tmove_and_slide()
"""

# Test driver (also written through MCP): waits for the player to land, holds
# move_right for a second, then prints where the player ended up.
DRIVER = """extends Node

var _frames := 0
var _start_x := 0.0


func _physics_process(_delta: float) -> void:
\tvar player := get_tree().current_scene.get_node_or_null("Player") as CharacterBody2D
\tif player == null:
\t\treturn
\t_frames += 1
\tif _frames == 60:
\t\t_start_x = player.position.x
\t\tprint("E2E_LANDED ", player.is_on_floor())
\t\tInput.action_press("move_right")
\tif _frames == 120:
\t\tprint("E2E_RESULT %.1f %.1f %s" % [_start_x, player.position.x, player.is_on_floor()])
\t\tget_tree().quit()
"""


async def test_build_and_run_a_moving_player(call, project_dir):
    # Input actions
    for action, keys in {
        "move_left": ["A", "Left"],
        "move_right": ["D", "Right"],
        "jump": ["Space"],
    }.items():
        await call(
            "edit_input_map", action=action, add_events=[{"type": "key", "key": k} for k in keys]
        )

    # Scene: player with sprite + collision, and a floor
    await call("new_scene", path="res://game/level.tscn", root_type="Node2D", root_name="Level")
    await call(
        "add_node", type="CharacterBody2D", name="Player", properties={"position": [100, 100]}
    )
    await call(
        "add_node", parent="Player", type="Sprite2D", properties={"texture": "res://icon.svg"}
    )
    await call(
        "add_node",
        parent="Player",
        type="CollisionShape2D",
        properties={
            "shape": {
                "_type": "Resource",
                "class": "RectangleShape2D",
                "properties": {"size": [64, 64]},
            }
        },
    )
    await call("add_node", type="StaticBody2D", name="Floor", properties={"position": [400, 300]})
    await call(
        "add_node",
        parent="Floor",
        type="CollisionShape2D",
        properties={
            "shape": {
                "_type": "Resource",
                "class": "RectangleShape2D",
                "properties": {"size": "Vector2(2000, 20)"},
            }
        },
    )
    await call("add_node", type="Camera2D", properties={"position": [400, 200]})

    # Movement script, attached to the player
    await call(
        "create_script",
        path="res://game/player_controller.gd",
        extends="CharacterBody2D",
        attach_to="Player",
    )
    written = await call("write_script", path="res://game/player_controller.gd", content=CONTROLLER)
    assert written["errors"] == [] and "warnings" not in written

    await call("write_script", path="res://game/e2e_driver.gd", content=DRIVER)
    await call("set_project_setting", name="autoload/E2EDriver", value="res://game/e2e_driver.gd")
    await call(
        "set_project_setting", name="application/run/main_scene", value="res://game/level.tscn"
    )

    saved = await call("save_scene")
    assert saved["unsaved"] is False
    diagnostics = await call("get_diagnostics", path="res://game")
    assert diagnostics["error_count"] == 0, diagnostics

    tree = [n["path"] for n in (await call("get_scene_tree"))["nodes"]]
    assert tree == [
        ".", "Player", "Player/Sprite2D", "Player/CollisionShape2D",
        "Floor", "Floor/CollisionShape2D", "Camera2D",
    ]  # fmt: skip

    # Run the saved game in its own Godot process (not the editor).
    run = subprocess.run(
        [os.environ["GODOT_BIN"], "--headless", "--path", str(project_dir), "--quit-after", "900"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = run.stdout + run.stderr
    assert "SCRIPT ERROR" not in output, output
    assert "E2E_LANDED true" in output, output
    match = re.search(r"E2E_RESULT (-?[\d.]+) (-?[\d.]+) (\w+)", output)
    assert match, output
    start, end, on_floor = float(match[1]), float(match[2]), match[3]
    print(f"player x: {start} -> {end} (on floor: {on_floor})")
    assert end - start > 100, f"player moved only {end - start:.1f}px"  # ~200 px/s for 1 s
    assert on_floor == "true"
