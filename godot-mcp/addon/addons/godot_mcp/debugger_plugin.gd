@tool
extends EditorDebuggerPlugin
## Editor side of the runtime bridge: tracks the game session started from the editor,
## sends "mcp:req" to the McpRuntime autoload and matches "mcp:res" replies, and keeps
## the game's output/errors ("mcp:log") for the current and the previous run.

const MAX_LOG := 3000

## Emitted when the runtime in a newly started game has said hello.
signal runtime_ready(info: Dictionary)
signal session_ended

var run_id := 0
var session_id := -1
var runtime_info: Dictionary = {}
var running := false
var started_msec := 0
var ended_msec := 0
## Game log of the current run (or the last one after it ended). Entries carry "seq".
var log_entries: Array[Dictionary] = []

var _next_request := 1
var _replies := {}  # id -> reply dict
var _log_seq := 0


func _has_capture(prefix: String) -> bool:
	return prefix == "mcp"


func _setup_session(id: int) -> void:
	var session := get_session(id)
	session.started.connect(_on_started.bind(id))
	session.stopped.connect(_on_stopped.bind(id))


func _on_started(id: int) -> void:
	session_id = id
	run_id += 1
	running = true
	runtime_info = {}
	started_msec = Time.get_ticks_msec()
	ended_msec = 0
	log_entries.clear()


func _on_stopped(id: int) -> void:
	if id != session_id or not running:
		return
	running = false
	ended_msec = Time.get_ticks_msec()
	session_ended.emit()


func _capture(message: String, data: Array, id: int) -> bool:
	if id != session_id:
		return true
	match message:
		"mcp:hello":
			runtime_info = data[0] if not data.is_empty() and data[0] is Dictionary else {}
			runtime_ready.emit(runtime_info)
		"mcp:res":
			if not data.is_empty() and data[0] is Dictionary:
				_replies[int(data[0].get("id", -1))] = data[0]
		"mcp:log":
			if not data.is_empty() and data[0] is Array:
				for e: Variant in data[0]:
					if e is Dictionary:
						_log_seq += 1
						var entry: Dictionary = e.duplicate()
						entry["seq"] = _log_seq
						log_entries.append(entry)
				if log_entries.size() > MAX_LOG:
					log_entries = log_entries.slice(log_entries.size() - MAX_LOG)
		_:
			return false
	return true


func is_connected_to_runtime() -> bool:
	return running and not runtime_info.is_empty()


## Sends a request to the game and waits for its reply (or the timeout, or the game
## ending). Returns {"result": ...} or {"error": "..."}.
func request(method: String, params: Dictionary, timeout_sec: float = 15.0) -> Dictionary:
	if not is_connected_to_runtime():
		return {"error": "The game is not running (start it with run_project)." if not running else "The game is starting and its MCP runtime hasn't connected yet."}
	var id := _next_request
	_next_request += 1
	get_session(session_id).send_message("mcp:req", [{"id": id, "method": method, "params": params}])
	var tree := Engine.get_main_loop() as SceneTree
	var deadline := Time.get_ticks_msec() + int(timeout_sec * 1000.0)
	while not _replies.has(id):
		if not running:
			return {"error": "The game exited before answering '%s'." % method}
		if Time.get_ticks_msec() > deadline:
			return {"error": "The game did not answer '%s' within %ss (is it frozen in a long loop?)." % [method, timeout_sec]}
		await tree.process_frame
	var reply: Dictionary = _replies[id]
	_replies.erase(id)
	return reply


## The latest log seq, to only report entries that arrive after this point.
func log_mark() -> int:
	return _log_seq
