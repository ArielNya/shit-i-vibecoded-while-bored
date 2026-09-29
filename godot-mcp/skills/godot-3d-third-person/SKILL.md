---
name: godot-3d-third-person
description: Build a 3D third-person controller and test level in Godot 4.7 through the godot-mcp tools — capsule player with camera-relative movement, orbit camera on a SpringArm3D, lit greybox level — and verify it by play-testing. Use when asked for a 3D character, third-person game or 3D prototype in Godot.
---

# 3D third-person prototype in Godot 4.7 (with godot-mcp)

## 1. Orient and input

1. `get_project_info` (renderer: Forward+ or Mobile for 3D; Compatibility works too).
2. `edit_input_map`: `move_forward` (W), `move_back` (S), `move_left` (A),
   `move_right` (D), `jump` (Space).

## 2. Level greybox (`res://levels/test_level.tscn`)

1. `new_scene` root `Node3D` named `TestLevel`.
2. Light and sky: `add_node` `DirectionalLight3D` (rotation `Vector3(-0.8, 0.6, 0)`,
   `shadow_enabled` true) and `WorldEnvironment` with an `Environment` resource
   (`background_mode` 2 = sky, with a `Sky` + `ProceduralSkyMaterial`), or keep it
   simple with `background_mode` 1 and a `background_color`.
3. Ground: `add_node` `CSGBox3D` named `Floor`, `size` `Vector3(40, 1, 40)`,
   `position` `Vector3(0, -0.5, 0)`, `use_collision` true. Add a few more CSGBox3D
   blocks as walls/steps (each with `use_collision` true).
4. `save_scene`, and `get_editor_screenshot` (3D view) to check it.

## 3. Player (`res://player/player_3d.tscn`)

Tree:

```
Player (CharacterBody3D)       group "player"
├── CollisionShape3D           CapsuleShape3D radius 0.4, height 1.8, position y 0.9
├── Body (MeshInstance3D)      CapsuleMesh radius 0.4, height 1.8, position y 0.9
└── CameraPivot (Node3D)       position y 1.5, top_level = true
    └── SpringArm3D            spring_length 4, rotation x -0.35
        └── Camera3D
```

Scripts: movement on the player, orbit on the pivot.

```gdscript
extends CharacterBody3D

@export var speed := 6.0
@export var jump_velocity := 5.0
@export var turn_speed := 12.0

@onready var pivot: Node3D = $CameraPivot
@onready var body: Node3D = $Body


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var view := pivot.global_transform.basis
	var direction := view.x * input.x + view.z * input.y
	direction.y = 0.0
	direction = direction.normalized()
	if direction != Vector3.ZERO:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
		body.rotation.y = lerp_angle(body.rotation.y, atan2(-direction.x, -direction.z), turn_speed * delta)
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		velocity.z = move_toward(velocity.z, 0.0, speed)
	move_and_slide()
	pivot.global_position = global_position + Vector3(0, 1.5, 0)
```

```gdscript
extends Node3D

@export var mouse_sensitivity := 0.003
@export var min_pitch := -1.2
@export var max_pitch := 0.4

@onready var arm: SpringArm3D = $SpringArm3D


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		rotation.y -= event.relative.x * mouse_sensitivity
		arm.rotation.x = clampf(arm.rotation.x - event.relative.y * mouse_sensitivity, min_pitch, max_pitch)
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
```

The SpringArm3D must not hit the player: set its `collision_mask` to the level's layer
only, or add the player to `excluded objects` from code (`arm.add_excluded_object(rid)`).

## 4. Put it together

`open_scene` the level, `add_node` with `scene` "res://player/player_3d.tscn" at
`Vector3(0, 1, 0)`, `save_scene`, set it as main scene.

## 5. Play-test

1. `validate_project`; `run_project`; `get_runtime_errors` empty.
2. `wait_for` a short time, then `get_live_properties` on `Player` (`position`): y about
   0 (standing on the floor), not falling.
3. `send_input` `move_forward` for 60 frames → position changed along -z (camera
   facing forward).
4. `get_game_screenshot` (window needed) to see the camera framing.

Falling through the floor: `use_collision` off on the CSG node, or the capsule's
collision shape missing. Camera inside walls: spring arm collision mask.
