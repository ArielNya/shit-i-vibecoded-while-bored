---
name: godot-ui-menu
description: Build game menus in Godot 4.7 through the godot-mcp tools — main menu, options with volume and fullscreen, pause menu — using containers and a shared Theme, with keyboard/gamepad focus, and check them with screenshots. Use when asked for a title screen, main/pause/options menu or other Godot UI screens.
---

# Menus in Godot 4.7 (with godot-mcp)

Read the `ui` guide (`read_guide` topic `ui`) first: full-rect root Control, layout
with containers, size flags instead of positions.

## 1. Theme once, reuse everywhere

`create_resource` `res://ui/theme.tres` of type `Theme` with `default_font_size` 24
(and a font if the project has one). Assign it to each menu's root `theme`.

## 2. Main menu (`res://ui/main_menu.tscn`)

1. `new_scene` root `Control` named `MainMenu`; `set_node_properties` anchors
   `anchor_right` 1, `anchor_bottom` 1 (full rect) and `theme`.
2. `add_node` `CenterContainer` (full rect the same way) → `VBoxContainer` named
   `Buttons` (theme constant `separation` via `add_theme_constant_override` in code, or
   leave the default).
3. `add_node` under `Buttons`: `Label` `Title` (`horizontal_alignment` 1), `Button`s
   `Play`, `Options`, `Quit` with `text`.
4. `write_script` + `attach_script`:

```gdscript
extends Control

const OPTIONS := preload("res://ui/options_menu.tscn")

@export_file("*.tscn") var first_level := "res://levels/level_1.tscn"

@onready var buttons: VBoxContainer = $CenterContainer/Buttons


func _ready() -> void:
	buttons.get_node("Play").pressed.connect(_on_play)
	buttons.get_node("Options").pressed.connect(_on_options)
	buttons.get_node("Quit").pressed.connect(get_tree().quit)
	(buttons.get_node("Play") as Button).grab_focus()


func _on_play() -> void:
	get_tree().change_scene_to_file(first_level)


func _on_options() -> void:
	var options := OPTIONS.instantiate()
	add_child(options)
```

Create the options scene (step 3) before this script, since `preload` checks the path.
Set `application/run/main_scene` to the menu.

## 3. Options (`res://ui/options_menu.tscn`)

Root `PanelContainer` (centered: anchors 0.5 and `grow_*` both), `VBoxContainer` with a
`HSlider` `Volume` (min 0, max 1, step 0.05), a `CheckButton` `Fullscreen`, a `Button`
`Back`.

```gdscript
extends PanelContainer

@onready var volume: HSlider = $VBoxContainer/Volume
@onready var fullscreen: CheckButton = $VBoxContainer/Fullscreen


func _ready() -> void:
	var bus := AudioServer.get_bus_index("Master")
	volume.value = db_to_linear(AudioServer.get_bus_volume_db(bus))
	volume.value_changed.connect(_on_volume)
	fullscreen.button_pressed = DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
	fullscreen.toggled.connect(_on_fullscreen)
	$VBoxContainer/Back.pressed.connect(queue_free)
	volume.grab_focus()


func _on_volume(value: float) -> void:
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Master"), linear_to_db(value))


func _on_fullscreen(on: bool) -> void:
	var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if on else DisplayServer.WINDOW_MODE_WINDOWED
	DisplayServer.window_set_mode(mode)
```

## 4. Pause menu (`res://ui/pause_menu.tscn`)

Root `CanvasLayer` (so it draws over the game), child `Control` full rect with a
semi-transparent `ColorRect` and buttons `Resume`, `Main menu`. Instance it in each level.

```gdscript
extends CanvasLayer

@export_file("*.tscn") var main_menu := "res://ui/main_menu.tscn"


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	visible = false


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		set_paused(not get_tree().paused)


func set_paused(paused: bool) -> void:
	get_tree().paused = paused
	visible = paused


func _on_main_menu() -> void:
	set_paused(false)
	get_tree().change_scene_to_file(main_menu)
```

Hook `Resume` → `set_paused(false)` and `Main menu` → `_on_main_menu` with
`connect_signal` (saved in the scene), or in `_ready`.

## 5. Check

1. `validate_project`.
2. `get_editor_screenshot` of each menu scene (2D view) to check the layout.
3. `run_project`, `get_game_screenshot`; `send_input` `{"key": "Down"}` then `{"key":
   "Enter"}` to check focus navigation reaches every button; `get_runtime_errors` empty.
