# Values in godot-mcp tools

Tools that read or write properties (`get_node_properties`, `set_node_properties`,
`add_node`, `create_resource`, `set_live_properties`, `wait_for`, ...) use one format.

## Plain JSON where it fits

| Type | Write | Read back |
| --- | --- | --- |
| bool, int, float, String | `true`, `3`, `1.5`, `"text"` | same |
| enum / flags | the int (`1`), or its name where the tool accepts it | int |
| null | `null` | `null` |

## Engine types as GDScript literals

Any built-in type is written the way GDScript writes it:

- `"Vector2(100, 200)"`, `"Vector3(0, 1, 0)"`, `"Vector2i(3, 4)"`
- `"Color(1, 0, 0, 1)"`; colors also take `"#ff0000"` or a name like `"red"`
- `"Rect2(0, 0, 64, 32)"`, `"Transform3D(...)"`, `"NodePath(\"../Player\")"`
- `"PackedVector2Array(0, 0, 10, 0, 10, 10)"`

Vectors also take a JSON array: `[100, 200]`. The target property's type decides how a
value is read, so `"position": [10, 20]` becomes a `Vector2` on a Node2D.

## Resources

- A saved resource by path: `"res://art/player.png"` or
  `{"_type": "Resource", "path": "res://art/player.png"}`.
- A new embedded resource with properties:
  `{"_type": "Resource", "class": "RectangleShape2D", "properties": {"size": [32, 32]}}`.
- Read back as `{"_type": "Resource", "class": "...", "path": "res://..."}`, or with
  `"embedded": true` for resources saved inside the scene.

## Nodes

Node references read back as `{"_type": "Node", "class": "...", "path": "..."}`, with the
path relative to the scene root. To set a node reference (for `@export var target: Node`),
write its NodePath relative to the node you're setting: `"../Player"`.

## In scripts

The same literals work in GDScript:

```gdscript
extends Node2D


func _ready() -> void:
	position = Vector2(100, 200)
	modulate = Color(1, 0, 0, 1)
	var shape := RectangleShape2D.new()
	shape.size = Vector2(32, 32)
```
