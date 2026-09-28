@tool
extends "base.gd"
## Project-level tools: info, files, search, settings, input map.

## Settings the agent may change with set_project_setting. Everything else (editor_plugins/,
## editor/, dotnet/, ...) is refused so an agent can't e.g. disable this plugin.
const WRITABLE_SETTING_PREFIXES := [
	"application/config/", "application/run/", "application/boot_splash/",
	"display/", "audio/", "physics/", "rendering/", "gui/", "input_devices/",
	"layer_names/", "internationalization/", "navigation/", "animation/", "debug/",
	"autoload/",
]

const JOY_BUTTONS := {
	"a": JOY_BUTTON_A, "b": JOY_BUTTON_B, "x": JOY_BUTTON_X, "y": JOY_BUTTON_Y,
	"back": JOY_BUTTON_BACK, "guide": JOY_BUTTON_GUIDE, "start": JOY_BUTTON_START,
	"left_stick": JOY_BUTTON_LEFT_STICK, "right_stick": JOY_BUTTON_RIGHT_STICK,
	"left_shoulder": JOY_BUTTON_LEFT_SHOULDER, "right_shoulder": JOY_BUTTON_RIGHT_SHOULDER,
	"dpad_up": JOY_BUTTON_DPAD_UP, "dpad_down": JOY_BUTTON_DPAD_DOWN,
	"dpad_left": JOY_BUTTON_DPAD_LEFT, "dpad_right": JOY_BUTTON_DPAD_RIGHT,
}
const JOY_AXES := {
	"left_x": JOY_AXIS_LEFT_X, "left_y": JOY_AXIS_LEFT_Y, "right_x": JOY_AXIS_RIGHT_X,
	"right_y": JOY_AXIS_RIGHT_Y, "trigger_left": JOY_AXIS_TRIGGER_LEFT,
	"trigger_right": JOY_AXIS_TRIGGER_RIGHT,
}

const MAX_SEARCH_FILE_BYTES := 1024 * 1024


func register(h: Dictionary) -> void:
	h["ping"] = ping
	h["get_project_info"] = get_project_info
	h["list_files"] = list_files
	h["search_files"] = search_files
	h["get_project_settings"] = get_project_settings
	h["set_project_setting"] = set_project_setting
	h["get_input_map"] = get_input_map
	h["edit_input_map"] = edit_input_map


func ping(_p: Dictionary) -> Variant:
	return {
		"pong": true,
		"godot_version": Engine.get_version_info()["string"],
		# false while the editor is still scanning/importing files (e.g. right after start)
		"editor_ready": not EditorInterface.get_resource_filesystem().is_scanning(),
	}


# --- project info -------------------------------------------------------------------------


func get_project_info(_p: Dictionary) -> Variant:
	await wait_for_filesystem()
	var autoloads := {}
	var actions: Array[String] = []
	var builtin_actions := 0
	for prop in ProjectSettings.get_property_list():
		var pname: String = prop["name"]
		if pname.begins_with("autoload/"):
			if pname == "autoload/McpRuntime":
				continue  # this plugin's own runtime, not part of the game
			var value := String(ProjectSettings.get_setting(pname))
			autoloads[pname.substr(9)] = Paths.uid_to_path(value.trim_prefix("*"))
		elif pname.begins_with("input/"):
			var action := pname.substr(6)
			if action.begins_with("ui_"):
				builtin_actions += 1
			else:
				actions.append(action)

	var counts := {}
	var all_files: Array[Dictionary] = []
	_collect_files(EditorInterface.get_resource_filesystem().get_filesystem(), all_files, true)
	for f in all_files:
		var cat := _category(f["type"])
		counts[cat] = counts.get(cat, 0) + 1

	var edited := EditorInterface.get_edited_scene_root()
	var selected: Array[String] = []
	if edited != null:
		for n in EditorInterface.get_selection().get_selected_nodes():
			selected.append(node_path(edited, n))

	var main_scene := Paths.uid_to_path(String(ProjectSettings.get_setting("application/run/main_scene", "")))
	return {
		"name": ProjectSettings.get_setting("application/config/name", ""),
		"description": ProjectSettings.get_setting("application/config/description", ""),
		"version": ProjectSettings.get_setting("application/config/version", ""),
		"godot_version": Engine.get_version_info()["string"],
		"project_path": ProjectSettings.globalize_path("res://"),
		"main_scene": main_scene,
		"features": Array(ProjectSettings.get_setting("application/config/features", PackedStringArray())),
		"renderer": ProjectSettings.get_setting("rendering/renderer/rendering_method", ""),
		"window": {
			"viewport_size": "%dx%d" % [ProjectSettings.get_setting("display/window/size/viewport_width", 0), ProjectSettings.get_setting("display/window/size/viewport_height", 0)],
			"stretch_mode": ProjectSettings.get_setting("display/window/stretch/mode", ""),
		},
		"autoloads": autoloads,
		"input_actions": actions,
		"builtin_ui_actions": builtin_actions,
		"enabled_plugins": Array(ProjectSettings.get_setting("editor_plugins/enabled", PackedStringArray())),
		"mcp_runtime_installed": ProjectSettings.has_setting("autoload/McpRuntime"),
		"uses_csharp": _uses_csharp(),
		"file_counts": counts,
		"editor": {
			"edited_scene": edited.scene_file_path if edited != null else "",
			"edited_scene_root_type": edited.get_class() if edited != null else "",
			"open_scenes": Array(EditorInterface.get_open_scenes()),
			"selected_nodes": selected,
			"headless": DisplayServer.get_name() == "headless",
		},
	}


