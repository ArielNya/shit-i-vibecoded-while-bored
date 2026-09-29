# Character movement recipes (Godot 4.7)

Use `CharacterBody2D` / `CharacterBody3D` for players and enemies you move from code.
Set `velocity`, then call `move_and_slide()` in `_physics_process`. Add the input actions
first (`edit_input_map`): the scripts below use `move_left`, `move_right`, `jump` (2D) and
`move_forward`, `move_back`, `move_left`, `move_right`, `jump` (3D).

The body needs a `CollisionShape2D`/`CollisionShape3D` child with a shape, and the floor
needs collision too (a `StaticBody2D` with a shape, or a `TileMapLayer` whose TileSet has a
physics layer, see `create_tileset`).

## 2D platformer

```gdscript
extends CharacterBody2D

@export var speed := 220.0
@export var jump_velocity := -420.0
@export var coyote_time := 0.1

var _time_since_floor := 0.0


func _physics_process(delta: float) -> void:
	if is_on_floor():
		_time_since_floor = 0.0
	else:
		_time_since_floor += delta
		velocity += get_gravity() * delta

	if Input.is_action_just_pressed("jump") and _time_since_floor <= coyote_time:
		velocity.y = jump_velocity
		_time_since_floor = coyote_time + 1.0
	# Release early for a short hop.
	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= 0.5

	var direction := Input.get_axis("move_left", "move_right")
	velocity.x = move_toward(velocity.x, direction * speed, speed * 10.0 * delta)
	move_and_slide()
```

- In 2D, +y is down, so jumps are negative.
- For one-way platforms, enable `one_way_collision` on the platform's collision shape.

## 2D top-down

```gdscript
extends CharacterBody2D

@export var speed := 180.0


func _physics_process(_delta: float) -> void:
	var input := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = input * speed
	move_and_slide()
```

Set `motion_mode` to `MOTION_MODE_FLOATING` on the body for top-down games, so walls
don't count as floors.

## 3D third person (camera-relative)

Scene layout: `Player (CharacterBody3D)` with `CollisionShape3D` (CapsuleShape3D),
a mesh, and `CameraPivot (Node3D)` → `SpringArm3D` → `Camera3D`.

```gdscript
extends CharacterBody3D

@export var speed := 6.0
@export var jump_velocity := 5.0
@export var turn_speed := 10.0

@onready var pivot: Node3D = $CameraPivot


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
		var target := atan2(-direction.x, -direction.z)
		rotation.y = lerp_angle(rotation.y, target, turn_speed * delta)
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		velocity.z = move_toward(velocity.z, 0.0, speed)
	move_and_slide()
```

Keep the camera pivot from turning with the body: set `top_level = true` on the pivot
and follow the player's position each frame, or rotate the mesh instead of the body.

## Checking it works

Run the game (`run_project`), then `send_input` with `{"action": "move_right"}` for
some frames, and `get_live_properties` (filter `position`) or `wait_for` a condition, like
`is_on_floor` being true.
