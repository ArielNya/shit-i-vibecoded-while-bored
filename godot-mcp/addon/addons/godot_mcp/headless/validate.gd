@tool
extends RefCounted
## validate_project: loads every script, scene and resource in the project the way the game
## would, and reports what fails (parse errors with file:line, broken resources) plus
## references to files that don't exist. Runs in a headless Godot, no editor needed.

const LogCapture := preload("../log_capture.gd")
const Paths := preload("../paths.gd")

const MAX_FILES := 5000
const MAX_PROBLEMS := 200
const SCRIPTS := ["gd"]
const RESOURCES := ["tscn", "scn", "tres", "res"]


func run(p: Dictionary) -> Dictionary:
	var include_addons: bool = p.get("include_addons", false)
	var files: Array[String] = []
	_walk("res://", files, include_addons)
	var scripts := files.filter(func(f: String) -> bool: return f.get_extension() in SCRIPTS)
	var resources := files.filter(func(f: String) -> bool: return f.get_extension() in RESOURCES)

	var capture := LogCapture.new()
	OS.add_logger(capture)
	var errors: Array[Dictionary] = []
	var missing: Array[Dictionary] = []
	_check_settings(missing)
	for path: String in resources:
		_check_dependencies(path, missing)
	for path: String in scripts + resources:
		_check_load(path, capture, errors)
	OS.remove_logger(capture)

	var out := {
		"ok": errors.is_empty() and missing.is_empty(),
		"checked": {"scripts": scripts.size(), "scenes_and_resources": resources.size()},
		"errors": errors.slice(0, MAX_PROBLEMS),
		"missing_dependencies": missing.slice(0, MAX_PROBLEMS),
	}
	if errors.size() > MAX_PROBLEMS or missing.size() > MAX_PROBLEMS:
		out["truncated"] = true
	if files.size() >= MAX_FILES:
		out["files_truncated"] = "Only the first %d files were checked." % MAX_FILES
	return out


func _walk(dir_path: String, out: Array[String], include_addons: bool) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for f in dir.get_files():
		if out.size() >= MAX_FILES:
			return
		if not f.begins_with(".") and not dir.is_link(f) and f.get_extension() in SCRIPTS + RESOURCES:
			out.append(dir_path.path_join(f))
	for d in dir.get_directories():
		var sub := dir_path.path_join(d)
		if Paths.skip_dir(dir_path, d) or (sub == "res://addons" and not include_addons):
			continue
		_walk(sub, out, include_addons)


## The main scene and autoloads must exist, or the game won't start.
func _check_settings(missing: Array[Dictionary]) -> void:
	var main := String(ProjectSettings.get_setting("application/run/main_scene", ""))
	if main != "" and not _exists(main):
		missing.append({"file": "res://project.godot", "setting": "application/run/main_scene", "dependency": main})
	for prop in ProjectSettings.get_property_list():
		var pname := String(prop["name"])
		if pname.begins_with("autoload/"):
			var target := String(ProjectSettings.get_setting(pname)).trim_prefix("*")
			if not _exists(target):
				missing.append({"file": "res://project.godot", "setting": pname, "dependency": target})


func _check_dependencies(path: String, missing: Array[Dictionary]) -> void:
	for dep in ResourceLoader.get_dependencies(path):
		# "uid://…::Type::res://path" (or just a path); the uid may be stale, the path is
		# what the loader falls back to.
		var parts := String(dep).split("::")
		var target := parts[parts.size() - 1] if parts.size() > 1 else String(dep)
		if target == "" and parts.size() > 0:
			target = parts[0]
		if not _exists(target):
			missing.append({"file": path, "dependency": target})


func _check_load(path: String, capture: LogCapture, errors: Array[Dictionary]) -> void:
	var mark := capture.mark()
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE)
	var found: Array[Dictionary] = []
	var seen := {}
	for e in capture.errors_since(mark):
		var entry := {"file": String(e["file"]), "message": String(e["message"])}
		if not entry["file"].begins_with("res://"):
			entry["file"] = path  # an engine source location; the file being loaded is what matters
		elif int(e["line"]) > 0:
			entry["line"] = int(e["line"])
		var key := "%s:%s:%s" % [entry["file"], entry.get("line", 0), entry["message"]]
		if not seen.has(key):
			seen[key] = true
			found.append(entry)
	# "Failed to load script ... Parse error" only repeats the file:line errors before it.
	var specific := found.any(func(e: Dictionary) -> bool: return e.has("line"))
	for entry in found:
		if not (specific and String(entry["message"]).begins_with("Failed to load script")):
			errors.append(entry)
	if res == null and found.is_empty():
		errors.append({"file": path, "message": "Could not be loaded."})


func _exists(target: String) -> bool:
	var path := Paths.uid_to_path(target)
	return path != "" and not path.begins_with("uid://") and (ResourceLoader.exists(path) or FileAccess.file_exists(path))
