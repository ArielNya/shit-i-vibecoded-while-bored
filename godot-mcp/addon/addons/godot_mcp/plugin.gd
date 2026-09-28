@tool
extends EditorPlugin
## Entry point: starts the localhost listener the godot-mcp server connects to, wires up
## the handler modules and adds the MCP dock.
##
## Configuration, highest priority first:
##   editor command line (after `--`):  --mcp-port=N  --mcp-token=T  --mcp-no-auth
##                                      --mcp-lsp-port=N (if the editor runs with --lsp-port N)
##   environment:                       GODOT_MCP_PORT  GODOT_MCP_TOKEN  GODOT_MCP_NO_AUTH=1
##   Editor Settings:                   godot_mcp/port, godot_mcp/token, godot_mcp/require_token,
##                                      godot_mcp/auto_start
## Without an explicit token the shared token file is used (created on first start).

const VERSION := "0.1.0"

const Protocol := preload("protocol.gd")
const Listener := preload("listener.gd")
const LogCapture := preload("log_capture.gd")
const Dock := preload("dock.gd")
const Paths := preload("paths.gd")
const DebuggerPlugin := preload("debugger_plugin.gd")
const ExportPlugin := preload("export_plugin.gd")

const RUNTIME_AUTOLOAD := "McpRuntime"
const RUNTIME_SCRIPT := "runtime/mcp_runtime.gd"
const HANDLER_SCRIPTS := [
	preload("handlers/project.gd"),
	preload("handlers/scene.gd"),
	preload("handlers/script.gd"),
	preload("handlers/docs.gd"),
	preload("handlers/view.gd"),
	preload("handlers/edit.gd"),
	preload("handlers/run.gd"),
]

const SETTING_PORT := "godot_mcp/port"
const SETTING_AUTO_START := "godot_mcp/auto_start"
const SETTING_TOKEN := "godot_mcp/token"
const SETTING_REQUIRE_TOKEN := "godot_mcp/require_token"

var listener: Listener
var log_capture: LogCapture
var dock: Dock
## Where the token came from, for the dock ("token file", "Editor Settings", ...).
var token_source := ""
var history := {"done": [], "undone": []}
var debugger: DebuggerPlugin
var exporter: ExportPlugin
var _handlers: Array = []


func _enter_tree() -> void:
	_define_settings()
	log_capture = LogCapture.new()
	OS.add_logger(log_capture)
	listener = Listener.new()
	listener.name = "GodotMcpListener"
	listener.log_capture = log_capture
	debugger = DebuggerPlugin.new()
	add_debugger_plugin(debugger)
	exporter = ExportPlugin.new()
	add_export_plugin(exporter)
	_ensure_runtime_autoload()
	for script: GDScript in HANDLER_SCRIPTS:
		var handler: RefCounted = script.new()
		handler.plugin = self
		handler.history = history
		handler.debugger = debugger
		handler.register(listener.handlers)
		_handlers.append(handler)
	add_child(listener)
	dock = Dock.new()
	dock.plugin = self
	add_dock(dock)
	if bool(_editor_settings().get_setting(SETTING_AUTO_START)) or _cli_value("--mcp-port") != "":
		start_server()


func _exit_tree() -> void:
	if listener != null:
		listener.stop()
	if dock != null:
		remove_dock(dock)
		dock.queue_free()
		dock = null
	if log_capture != null:
		OS.remove_logger(log_capture)
		log_capture = null
	if debugger != null:
		remove_debugger_plugin(debugger)
		debugger = null
	if exporter != null:
		remove_export_plugin(exporter)
		exporter = null
	_handlers.clear()


func start_server() -> bool:
	listener.token = _resolve_token()
	listener.server_info = _server_info()
	return listener.start(Protocol.DEFAULT_HOST, _resolve_port())


func stop_server() -> void:
	listener.stop()


