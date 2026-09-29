@tool
extends "base.gd"
## execute_gdscript: the escape hatch for what the structured tools can't do. Off unless
## the user allows it (plugin.gd execute_blocked_reason).

const Exec := preload("../exec.gd")


func register(h: Dictionary) -> void:
	h["execute_gdscript"] = execute_gdscript


func execute_gdscript(p: Dictionary) -> Variant:
	var reason := String(plugin.call("execute_blocked_reason"))
	if reason != "":
		return fail(reason)
	var code := String(p.get("code", ""))
	if code.strip_edges() == "":
		return invalid("`code` is empty")
	var target := String(p.get("target", "editor"))
	if target == "game":
		var reply: Dictionary = await debugger.request("exec", {"code": code}, float(p.get("timeout", 30.0)))
		if reply.has("error"):
			return fail(String(reply["error"]))
		return reply["result"]
	if target != "editor":
		return invalid("`target` must be editor or game")
	var capture: Variant = plugin.get("log_capture")
	return await Exec.run(code, capture, EditorInterface.get_edited_scene_root(), plugin.get_tree(), EditorInterface)
