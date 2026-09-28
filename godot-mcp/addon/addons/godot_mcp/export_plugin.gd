@tool
extends EditorExportPlugin
## Keeps godot-mcp out of exported games' startup: drops the McpRuntime autoload from the
## exported project settings (in memory, restored after the export), so an exported game
## never loads the runtime. The plugin's scripts may still be packed (Godot's own script
## exporter adds them); exclude `addons/godot_mcp/*` in the export preset to drop them.

const RUNTIME_AUTOLOAD := "autoload/McpRuntime"

var _saved_autoload: Variant = null


func _get_name() -> String:
	return "godot_mcp"


func _export_begin(_features: PackedStringArray, _is_debug: bool, _path: String, _flags: int) -> void:
	_saved_autoload = null
	if ProjectSettings.has_setting(RUNTIME_AUTOLOAD):
		_saved_autoload = ProjectSettings.get_setting(RUNTIME_AUTOLOAD)
		ProjectSettings.set_setting(RUNTIME_AUTOLOAD, null)  # in memory only, restored below


func _export_end() -> void:
	if _saved_autoload != null:
		ProjectSettings.set_setting(RUNTIME_AUTOLOAD, _saved_autoload)
		_saved_autoload = null

