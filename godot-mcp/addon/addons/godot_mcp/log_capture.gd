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


func _log_error(function: String, file: String, line: int, code: String, rationale: String, _editor_notify: bool, error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
	var kind := "error"
	match error_type:
		ERROR_TYPE_WARNING:
			kind = "warning"
		ERROR_TYPE_SCRIPT:
			kind = "script_error"
		ERROR_TYPE_SHADER:
			kind = "shader_error"
	var text := rationale if rationale != "" else code
	_add({"level": kind, "message": text, "file": file, "line": line, "function": function})


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


func errors_since(seq: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	_mutex.lock()
	for e in _entries:
		if int(e["seq"]) > seq and e["level"] in ["error", "script_error", "shader_error"]:
			out.append(e)
	_mutex.unlock()
	return out
