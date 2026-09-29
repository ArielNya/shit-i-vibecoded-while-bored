"""M5 acceptance: a tile-based level with imported pixel art, through MCP tools only.
Runs the editor with a window (Xvfb) so the result can be screenshotted."""

import base64
import os

import pytest

from .pixel_art import tile_sheet

pytestmark = pytest.mark.anyio

EDITOR_OPTIONS = {"display": True}

PLAYER = """extends CharacterBody2D

const SPEED := 120.0
var grounded := false


func _physics_process(delta: float) -> void:
\tif not is_on_floor():
\t\tvelocity += get_gravity() * delta
\tvelocity.x = Input.get_axis("move_left", "move_right") * SPEED
\tmove_and_slide()
\tgrounded = is_on_floor()
"""

LEVEL = [
    "                                        ",
    "                                        ",
    "                   ======               ",
    "                                        ",
    "        ====                            ",
    "                                        ",
    "########################################",
    "########################################",
]


async def test_tile_level_with_imported_pixel_art(call, call_image, bridge, tmp_path, monkeypatch):
    art = tmp_path / "art"
    art.mkdir()
    (art / "tiles.png").write_bytes(tile_sheet())
    monkeypatch.setenv("GODOT_MCP_ASSET_DIRS", str(art))

    # Pixel art: import the sheet, render it crisp.
    await call("import_asset", source="tiles.png", path="res://art/tiles.png")
    await call(
        "set_project_setting",
        name="rendering/textures/canvas_textures/default_texture_filter",
        value="0",
    )
    tileset = await call(
        "create_tileset",
        path="res://art/tiles.tres",
        texture="res://art/tiles.png",
        tile_size=[16, 16],
        collision="all",
    )
    assert tileset["tiles"] == [[0, 0], [1, 0], [2, 0]]

    # The level: a TileMapLayer painted from ASCII rows.
    await call("edit_input_map", action="move_right", add_events=[{"type": "key", "key": "Right"}])
    await call("edit_input_map", action="move_left", add_events=[{"type": "key", "key": "Left"}])
    await call("new_scene", path="res://levels/level1.tscn", root_type="Node2D")
    await call(
        "add_node", type="TileMapLayer", name="Ground",
        properties={"tile_set": "res://art/tiles.tres"},
    )  # fmt: skip
    painted = await call("set_tiles", node="Ground", grid=LEVEL, legend={"#": [2, 0], "=": [1, 0]})
    assert painted["cells"] == 80 + 4 + 6

    # A player standing above the floor (floor top is y = 6 * 16 = 96).
    await call("add_node", type="CharacterBody2D", name="Player", properties={"position": [40, 40]})
    await call(
        "add_node", parent="Player", type="CollisionShape2D",
        properties={"shape": {"_type": "Resource", "class": "RectangleShape2D",
                              "properties": {"size": [12, 14]}}},
    )  # fmt: skip
    await call(
        "add_node", parent="Player", type="Sprite2D",
        properties={"texture": "res://icon.svg", "scale": [0.2, 0.2]},
    )  # fmt: skip
    await call("write_script", path="res://levels/player.gd", content=PLAYER)
    await call("attach_script", node="Player", path="res://levels/player.gd")
    await call("add_node", type="Camera2D", properties={"position": [320, 60], "zoom": [1, 1]})
    await call("save_scene")
    assert (await call("get_diagnostics", path="res://levels"))["error_count"] == 0

    # Play it: the player must land on the tiles and walk along them.
    run = await call("run_project", scene="res://levels/level1.tscn")
    assert run["running"] and not run["headless"]
    try:
        landed = await call(
            "wait_for", until="property", node="Player", property="grounded", value="true",
            timeout=5,
        )  # fmt: skip
        assert landed["met"], landed
        y = await call("get_live_properties", node="Player", filter="position")
        y_on_floor = float(y["properties"][0]["value"].rstrip(")").split(",")[1])
        assert 80 < y_on_floor < 96  # resting on the floor tiles, not fallen through

        await call("send_input", events=[{"action": "move_right"}], frames=60)
        walked = await call("get_live_properties", node="Player", filter="position")
        x, y2 = walked["properties"][0]["value"].removeprefix("Vector2(").rstrip(")").split(",")
        assert float(x) > 120 and abs(float(y2) - y_on_floor) < 1  # moved along the floor
        assert (await call("get_runtime_errors"))["errors"] == []

        shot = await call_image("get_game_screenshot", size=640)
        assert shot["width"] == 640
        if out := os.environ.get("GODOT_MCP_SHOT_DIR"):
            reply = await bridge.call("get_game_screenshot", {"size": 640})
            with open(f"{out}/m5_level.png", "wb") as f:
                f.write(base64.b64decode(reply["image_base64"]))
    finally:
        await call("stop_project")
