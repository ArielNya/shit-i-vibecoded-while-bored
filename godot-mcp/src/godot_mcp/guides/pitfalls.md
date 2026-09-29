# Godot 3 → Godot 4.7 pitfalls

Most GDScript online (and in model training data) is Godot 3. These are the changes that
break code most often. When unsure, check the API with `get_class_docs`.

## Syntax

| Godot 3 | Godot 4.7 |
| --- | --- |
| `export var speed = 200` | `@export var speed := 200.0` |
| `onready var sprite = $Sprite` | `@onready var sprite: Sprite2D = $Sprite2D` |
| `tool` | `@tool` (first line) |
| `yield(get_tree().create_timer(1), "timeout")` | `await get_tree().create_timer(1.0).timeout` |
| `yield(anim, "animation_finished")` | `await anim.animation_finished` |
| `connect("pressed", self, "_on_pressed")` | `pressed.connect(_on_pressed)` |
| `emit_signal("died", cause)` | `died.emit(cause)` |
| `funcref(obj, "f")` | `obj.f` (a `Callable`) or `Callable(obj, "f")` |
| `setget set_hp, get_hp` | `var hp: int: set = set_hp, get = get_hp` (or inline `set(value):`) |
| `var x = 5 as int` everywhere | static typing: `var x: int = 5`, `var y := 5.0` |
| `str2var` / `var2str` | `str_to_var` / `var_to_str` |
| `rand_range(a, b)` | `randf_range(a, b)` / `randi_range(a, b)` |
| `deg2rad` / `rad2deg` | `deg_to_rad` / `rad_to_deg` |
| `stepify(x, s)` | `snappedf(x, s)` / `snapped(x, s)` |
| `PoolStringArray` | `PackedStringArray` |

## Nodes and classes

| Godot 3 | Godot 4.7 |
| --- | --- |
| `KinematicBody2D` / `KinematicBody` | `CharacterBody2D` / `CharacterBody3D` |
| `move_and_slide(velocity, Vector2.UP)` | set `velocity`, then `move_and_slide()` (no arguments, no return value) |
| `is_on_floor()` before moving | still `is_on_floor()`, updated by `move_and_slide()` |
| `Spatial` | `Node3D` |
| `Sprite` | `Sprite2D` (and `Sprite3D`) |
| `Position2D` | `Marker2D` |
| `TileMap` | `TileMapLayer` (one node per layer; `set_cell(coords, source_id, atlas_coords)`) |
| `Navigation2D` | `NavigationRegion2D` + `NavigationAgent2D` |
| `VisibilityNotifier2D` | `VisibleOnScreenNotifier2D` |
| `Light2D` | `PointLight2D` |
| `Particles2D` | `GPUParticles2D` |
| `ToolButton` | `Button` with `flat = true` |
| `Reference` | `RefCounted` |
| `File` / `Directory` | `FileAccess.open(...)` / `DirAccess.open(...)` (static constructors) |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `get_tree().change_scene("...")` | `get_tree().change_scene_to_file("res://...")` |
| `instance()` | `instantiate()` |
| `rect_position`, `rect_size` | `position`, `size` on `Control` |
| `margin_left` etc. | `offset_left` etc. |

## Physics and input

- Gravity comes from `get_gravity()` on physics bodies (it includes Area2D/Area3D
  overrides), instead of reading a project setting by hand.
- `Input.get_axis("move_left", "move_right")` and `Input.get_vector(...)` replace
  hand-written left/right subtraction.
- Actions used in code must exist in the Input Map (`edit_input_map`), or `Input` calls
  print errors.
- Collision layers are bits: `set_collision_layer_value(2, true)` uses the 1-based layer
  number shown in the editor.

## Checking your work

- `get_diagnostics` (editor) or `validate_project` (any time) after writing GDScript.
- `search_docs` finds where an API lives now, e.g. "raycast" or "change scene".

## Example: a Godot 4 script in the modern style

```gdscript
extends Node2D

signal exploded(position: Vector2)

@export var fuse_seconds := 1.5
@onready var timer := Timer.new()


func _ready() -> void:
	add_child(timer)
	timer.one_shot = true
	timer.timeout.connect(_on_timeout)
	timer.start(fuse_seconds)


func _on_timeout() -> void:
	exploded.emit(global_position)
	await get_tree().create_timer(0.1).timeout
	queue_free()
```
