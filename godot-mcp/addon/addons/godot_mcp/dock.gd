@tool
extends EditorDock
## "MCP" dock: server status, start/stop, token and client-setup helpers, recent commands.

var plugin: EditorPlugin

var _status: Label
var _details: Label
var _toggle: Button
var _log: ItemList


func _init() -> void:
	title = "MCP"
	default_slot = DOCK_SLOT_RIGHT_UL
	layout_key = "godot_mcp"


func _ready() -> void:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	add_child(box)

	_status = Label.new()
	box.add_child(_status)
	_details = Label.new()
	_details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_details.add_theme_color_override("font_color", get_theme_color("font_disabled_color", "Editor"))
	box.add_child(_details)

	var buttons := HFlowContainer.new()
	box.add_child(buttons)
	_toggle = Button.new()
	_toggle.pressed.connect(_on_toggle)
	buttons.add_child(_toggle)
	var copy_cmd := Button.new()
	copy_cmd.text = "Copy Claude Code command"
	copy_cmd.tooltip_text = "Copies a `claude mcp add` command. See the godot-mcp README for other clients."
	copy_cmd.pressed.connect(_copy_command)
	buttons.add_child(copy_cmd)

	var log_label := Label.new()
	log_label.text = "Recent commands"
	box.add_child(log_label)
	_log = ItemList.new()
	_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_log.custom_minimum_size = Vector2(0, 160)
	box.add_child(_log)

	plugin.listener.status_changed.connect(_refresh)
	plugin.listener.command_logged.connect(_on_command)
	for line in plugin.listener.recent:
		_log.add_item(line)
	_refresh()


func _refresh() -> void:
	var l: Node = plugin.listener
	if l.is_listening():
		_status.text = "● Listening on 127.0.0.1:%d" % l.port
		_status.add_theme_color_override("font_color", get_theme_color("success_color", "Editor"))
		_toggle.text = "Stop"
		var auth := "token: %s" % plugin.token_source if l.token != "" else "no token required (any local process can connect)"
		_details.text = "%d client(s) connected · %s" % [l.client_count(), auth]
	else:
		_status.text = "○ Stopped"
		_status.remove_theme_color_override("font_color")
		_toggle.text = "Start"
		_details.text = l.last_error if l.last_error != "" else "Start the server so MCP clients can connect."


func _on_toggle() -> void:
	if plugin.listener.is_listening():
		plugin.stop_server()
	else:
		plugin.start_server()


func _on_command(line: String) -> void:
	_log.add_item("%s  %s" % [Time.get_time_string_from_system(), line])
	while _log.item_count > 50:
		_log.remove_item(0)
	_log.ensure_current_is_visible()
	_refresh()


func _copy_command() -> void:
	var spec := "git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=godot-mcp"
	var env := ""
	if plugin.listener.port != 9080:
		env = "-e GODOT_MCP_PORT=%d " % plugin.listener.port
	DisplayServer.clipboard_set("claude mcp add godot -s user %s-- uvx --from \"%s\" godot-mcp" % [env, spec])