func _uses_csharp() -> bool:
	if ProjectSettings.get_setting("dotnet/project/assembly_name", "") != "":
		return true
	for f in DirAccess.get_files_at("res://"):
		if f.get_extension() in ["csproj", "sln"]:
			return true
	return false


# --- files --------------------------------------------------------------------------------


func _collect_files(dir: EditorFileSystemDirectory, out: Array[Dictionary], recursive: bool) -> void:
	if dir == null:
		return
	for i in dir.get_file_count():
		var entry := {"path": dir.get_file_path(i), "type": String(dir.get_file_type(i))}
		var cls := String(dir.get_file_script_class_name(i))
		if cls != "":
			entry["class_name"] = cls
		out.append(entry)
	if recursive:
		for i in dir.get_subdir_count():
			_collect_files(dir.get_subdir(i), out, true)


static func _category(type: String) -> String:
	if type == "PackedScene":
		return "scene"
	if type == "":
		return "other"
	if ClassDB.class_exists(type):
		if ClassDB.is_parent_class(type, "Script"):
			return "script"
		if ClassDB.is_parent_class(type, "Shader") or ClassDB.is_parent_class(type, "ShaderInclude"):
			return "shader"
		if ClassDB.is_parent_class(type, "Texture"):
			return "texture"
		if ClassDB.is_parent_class(type, "AudioStream"):
			return "audio"
		if ClassDB.is_parent_class(type, "Font"):
			return "font"
	return "resource"


func list_files(p: Dictionary) -> Variant:
	await wait_for_filesystem()
	var path := Paths.normalize(String(p.get("path", "res://")))
	if path == "":
		return invalid(Paths.describe_bad(String(p.get("path"))))
	var dir := EditorInterface.get_resource_filesystem().get_filesystem_path(path)
	if dir == null:
		return fail("No folder '%s' in the project (the editor only lists folders it imported; folders with a .gdignore are skipped)." % path)
	var recursive: bool = p.get("recursive", true)
	var type_filter := String(p.get("type", "")).strip_edges()
	var files: Array[Dictionary] = []
	_collect_files(dir, files, recursive)
	if type_filter != "":
		var categories := ["scene", "script", "shader", "texture", "audio", "font", "resource", "other"]
		files = files.filter(func(f: Dictionary) -> bool:
			if type_filter in categories:
				return _category(f["type"]) == type_filter
			return f["type"] == type_filter or (ClassDB.class_exists(f["type"]) and ClassDB.class_exists(type_filter) and ClassDB.is_parent_class(f["type"], type_filter)))
	var result := page(files, int(p.get("offset", 0)), int(p.get("limit", 200)))
	var out := {"path": path, "files": result["items"], "total": result["total"]}
	if result.has("next_offset"):
		out["next_offset"] = result["next_offset"]
	if not recursive:
		var subdirs: Array[String] = []
		for i in dir.get_subdir_count():
			subdirs.append(dir.get_subdir(i).get_path().trim_suffix("/"))
		out["folders"] = subdirs
	return out


