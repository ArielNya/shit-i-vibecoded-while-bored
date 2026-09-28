@tool
extends "base.gd"
## Running the game from the editor and observing/driving it through the McpRuntime
## autoload (see runtime/mcp_runtime.gd and debugger_plugin.gd).

const RUNTIME_AUTOLOAD := "McpRuntime"
const START_TIMEOUT_MSEC := 30000
const ERROR_LEVELS := ["error", "script_error", "shader_error"]


func register(h: Dictionary) -> void:
	h["run_project"] = run_project
	h["stop_project"] = stop_project
	h["get_run_status"] = get_run_status
	h["get_output"] = get_output
	h["get_runtime_errors"] = get_runtime_errors
	h["get_game_screenshot"] = get_game_screenshot
	h["get_live_tree"] = get_live_tree
	h["get_live_properties"] = get_live_properties
	h["set_live_properties"] = set_live_properties
	h["send_input"] = send_input
	h["wait_for"] = wait_for
	h["get_performance"] = get_performance


# --- launching -----------------------------------------------------------------------------


## The editor takes extra command-line arguments for the game only from the "Run
## Instances" dialog's main-arguments field (read when the game launches). We put ours
## there just for the launch and restore the user's text right after; nothing is saved.
func _run_args_field() -> LineEdit:
	var dialogs := EditorInterface.get_base_control().find_children("*", "RunInstancesDialog", true, false)
	if dialogs.is_empty():
		return null
	for edit in dialogs[0].find_children("*", "LineEdit", true, false):
		if edit is LineEdit and not (edit.get_parent() is SpinBox):
			return edit  # the first plain LineEdit is the main run arguments field
	return null


func run_project(p: Dictionary) -> Variant:
	var target := String(p.get("scene", ""))
	var display := String(p.get("display", "auto"))
	var editor_headless := DisplayServer.get_name() == "headless"
	var headless := display == "headless" or (display == "auto" and editor_headless)
	if display == "window" and editor_headless:
		return fail("The editor runs headless (no display), so the game can't open a window. Use display=headless, or run the editor with a display (e.g. under Xvfb).")
	if display not in ["auto", "headless", "window"]:
		return invalid("`display` must be auto, headless or window")
	if not ProjectSettings.has_setting("autoload/" + RUNTIME_AUTOLOAD):
		return fail("The %s autoload is missing, so the game can't talk to MCP. Disable and re-enable the Godot MCP plugin to add it." % RUNTIME_AUTOLOAD)

	var scene_path := ""
	if target == "":
		scene_path = uid_to_path(String(ProjectSettings.get_setting("application/run/main_scene", "")))
		if scene_path == "":
			return fail("The project has no main scene. Pass `scene`, or set application/run/main_scene.")
	elif target == "current":
		var root := EditorInterface.get_edited_scene_root()
		if root == null or root.scene_file_path == "":
			return fail("No saved scene is open in the editor.")
		scene_path = root.scene_file_path
	else:
		scene_path = Paths.normalize(target)
		if scene_path == "" or not ResourceLoader.exists(scene_path):
			return fail("No scene at '%s'." % target)
	if scene_path in EditorInterface.get_unsaved_scenes() and not p.get("allow_unsaved", false):
		return fail("'%s' has unsaved changes; the game runs the saved file. Call save_scene first (or pass allow_unsaved=true)." % scene_path)

	if EditorInterface.is_playing_scene():
		await _stop_and_wait()
	# The game reads project.godot from disk; flush settings the editor hasn't saved yet
	# (the editor itself saves them on a timer).
	ProjectSettings.save()

	var extra: PackedStringArray = []
	if headless:
		extra.append("--headless")
	if not p.get("break_on_errors", false):
		extra.append_array(["--ignore-error-breaks", "--skip-breakpoints"])
	var field := _run_args_field()
	if field == null and headless:
		return fail("Couldn't pass --headless to the game (editor UI changed?). Add it yourself under Debug > Customize Run Instances > Main Run Args.")
	var previous_run := debugger.run_id
	var saved_text := ""
	if field != null:
		saved_text = field.text
		field.text = (saved_text + " " + " ".join(extra)).strip_edges()
	if target == "":
		EditorInterface.play_main_scene()
	elif target == "current":
		EditorInterface.play_current_scene()
	else:
		EditorInterface.play_custom_scene(scene_path)
	if field != null:
		field.text = saved_text

	var started := Time.get_ticks_msec()
	var dbg = debugger
	while Time.get_ticks_msec() - started < START_TIMEOUT_MSEC:
		if dbg.run_id != previous_run and dbg.is_connected_to_runtime():
			break
		if dbg.run_id != previous_run and not dbg.running:
			break  # started and already ended
		if Time.get_ticks_msec() - started > 3000 and not EditorInterface.is_playing_scene() and dbg.run_id == previous_run:
			break  # never got going
		await plugin.get_tree().process_frame
	# Give very early errors (e.g. in _ready) a moment to arrive.
	for i in 10:
		await plugin.get_tree().process_frame

	var out := {"scene": scene_path, "headless": headless, "run": dbg.run_id}
	if dbg.run_id != previous_run and dbg.is_connected_to_runtime():
		out["running"] = true
		out["pid"] = dbg.runtime_info.get("pid", 0)
	else:
		out["running"] = false
		out["note"] = "The game did not start or exited right away. Check get_output / get_runtime_errors." if dbg.run_id != previous_run else "The game process didn't connect back to the editor within %d s. See Godot's Output panel." % (START_TIMEOUT_MSEC / 1000)
	var errors := _errors(0)
	if not errors.is_empty():
		out["errors_so_far"] = errors.slice(0, 5)
	return out


