---
name: godot-2d-platformer
description: Build a playable 2D platformer in Godot 4.7 through the godot-mcp tools — player with run/jump, tile level, collectibles, camera, HUD — and verify it by play-testing. Use when asked to make a 2D platformer or side-scroller in Godot.
---

# 2D platformer in Godot 4.7 (with godot-mcp)

Work in small steps and check each one: `get_diagnostics` after every script,
`save_scene` after every scene, and play-test with `run_project` + `send_input`.

## 1. Orient

1. `get_project_info`: Godot version, main scene, existing input actions, window size.
2. `list_files` to see what exists. Reuse art the user already has (`import_asset` for
   new files).
3. If the project is new, set a pixel-art friendly window if the art is small:
   `display/window/size/viewport_width` 640, `_height` 360,
   `display/window/stretch/mode` "canvas_items", and for pixel art
   `rendering/textures/canvas_textures/default_texture_filter` 0.

## 2. Input actions

`edit_input_map` for `move_left` (A, Left), `move_right` (D, Right), `jump` (Space, W,
Up). Code that uses an action which doesn't exist prints errors.

## 3. Player scene (`res://player/player.tscn`)

1. `new_scene` root `CharacterBody2D` named `Player`, `set_groups` → `player`.
2. `add_node` `CollisionShape2D` with `{"_type": "Resource", "class":
   "CapsuleShape2D", "properties": {"radius": 6, "height": 20}}`.
3. `add_node` `Sprite2D` (texture from the project, or `res://icon.svg` scaled 0.15 as a
   placeholder) or an `AnimatedSprite2D` with a `SpriteFrames` resource.
4. `add_node` `Camera2D` as a child of the player, `position_smoothing_enabled` true.
5. `write_script` `res://player/player.gd`, `attach_script` to the root, `save_scene`.

```gdscript
extends CharacterBody2D

signal died

@export var speed := 160.0
@export var jump_velocity := -330.0
@export var coyote_time := 0.1

var _air_time := 0.0


func _physics_process(delta: float) -> void:
	if is_on_floor():
		_air_time = 0.0
	else:
		_air_time += delta
		velocity += get_gravity() * delta
	if Input.is_action_just_pressed("jump") and _air_time <= coyote_time:
		velocity.y = jump_velocity
		_air_time = coyote_time + 1.0
	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= 0.5
	var direction := Input.get_axis("move_left", "move_right")
	velocity.x = move_toward(velocity.x, direction * speed, speed * 8.0 * delta)
	move_and_slide()
	if global_position.y > 2000.0:
		died.emit()
```

## 4. Level (`res://levels/level_1.tscn`)

1. Tiles: `import_asset` the tile sheet (or have the user provide one), then
   `create_tileset` with `collision` "all" or `solid_tiles` for the ground tiles.
2. `new_scene` root `Node2D` named `Level1`; `add_node` `TileMapLayer` named `Ground` with
   `tile_set` = the TileSet path.
3. Draw the level with `set_tiles` `grid` + `legend` (rows top to bottom, 1 char = 1
   tile). Leave gaps to jump over and platforms at reachable heights: with the values
   above the player jumps about 3 tiles (16 px tiles) high and 5 wide.
4. Instance the player: `add_node` with `scene` "res://player/player.tscn", position
   above the floor.
5. `save_scene`; set `application/run/main_scene` to it.

## 5. Collectibles and HUD

Coin scene (`Area2D` + `CollisionShape2D` + sprite, script below) instanced a few times;
score in an autoload (`autoload/GameState` = `"*res://game_state.gd"`); a `CanvasLayer`
with a `Label` that listens to `score_changed`.

```gdscript
extends Area2D

@export var points := 1


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node2D) -> void:
	if body.is_in_group("player"):
		var state := get_node_or_null("/root/GameState")
		if state != null:
			state.call("add_points", points)
		queue_free()
```

```gdscript
extends Node

signal score_changed(score: int)

var score := 0


func add_points(points: int) -> void:
	score += points
	score_changed.emit(score)
```

## 6. Play-test (don't skip)

1. `validate_project`, fix everything it reports.
2. `run_project`; `get_runtime_errors` must be empty.
3. `wait_for` `seconds` 1, then `get_live_properties` on the player (filter
   `velocity`): `velocity.y` must be 0, i.e. it landed. (`is_on_floor()` is a method,
   not a property; to wait on it, keep a `var grounded := is_on_floor()` updated in
   `_physics_process` and `wait_for` that.)
4. `send_input` `move_right` for 60 frames, then `get_live_properties` `position`: it
   must have moved right and not fallen through.
5. `send_input` `jump` and check `position:y` went up.
6. `get_game_screenshot` (needs a window) to look at it; `stop_project`.

If the player falls through: the TileSet has no physics layer, or the collision shape
is missing. If it can't jump: the `jump` action is missing or `is_on_floor()` is never
true (floor collision).
