# Physics bodies, areas and layers

## Which node

| Node | Use for |
| --- | --- |
| `StaticBody2D/3D` | floors, walls: never moves by itself |
| `AnimatableBody2D/3D` | moving platforms (moved by code or an AnimationPlayer; carries bodies on it) |
| `CharacterBody2D/3D` | player, enemies: moved by code with `move_and_slide()` |
| `RigidBody2D/3D` | crates, balls: moved by the physics engine; push with `apply_impulse()` |
| `Area2D/3D` | triggers, pickups, hitboxes: detects overlaps, doesn't collide |

Every body/area needs a `CollisionShape2D`/`3D` (or `CollisionPolygon`) child with a
shape resource, e.g. `{"_type": "Resource", "class": "CircleShape2D", "properties":
{"radius": 12}}` in `add_node`.

## Layers and masks

- `collision_layer`: which layers this object **is on**.
- `collision_mask`: which layers it **looks at** (collides with / detects).
- Both are bit masks; layer N is bit N-1. In code, use the 1-based helpers:
  `set_collision_layer_value(3, true)`.
- Name layers in project settings (`layer_names/2d_physics/layer_1 = "world"`) with
  `set_project_setting`, so they show up by name in the inspector.

A typical setup: 1 world, 2 player, 3 enemies, 4 pickups. The player is on 2 and masks
1, 3 and 4. A pickup is an Area2D on 4 masking 2.

## Pickups and hitboxes with Area2D

```gdscript
extends Area2D

signal collected

@export var points := 10


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node2D) -> void:
	if body.is_in_group("player"):
		collected.emit()
		queue_free()
```

Put the player in the `player` group (`set_groups`) so the check works.

## Rigid bodies

```gdscript
extends RigidBody2D


func kick(direction: Vector2) -> void:
	apply_central_impulse(direction.normalized() * 400.0)
```

Don't set a RigidBody's `position` every frame; use forces/impulses, or
`PhysicsServer2D` state in `_integrate_forces` for teleports.

## Raycasts

For line-of-sight or ground checks, add a `RayCast2D` child (`target_position`,
`enabled`), then read `is_colliding()` and `get_collider()`. For one-off queries in
code:

```gdscript
extends Node2D


func first_hit(from: Vector2, to: Vector2) -> Dictionary:
	var space := get_world_2d().direct_space_state
	var query := PhysicsRayQueryParameters2D.create(from, to)
	return space.intersect_ray(query)
```

## Debugging collisions

- Nothing collides: check the shape exists and has a size, the layers/masks overlap,
  and the body isn't disabled.
- Falling through the floor: the floor has no collision (a TileSet without a physics
  layer is a common cause) or the body moves too fast (enable continuous CD on
  RigidBody).