func search_files(p: Dictionary) -> Variant:
	var query := String(p.get("query", ""))
	if query == "":
		return invalid("`query` must not be empty")
	var root := Paths.normalize(String(p.get("path", "res://")))
	if root == "":
		return invalid(Paths.describe_bad(String(p.get("path"))))
	var case_sensitive: bool = p.get("case_sensitive", false)
	var max_results := int(p.get("max_results", 100))
	var exts: Array = p.get("extensions", [])
	var regex: RegEx = null
	if p.get("regex", false):
		regex = RegEx.new()
		var pattern := query if case_sensitive else "(?i)" + query
		if regex.compile(pattern) != OK:
			return invalid("invalid regular expression: %s" % query)
	var needle := query if case_sensitive else query.to_lower()

	var files: Array[String] = []
	if FileAccess.file_exists(root):
		files.append(root)
	else:
		_walk_text_files(root, files, exts)
	var matches: Array[Dictionary] = []
	var files_matched := 0
	var truncated := false
	for f in files:
		var fa := FileAccess.open(f, FileAccess.READ)
		if fa == null or fa.get_length() > MAX_SEARCH_FILE_BYTES:
			continue
		var line_no := 0
		var hit := false
		while not fa.eof_reached():
			var line := fa.get_line()
			line_no += 1
			var found := false
			if regex != null:
				found = regex.search(line) != null
			else:
				found = (line if case_sensitive else line.to_lower()).contains(needle)
			if found:
				hit = true
				if matches.size() >= max_results:
					truncated = true
					break
				matches.append({"path": f, "line": line_no, "text": line.strip_edges().left(200)})
		if hit:
			files_matched += 1
		if truncated:
			break
	var out := {"matches": matches, "files_searched": files.size(), "files_matched": files_matched}
	if truncated:
		out["truncated"] = true
	return out


func _walk_text_files(dir_path: String, out: Array[String], exts: Array) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for f in dir.get_files():
		if f.begins_with(".") or dir.is_link(f):
			continue
		var ext := f.get_extension().to_lower()
		if (exts.is_empty() and Paths.is_text_file(f) and ext != "import") or (not exts.is_empty() and ext in exts):
			out.append(dir_path.path_join(f))
	for d in dir.get_directories():
		if not Paths.skip_dir(dir_path, d):
			_walk_text_files(dir_path.path_join(d), out, exts)


# --- settings -----------------------------------------------------------------------------


