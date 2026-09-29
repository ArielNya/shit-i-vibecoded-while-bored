# UI: Controls, anchors and containers

## The rules that avoid most layout bugs

1. **Put a `Control` (or `CanvasLayer` → `Control`) at the root of a UI scene** and make
   it fill the screen: `set_anchors_preset(Control.PRESET_FULL_RECT)`, or the property
   values `anchor_right = 1`, `anchor_bottom = 1` with all `offset_*` at 0.
2. **Lay out with containers, not positions.** `VBoxContainer`/`HBoxContainer` stack
   children, `MarginContainer` pads, `CenterContainer` centers, `GridContainer` makes
   grids. Children of containers ignore their own position/size.
3. **Size behaviour comes from `size_flags_horizontal`/`size_flags_vertical`**
   (`SIZE_EXPAND_FILL` = 3 to take the free space) and `custom_minimum_size`.
4. **HUD over a game world goes in a `CanvasLayer`**, so it doesn't move with the camera.

## Main menu scene layout

```
MainMenu (Control, full rect)
└── CenterContainer (full rect)
    └── VBoxContainer (separation 12)
        ├── Title (Label)
        ├── PlayButton (Button, text "Play")
        ├── OptionsButton (Button, text "Options")
        └── QuitButton (Button, text "Quit")
```

```gdscript
extends Control

@export_file("*.tscn") var first_level := "res://levels/level_1.tscn"


func _ready() -> void:
	$CenterContainer/VBoxContainer/PlayButton.pressed.connect(_on_play)
	$CenterContainer/VBoxContainer/QuitButton.pressed.connect(get_tree().quit)
	$CenterContainer/VBoxContainer/PlayButton.grab_focus()  # keyboard/gamepad navigation


func _on_play() -> void:
	get_tree().change_scene_to_file(first_level)
```

## Pause menu

A pause menu must keep running while the tree is paused: set its `process_mode` to
`PROCESS_MODE_WHEN_PAUSED` (value 2).

```gdscript
extends CanvasLayer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_WHEN_PAUSED
	visible = false


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		toggle()


func toggle() -> void:
	get_tree().paused = not get_tree().paused
	visible = get_tree().paused
```

## Theming

Create one `Theme` resource (`create_resource` type `Theme`), set fonts/colors/styleboxes
in it, and assign it to the root Control's `theme`: every child inherits it. Per-node
tweaks use `add_theme_color_override("font_color", Color.RED)` and friends.

## Checking layout

`get_editor_screenshot` shows the 2D view of the open scene; run the game and
`get_game_screenshot` for the real size. Change `display/window/size/viewport_width` /
`_height` and `display/window/stretch/mode` (`canvas_items`) for resolution scaling.