func _stop_and_wait() -> void:
	EditorInterface.stop_playing_scene()
	var started := Time.get_ticks_msec()
	while debugger.running and Time.get_ticks_msec() - started < 5000:
		await plugin.get_tree().process_frame


func stop_project(_p: Dictionary) -> Variant:
	if not EditorInterface.is_playing_scene() and not debugger.running:
		return {"stopped": false, "note": "The game wasn't running."}
	await _stop_and_wait()
	return {"stopped": true, "run": debugger.run_id}


func get_run_status(_p: Dictionary) -> Variant:
	var dbg = debugger
	var out := {
		"running": dbg.running,
		"runtime_connected": dbg.is_connected_to_runtime(),
		"run": dbg.run_id,
		"scene": EditorInterface.get_playing_scene() if dbg.running else String(dbg.runtime_info.get("scene", "")),
		"errors": _errors(0).size(),
		"warnings": dbg.log_entries.filter(func(e: Dictionary) -> bool: return e.get("level") == "warning").size(),
		"output_lines": dbg.log_entries.size(),
	}
	if dbg.run_id > 0:
		var end: int = Time.get_ticks_msec() if dbg.running else dbg.ended_msec
		out["seconds"] = snappedf((end - dbg.started_msec) / 1000.0, 0.1)
	if dbg.is_connected_to_runtime():
		var ping: Dictionary = await dbg.request("ping", {}, 5.0)
		if ping.has("result"):
			out["frame"] = ping["result"].get("frame")
			out["fps"] = ping["result"].get("fps")
			out["paused"] = ping["result"].get("paused")
	return out


# --- output --------------------------------------------------------------------------------


static func _format(e: Dictionary) -> Dictionary:
	var out := {"seq": e["seq"], "level": e.get("level", "stdout"), "message": e.get("message", "")}
	if e.get("level") != "stdout" and e.get("level") != "stderr":
		if String(e.get("file", "")) != "":
			out["at"] = "%s:%s" % [e["file"], e.get("line", 0)]
		if e.has("backtrace"):
			out["backtrace"] = e["backtrace"]
	return out


func _errors(since: int) -> Array:
	return debugger.log_entries.filter(func(e: Dictionary) -> bool: return int(e["seq"]) > since and e.get("level") in ERROR_LEVELS)


func get_output(p: Dictionary) -> Variant:
	var since := int(p.get("since", 0))
	var levels: Array = p.get("levels", [])
	var limit := int(p.get("limit", 200))
	var dbg = debugger
	var matching: Array = dbg.log_entries.filter(func(e: Dictionary) -> bool: return int(e["seq"]) > since and (levels.is_empty() or e.get("level") in levels))
	var truncated := matching.size() > limit
	if truncated:
		matching = matching.slice(matching.size() - limit)  # keep the newest
	var out := {
		"run": dbg.run_id,
		"running": dbg.running,
		"entries": matching.map(_format),
		"next_since": dbg.log_mark(),
	}
	if truncated:
		out["truncated"] = "Only the newest %d entries; pass a later `since` or raise `limit`." % limit
	if dbg.run_id == 0:
		out["note"] = "The game hasn't been run in this editor session yet."
	return out


func get_runtime_errors(p: Dictionary) -> Variant:
	var since := int(p.get("since", 0))
	var include_warnings: bool = p.get("include_warnings", true)
	var dbg = debugger
	var grouped := {}
	var order: Array[String] = []
	for e: Dictionary in dbg.log_entries:
		if int(e["seq"]) <= since:
			continue
		var level := String(e.get("level", ""))
		if not (level in ERROR_LEVELS or (include_warnings and level == "warning")):
			continue
		var key := "%s|%s|%s|%s" % [level, e.get("message", ""), e.get("file", ""), e.get("line", 0)]
		if not grouped.has(key):
			var entry := _format(e)
			entry.erase("seq")
			entry["count"] = 0
			entry["first_seq"] = e["seq"]
			grouped[key] = entry
			order.append(key)
		grouped[key]["count"] += 1
	var errors: Array = []
	var warnings: Array = []
	for key in order:
		(warnings if grouped[key]["level"] == "warning" else errors).append(grouped[key])
	var out := {"run": dbg.run_id, "running": dbg.running, "errors": errors, "next_since": dbg.log_mark()}
	if include_warnings:
		out["warnings"] = warnings
	return out


# --- forwarding to the game --------------------------------------------------------------


func _forward(method: String, params: Dictionary, timeout: float = 15.0) -> Variant:
	var reply: Dictionary = await debugger.request(method, params, timeout)
	if reply.has("error"):
		return fail(String(reply["error"]))
	return reply.get("result")


func get_game_screenshot(p: Dictionary) -> Variant:
	return await _forward("screenshot", {"size": int(p.get("size", 768))}, 20.0)


func get_live_tree(p: Dictionary) -> Variant:
	return await _forward("get_tree", p)


func get_live_properties(p: Dictionary) -> Variant:
	return await _forward("get_properties", p)


func set_live_properties(p: Dictionary) -> Variant:
	return await _forward("set_properties", p)


func send_input(p: Dictionary) -> Variant:
	var frames := int(p.get("frames", 1))
	return await _forward("input", p, 10.0 + frames / 30.0)


func wait_for(p: Dictionary) -> Variant:
	var timeout := float(p.get("timeout", 10.0))
	if p.has("seconds"):
		timeout = max(timeout, float(p["seconds"]) + 1.0)
	return await _forward("wait", p, timeout + 10.0)


func get_performance(_p: Dictionary) -> Variant:
	return await _forward("performance", {})