func _server_info() -> Dictionary:
	# The engine consumes --lsp-port before scripts can see it, so an editor started with
	# `--lsp-port N` should also get `-- --mcp-lsp-port=N` to report the right port.
	var lsp_port := int(_editor_settings().get_setting("network/language_server/remote_port"))
	if _cli_value("--mcp-lsp-port") != "":
		lsp_port = int(_cli_value("--mcp-lsp-port"))
	return {
		"godot_version": Engine.get_version_info()["string"],
		"plugin_version": VERSION,
		"project_name": ProjectSettings.get_setting("application/config/name", ""),
		"project_path": ProjectSettings.globalize_path("res://"),
		"lsp": {"host": String(_editor_settings().get_setting("network/language_server/remote_host")), "port": lsp_port},
		"headless": DisplayServer.get_name() == "headless",
		"pid": OS.get_process_id(),
	}


func _resolve_port() -> int:
	var cli := _cli_value("--mcp-port")
	if cli != "":
		return int(cli)
	var env := OS.get_environment("GODOT_MCP_PORT")
	if env != "":
		return int(env)
	return int(_editor_settings().get_setting(SETTING_PORT))


func _resolve_token() -> String:
	var no_auth_env := OS.get_environment("GODOT_MCP_NO_AUTH").to_lower()
	if "--mcp-no-auth" in OS.get_cmdline_user_args() or no_auth_env in ["1", "true", "yes"] or not bool(_editor_settings().get_setting(SETTING_REQUIRE_TOKEN)):
		token_source = "disabled"
		return ""
	var cli := _cli_value("--mcp-token")
	if cli != "":
		token_source = "command line"
		return cli
	var env := OS.get_environment("GODOT_MCP_TOKEN")
	if env != "":
		token_source = "GODOT_MCP_TOKEN"
		return env
	var configured := String(_editor_settings().get_setting(SETTING_TOKEN)).strip_edges()
	if configured != "":
		token_source = "Editor Settings"
		return configured
	token_source = "token file"
	return Protocol.ensure_token_file()


func _cli_value(flag: String) -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with(flag + "="):
			return arg.substr(flag.length() + 1)
	return ""


func _editor_settings() -> EditorSettings:
	return EditorInterface.get_editor_settings()


func _define_settings() -> void:
	var es := _editor_settings()
	var defs := [
		[SETTING_PORT, Protocol.DEFAULT_PORT, TYPE_INT, PROPERTY_HINT_RANGE, "1024,65535"],
		[SETTING_AUTO_START, true, TYPE_BOOL, PROPERTY_HINT_NONE, ""],
		[SETTING_REQUIRE_TOKEN, true, TYPE_BOOL, PROPERTY_HINT_NONE, ""],
		[SETTING_TOKEN, "", TYPE_STRING, PROPERTY_HINT_PASSWORD, ""],
	]
	for d: Array in defs:
		if not es.has_setting(d[0]):
			es.set_setting(d[0], d[1])
		es.set_initial_value(d[0], d[1], false)
		es.add_property_info({"name": d[0], "type": d[2], "hint": d[3], "hint_string": d[4]})


## The McpRuntime autoload lets MCP tools see and drive the running game. It is inert
## unless the game runs from the editor with the debugger, and exports leave it out.
func _ensure_runtime_autoload() -> void:
	var path: String = get_script().resource_path.get_base_dir().path_join(RUNTIME_SCRIPT)
	var current := String(ProjectSettings.get_setting("autoload/" + RUNTIME_AUTOLOAD, "")).trim_prefix("*")
	if Paths.uid_to_path(current) != path:
		add_autoload_singleton(RUNTIME_AUTOLOAD, path)
		ProjectSettings.save()  # the editor would save later; a game started now needs it


func _disable_plugin() -> void:
	if ProjectSettings.has_setting("autoload/" + RUNTIME_AUTOLOAD):
		remove_autoload_singleton(RUNTIME_AUTOLOAD)

