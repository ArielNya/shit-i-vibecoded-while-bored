"""M3 acceptance: the fix-errors loop, through MCP tools only.

Build a small game whose movement script has a bug the static checker can't see (a
mistyped node path), run it, play-test it, read the runtime error with file:line, fix
the script, rerun and confirm the player now moves."""

import pytest

pytestmark = pytest.mark.anyio

BUGGY = """extends CharacterBody2D

const SPEED := 200.0


func _physics_process(delta: float) -> void:
\tif not is_on_floor():
\t\tvelocity += get_gravity() * delta
\tvar direction := Input.get_axis("move_left", "move_right")
\tvar sprite: Sprite2D = get_node_or_null("Sprit")
\tsprite.flip_h = direction < 0
\tvelocity.x = direction * SPEED
\tmove_and_slide()
"""


def x_of(props):
    value = next(p["value"] for p in props["properties"] if p["name"] == "position")
    return float(value.removeprefix("Vector2(").split(",")[0])


async def test_fix_errors_loop(call):
    # --- build ------------------------------------------------------------------------
    for action, key in {"move_left": "Left", "move_right": "Right"}.items():
        await call("edit_input_map", action=action, add_events=[{"type": "key", "key": key}])
    await call("new_scene", path="res://game/level.tscn", root_type="Node2D")
    await call(
        "add_node", type="CharacterBody2D", name="Player", properties={"position": [100, 250]}
    )
    await call(
        "add_node", parent="Player", type="Sprite2D", properties={"texture": "res://icon.svg"}
    )
    await call(
        "add_node", parent="Player", type="CollisionShape2D",
        properties={"shape": {"_type": "Resource", "class": "RectangleShape2D",
                              "properties": {"size": [64, 64]}}},
    )  # fmt: skip
    await call("add_node", type="StaticBody2D", name="Floor", properties={"position": [400, 300]})
    await call(
        "add_node", parent="Floor", type="CollisionShape2D",
        properties={"shape": {"_type": "Resource", "class": "RectangleShape2D",
                              "properties": {"size": [2000, 20]}}},
    )  # fmt: skip
    await call("write_script", path="res://game/player.gd", content=BUGGY)
    await call("attach_script", node="Player", path="res://game/player.gd")
    await call("save_scene")
    # The static check is clean: this bug only shows up at runtime.
    assert (await call("get_diagnostics", path="res://game/player.gd"))["error_count"] == 0

    # --- run and play-test: it's broken -------------------------------------------------
    run = await call("run_project", scene="res://game/level.tscn")
    assert run["running"]
    start = x_of(await call("get_live_properties", node="Player", filter="position"))
    await call("send_input", events=[{"action": "move_right"}], frames=30)
    after = x_of(await call("get_live_properties", node="Player", filter="position"))
    assert abs(after - start) < 1, "the buggy player should not move"

    errors = (await call("get_runtime_errors"))["errors"]
    assert errors, "the null access should be reported"
    bug = errors[0]
    print("runtime error seen by the agent:", bug)
    assert bug["at"] == "res://game/player.gd:11"
    assert "flip_h" in bug["message"] and "null" in bug["message"].lower()
    assert bug["count"] > 1  # once per physics frame

    # --- fix it at the reported line and rerun ------------------------------------------
    source = await call("read_script", path="res://game/player.gd", start_line=10, end_line=11)
    assert "Sprit" in source["text"]
    fixed = await call(
        "edit_script",
        path="res://game/player.gd",
        old_text='get_node_or_null("Sprit")',
        new_text='get_node_or_null("Sprite2D")',
    )
    assert fixed["errors"] == []

    rerun = await call("run_project", scene="res://game/level.tscn")
    assert rerun["run"] == run["run"] + 1
    await call("wait_for", until="frames", frames=20)  # land on the floor
    start = x_of(await call("get_live_properties", node="Player", filter="position"))
    await call("send_input", events=[{"action": "move_right"}], mode="press")
    moved = await call(
        "wait_for", until="property", node="Player", property="position:x", op=">",
        value=str(start + 150), timeout=5,
    )  # fmt: skip
    await call("send_input", events=[{"action": "move_right"}], mode="release")
    assert moved["met"] is True, moved
    assert (await call("get_runtime_errors"))["errors"] == []
    flipped = await call("get_live_properties", node="Player/Sprite2D", filter="flip_h")
    assert flipped["properties"] == []  # still false: moving right doesn't flip
    await call("stop_project")