func get_project_settings(p: Dictionary) -> Variant:
	var prefix := String(p.get("prefix", ""))
	var changed_only: bool = p.get("changed_only", prefix == "")
	var items: Array[Dictionary] = []
	for prop in ProjectSettings.get_property_list():
		var pname: String = prop["name"]
		if not pname.contains("/") or not pname.begins_with(prefix):
			continue
		if prop["usage"] & (PROPERTY_USAGE_CATEGORY | PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
			continue
		var value: Variant = ProjectSettings.get_setting(pname)
		if changed_only and not _is_changed(pname, value):
			continue
		var entry := {"name": pname, "type": Codec.type_label(prop), "value": Codec.encode(value)}
		if prop.get("hint", 0) == PROPERTY_HINT_ENUM:
			entry["options"] = prop.get("hint_string", "")
		items.append(entry)
	var result := page(items, int(p.get("offset", 0)), int(p.get("limit", 100)))
	var out := {"settings": result["items"], "total": result["total"]}
	if result.has("next_offset"):
		out["next_offset"] = result["next_offset"]
	return out


func _is_changed(pname: String, value: Variant) -> bool:
	if not ProjectSettings.property_can_revert(pname):
		return true  # custom setting with no default
	var default: Variant = ProjectSettings.property_get_revert(pname)
	return typeof(default) != typeof(value) or default != value


func set_project_setting(p: Dictionary) -> Variant:
	var pname := String(p.get("name", "")).strip_edges()
	if pname == "" or not pname.contains("/"):
		return invalid("`name` must be a full setting path like 'display/window/size/viewport_width'")
	var allowed := WRITABLE_SETTING_PREFIXES.any(func(prefix: String) -> bool: return pname.begins_with(prefix))
	if not allowed:
		return fail("'%s' can't be changed through MCP. Writable prefixes: %s. (Input actions: use edit_input_map.)" % [pname, ", ".join(WRITABLE_SETTING_PREFIXES)])
	var value: Variant = p.get("value")
	if pname.begins_with("autoload/"):
		return _set_autoload(pname.substr(9), value)
	var exists := ProjectSettings.has_setting(pname)
	var old: Variant = ProjectSettings.get_setting(pname) if exists else null
	var decoded: Variant = value
	if value == null:
		if not exists:
			return fail("No setting '%s' to reset." % pname)
		decoded = ProjectSettings.property_get_revert(pname) if ProjectSettings.property_can_revert(pname) else null
	else:
		var target := typeof(old) if exists else TYPE_NIL
		if target in [TYPE_STRING, TYPE_STRING_NAME, TYPE_NODE_PATH] and not (value is String):
			value = String(p.get("value_text", str(value)))  # e.g. '123' for a text setting
		var conv := Codec.decode(value, target)
		if not conv[0]:
			return invalid("%s: %s" % [pname, conv[1]])
		decoded = conv[1]
	_commit_setting("set %s" % pname, pname, old, decoded)
	var out := {"name": pname, "value": Codec.encode(ProjectSettings.get_setting(pname)), "previous": Codec.encode(old)}
	if not exists:
		out["note"] = "This setting did not exist before; it was created. Check the name if you meant an existing engine setting."
	return out


func _set_autoload(autoload_name: String, value: Variant) -> Variant:
	if autoload_name == "McpRuntime":
		return fail("McpRuntime is the godot-mcp plugin's own runtime; it can't be changed through MCP.")
	if not autoload_name.is_valid_identifier():
		return invalid("autoload name '%s' must be a valid identifier" % autoload_name)
	var key := "autoload/" + autoload_name
	var old := String(ProjectSettings.get_setting(key, "")).trim_prefix("*")
	if value == null or String(value) == "":
		if not ProjectSettings.has_setting(key):
			return fail("No autoload named '%s'." % autoload_name)
		plugin.remove_autoload_singleton(autoload_name)
		return {"name": key, "removed": true, "previous": Paths.uid_to_path(old)}
	var path := Paths.normalize(String(value).trim_prefix("*"))
	if path == "" or not FileAccess.file_exists(path):
		return fail("No script or scene at '%s' to use as autoload." % value)
	if ProjectSettings.has_setting(key):
		plugin.remove_autoload_singleton(autoload_name)
	plugin.add_autoload_singleton(autoload_name, path)
	return {"name": key, "value": path, "previous": Paths.uid_to_path(old)}


## Changes a project setting as one undoable editor action and saves project.godot.
func _commit_setting(action: String, pname: String, old: Variant, new_value: Variant) -> void:
	var ur := begin_action(action, ProjectSettings)
	ur.add_do_method(ProjectSettings, "set_setting", pname, new_value)
	ur.add_do_method(ProjectSettings, "save")
	ur.add_undo_method(ProjectSettings, "set_setting", pname, old)
	ur.add_undo_method(ProjectSettings, "save")
	commit_action(ur, action, ProjectSettings)


# --- input map ----------------------------------------------------------------------------


func get_input_map(p: Dictionary) -> Variant:
	var include_builtin: bool = p.get("include_builtin", false)
	var actions := {}
	for prop in ProjectSettings.get_property_list():
		var pname: String = prop["name"]
		if not pname.begins_with("input/"):
			continue
		var action := pname.substr(6)
		if action.begins_with("ui_") and not include_builtin:
			continue
		actions[action] = _describe_action(ProjectSettings.get_setting(pname))
	return {"actions": actions}


func _describe_action(value: Variant) -> Dictionary:
	var events: Array = []
	var deadzone := 0.2
	if value is Dictionary:
		deadzone = float(value.get("deadzone", 0.2))
		for ev: Variant in value.get("events", []):
			if ev is InputEvent:
				events.append(_event_to_spec(ev))
	return {"deadzone": deadzone, "events": events}


func _event_to_spec(ev: InputEvent) -> Dictionary:
	var spec := {}
	if ev is InputEventKey:
		var k := ev as InputEventKey
		var physical := k.physical_keycode != KEY_NONE
		spec = {"type": "key", "key": OS.get_keycode_string(k.physical_keycode if physical else k.keycode), "physical": physical}
	elif ev is InputEventMouseButton:
		var b := (ev as InputEventMouseButton).button_index
		spec = {"type": "mouse_button", "button": Codec.MOUSE_BUTTONS.find_key(b) if Codec.MOUSE_BUTTONS.find_key(b) != null else b}
	elif ev is InputEventJoypadButton:
		var jb := (ev as InputEventJoypadButton).button_index
		spec = {"type": "joypad_button", "button": JOY_BUTTONS.find_key(jb) if JOY_BUTTONS.find_key(jb) != null else jb}
	elif ev is InputEventJoypadMotion:
		var m := ev as InputEventJoypadMotion
		spec = {"type": "joypad_motion", "axis": JOY_AXES.find_key(m.axis) if JOY_AXES.find_key(m.axis) != null else m.axis, "direction": 1 if m.axis_value >= 0 else -1}
	else:
		spec = {"type": ev.get_class()}
	if ev is InputEventWithModifiers:
		var mod := ev as InputEventWithModifiers
		for flag: String in ["ctrl", "shift", "alt", "meta"]:
			if mod.get(flag + "_pressed"):
				spec[flag] = true
	if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
		if ev.device != -1:
			spec["device"] = ev.device
	spec["text"] = ev.as_text()
	return spec


## Builds an InputEvent from a spec dict, or returns an error message string.
func _spec_to_event(spec: Variant) -> Variant:
	if not (spec is Dictionary):
		return "each event must be an object like {\"type\": \"key\", \"key\": \"W\"}"
	var t := String(spec.get("type", ""))
	var ev: InputEvent
	match t:
		"key":
			var key_name := String(spec.get("key", ""))
			var code := OS.find_keycode_from_string(key_name)
			if code == KEY_NONE:
				return "unknown key '%s' (use names like W, Space, Enter, Left, Escape, F1, Shift)" % key_name
			var k := InputEventKey.new()
			if spec.get("physical", true):
				k.physical_keycode = code
			else:
				k.keycode = code
			ev = k
		"mouse_button":
			var b: Variant = spec.get("button", "left")
			var idx: int = Codec.MOUSE_BUTTONS.get(b, -1) if b is String else int(b)
			if idx <= 0:
				return "unknown mouse button '%s' (%s)" % [b, ", ".join(Codec.MOUSE_BUTTONS.keys())]
			var mb := InputEventMouseButton.new()
			mb.button_index = idx
			ev = mb
		"joypad_button":
			var jb: Variant = spec.get("button", "a")
			var jidx: int = JOY_BUTTONS.get(jb, -1) if jb is String else int(jb)
			if jidx < 0:
				return "unknown joypad button '%s' (%s or an index)" % [jb, ", ".join(JOY_BUTTONS.keys())]
			var j := InputEventJoypadButton.new()
			j.button_index = jidx
			ev = j
		"joypad_motion":
			var ax: Variant = spec.get("axis", "left_x")
			var aidx: int = JOY_AXES.get(ax, -1) if ax is String else int(ax)
			if aidx < 0:
				return "unknown joypad axis '%s' (%s or an index)" % [ax, ", ".join(JOY_AXES.keys())]
			var m := InputEventJoypadMotion.new()
			m.axis = aidx
			m.axis_value = 1.0 if float(spec.get("direction", 1)) >= 0 else -1.0
			ev = m
		_:
			return "unknown event type '%s' (key, mouse_button, joypad_button, joypad_motion)" % t
	if ev is InputEventWithModifiers:
		for flag: String in ["ctrl", "shift", "alt", "meta"]:
			if spec.get(flag, false):
				ev.set(flag + "_pressed", true)
	if ev is InputEventJoypadButton or ev is InputEventJoypadMotion:
		ev.device = int(spec.get("device", -1))
	return ev


func edit_input_map(p: Dictionary) -> Variant:
	var action := String(p.get("action", "")).strip_edges()
	if action == "" or action.contains("/") or action.contains(" "):
		return invalid("`action` must be a name without spaces or '/', e.g. 'jump' or 'move_left'")
	if action.begins_with("ui_") and p.get("remove_action", false):
		return fail("Built-in ui_* actions can't be removed.")
	var key := "input/" + action
	var exists := ProjectSettings.has_setting(key)
	var old: Variant = ProjectSettings.get_setting(key) if exists else null

	if p.get("remove_action", false):
		if not exists:
			return fail("No input action '%s'." % action)
		_commit_setting("remove input action %s" % action, key, old, null)
		return {"action": action, "removed": true}

	var current: Dictionary = old.duplicate(true) if old is Dictionary else {"deadzone": 0.2, "events": []}
	var events: Array = current.get("events", []).duplicate()
	if p.get("clear_events", false):
		events.clear()
	for spec: Variant in p.get("remove_events", []):
		var target: Variant = _spec_to_event(spec)
		if target is String:
			return invalid(target)
		events = events.filter(func(e: InputEvent) -> bool: return not e.is_match(target, true))
	for spec: Variant in p.get("add_events", []):
		var ev: Variant = _spec_to_event(spec)
		if ev is String:
			return invalid(ev)
		if not events.any(func(e: InputEvent) -> bool: return e.is_match(ev, true)):
			events.append(ev)
	current["events"] = events
	var deadzone := float(p.get("deadzone", -1.0))
	if deadzone >= 0.0:
		current["deadzone"] = deadzone
	_commit_setting("edit input action %s" % action, key, old, current)
	var out := {"action": action, "created": not exists}
	out.merge(_describe_action(current))
	return out
