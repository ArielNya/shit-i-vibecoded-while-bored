# Scenes, instancing, signals and autoloads

## Scenes are reusable node trees

- Build a player, enemy or pickup as its own scene (`new_scene`, then `add_node`s,
  `save_scene`), then instance it into levels with `add_node` and `scene:
  "res://player.tscn"`.
- Already built something inline? `save_branch_as_scene` turns a subtree into its own
  `.tscn` and replaces it with an instance.
- Edit the instanced scene's file to change every copy; set properties on one
  instance to override just that one.

## Spawning at runtime

```gdscript
extends Node2D

const BULLET := preload("res://bullet.tscn")


func shoot(at: Vector2) -> void:
	var bullet := BULLET.instantiate() as Node2D
	bullet.global_position = at
	add_child(bullet)
```

`preload` needs the file to exist (the path is checked when the script compiles). Use
`load()` for paths chosen at runtime.

## Signals

Declare, emit, connect:

```gdscript
extends Node

signal health_changed(value: int)
signal died

var health := 3


func take_damage(amount: int) -> void:
	health = maxi(health - amount, 0)
	health_changed.emit(health)
	if health == 0:
		died.emit()


func _ready() -> void:
	died.connect(_on_died)


func _on_died() -> void:
	print("game over")
```

- Connections made in code are lost when the node is freed. Connections that should be
  saved in the scene (e.g. a Button's `pressed` to a method on the root) are made with
  `connect_signal`; `list_signals` shows what's there.
- Wait for a signal with `await`: `await $AnimationPlayer.animation_finished`.

## Autoloads (singletons)

Global state (score, settings, save data) goes in an autoload: a script registered in
project settings (`set_project_setting` with `autoload/GameState` =
`"*res://game_state.gd"`). Any script can then use `GameState.score`.

```gdscript
extends Node

signal score_changed(score: int)

var score := 0


func add_points(points: int) -> void:
	score += points
	score_changed.emit(score)
```

## Groups

Tag nodes with groups (`set_groups`), then find them without hard-coded paths:
`get_tree().get_nodes_in_group("enemies")`, or `get_tree().call_group("enemies",
"freeze")`.

## Changing scenes

`get_tree().change_scene_to_file("res://levels/level_2.tscn")`, or
`change_scene_to_packed(preloaded_scene)`. Autoloads stay alive across the change.
