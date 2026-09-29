@tool
extends Logger
## Keeps the most recent engine errors/warnings so a failed handler can say *why* it
## failed (GDScript runtime errors don't propagate; they're only logged).
##
## Logger callbacks can arrive from any thread, hence the mutex.

const MAX_ENTRIES := 500

var _mutex := Mutex.new()
var _entries: Array[Dictionary] = []
var _serial := 0


func _log_error(function: String, file: String, line: int, code: String, rationale: String, _editor_notify: bool, error_type: int, script_backtraces: Array[ScriptBacktrace]) -> void:
	var kind := "error"
	match error_type:
		ERROR_TYPE_WARNING:
			kind = "warning"
		ERROR_TYPE_SCRIPT:
			kind = "script_error"
		ERROR_TYPE_SHADER:
			kind = "shader_error"
	var text := rationale if rationale != "" else code
	var entry := {"level": kind, "message": text, "file": file, "line": line, "function": function}
	var frames: Array = []
	for bt in script_backtraces:
		for i in min(bt.get_frame_count(), 8):
			frames.append("%s:%d in %s()" % [bt.get_frame_file(i), bt.get_frame_line(i), bt.get_frame_function(i)])
	if not frames.is_empty():
		entry["backtrace"] = frames
		# Point at the script line rather than the engine's C++ source when we can.
		var top: ScriptBacktrace = script_backtraces[0]
		# (gdscript:// is an in-memory script, e.g. an execute_gdscript snippet: keep it.)
		if top.get_frame_count() > 0 and not file.begins_with("res://") and not file.begins_with("gdscript://"):
			entry["file"] = top.get_frame_file(0)
			entry["line"] = top.get_frame_line(0)
	_add(entry)


func _log_message(message: String, error: bool) -> void:
	_add({"level": "stderr" if error else "stdout", "message": message.strip_edges(false, true)})


func _add(entry: Dictionary) -> void:
	_mutex.lock()
	_serial += 1
	entry["seq"] = _serial
	_entries.append(entry)
	if _entries.size() > MAX_ENTRIES:
		_entries = _entries.slice(_entries.size() - MAX_ENTRIES)
	_mutex.unlock()


## Sequence number of the latest entry; pass it to errors_since() later.
func mark() -> int:
	_mutex.lock()
	var n := _serial
	_mutex.unlock()
	return n


## Every entry (errors, warnings and printed output) newer than `seq`.
func entries_since(seq: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	_mutex.lock()
	for e in _entries:
		if int(e["seq"]) > seq:
			out.append(e)
	_mutex.unlock()
	return out


func errors_since(seq: int) -> Array[Dictionary]:
	return entries_since(seq).filter(func(e: Dictionary) -> bool: return e["level"] in ["error", "script_error", "shader_error"])
