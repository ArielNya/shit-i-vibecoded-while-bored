@tool
extends RefCounted
## execute_gdscript: runs a snippet of GDScript as the body of a function, in the editor
## or in the running game. Shared by handlers/exec.gd and runtime/mcp_runtime.gd.
##
## The snippet sees `scene` (the edited scene root / the game's current scene), `tree`
## (the SceneTree) and, in the editor, `editor` (EditorInterface). It may `await` and
## `return` a value. Prints and errors are captured through a LogCapture.

const Codec := preload("codec.gd")
const LogCapture := preload("log_capture.gd")

const HEADER := [
	"@tool",
	"extends RefCounted",
	"var scene: Node",
	"var tree: SceneTree",
	"var editor: Object",
	"func run() -> Variant:",
]
const MAX_OUTPUT_LINES := 200


## Returns {"ok", "result"?, "output": [...], "errors": [{"line"?, "message"}]}.
static func run(code: String, capture: LogCapture, scene: Node, tree: SceneTree, editor: Object) -> Dictionary:
	var source := _source(code)
	var mark := capture.mark()
	var script := GDScript.new()
	script.source_code = source
	if script.reload() != OK:
		return {"ok": false, "stage": "compile", "errors": _errors(capture, mark), "output": []}
	var runner: Object = script.new()
	runner.set("scene", scene)
	runner.set("tree", tree)
	runner.set("editor", editor)
	var value: Variant = await runner.call("run")
	var errors := _errors(capture, mark)
	var out := {"ok": errors.is_empty(), "output": _output(capture, mark), "errors": errors}
	if errors.is_empty():
		out["result"] = Codec.encode(value, scene)
	else:
		out["stage"] = "run"
	return out


## The snippet, indented into run() with the snippet's own indent style (GDScript refuses
## tabs and spaces mixed in one line's indentation).
static func _source(code: String) -> String:
	var lines := code.replace("\r\n", "\n").split("\n")
	var unit := "\t"
	for line in lines:
		if line.begins_with(" "):
			unit = "    "
			break
	var body: PackedStringArray = []
	for line in lines:
		body.append(unit + line if line.strip_edges() != "" else "")
	body.append(unit + "return null")
	return "\n".join(HEADER) + "\n" + "\n".join(body) + "\n"


static func _errors(capture: LogCapture, mark: int) -> Array:
	var out: Array = []
	for e in capture.errors_since(mark):
		var entry := {"message": String(e["message"])}
		var line := int(e["line"])
		# Lines of the generated script -> lines of the snippet. Errors from other files
		# (a function the snippet called) keep their own file:line.
		var file := String(e["file"])
		if file.begins_with("gdscript://") and line > HEADER.size():
			entry["line"] = line - HEADER.size()
		elif file.begins_with("res://"):
			entry["file"] = file
			entry["line"] = line
		if not out.has(entry):
			out.append(entry)
	return out


static func _output(capture: LogCapture, mark: int) -> Array:
	var lines: Array = []
	for e in capture.entries_since(mark):
		if e["level"] in ["stdout", "stderr"]:
			lines.append(String(e["message"]))
	return lines.slice(max(0, lines.size() - MAX_OUTPUT_LINES))
