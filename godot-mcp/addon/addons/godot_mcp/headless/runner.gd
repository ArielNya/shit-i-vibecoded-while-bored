extends SceneTree
## Entry point for work the MCP server does without an editor:
##   godot --headless --path <project> -s <this file> -- --mcp-request=<file> --mcp-reply=<file>
## Reads {"method", "params"} from the request file and writes {"result"} or {"error"} to
## the reply file. The server runs its own copy of this add-on, so the project doesn't
## need the plugin installed.

const McpError := preload("../mcp_error.gd")
const Validate := preload("validate.gd")


func _initialize() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--mcp-") and a.contains("="):
			args[a.substr(6, a.find("=") - 6)] = a.substr(a.find("=") + 1)
	var reply_path := String(args.get("reply", ""))
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(String(args.get("request", ""))))
	var reply: Dictionary
	if not request is Dictionary or reply_path == "":
		reply = {"error": {"message": "runner.gd needs --mcp-request=<json file> --mcp-reply=<file>"}}
	else:
		reply = _handle(String(request.get("method", "")), request.get("params", {}))
	var f := FileAccess.open(reply_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(reply))
		f.close()
	quit(0 if not reply.has("error") else 1)


func _handle(method: String, params: Dictionary) -> Dictionary:
	var result: Variant
	match method:
		"validate_project":
			result = Validate.new().run(params)
		"get_class_docs", "search_docs":
			# Loaded on demand: the docs handler is shared with the editor plugin.
			var docs: Object = load(get_script().resource_path.get_base_dir().path_join("../handlers/docs.gd")).new()
			result = docs.call(method, params)
		_:
			return {"error": {"message": "unknown method '%s'" % method}}
	if result is McpError:
		return {"error": {"message": result.message, "code": result.code}}
	if result == null:
		return {"error": {"message": "'%s' failed in the headless Godot (see its output)" % method}}
	return {"result": result}
