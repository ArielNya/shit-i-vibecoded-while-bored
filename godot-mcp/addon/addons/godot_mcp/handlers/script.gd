@tool
extends "base.gd"
## Reading scripts and other text files. (Diagnostics come from Godot's GDScript language
## server, which the MCP server talks to directly; these helpers feed it file contents.)

const MAX_LINES := 2000
const MAX_FILES := 2000


func register(h: Dictionary) -> void:
	h["read_script"] = read_script
	h["list_script_files"] = list_script_files
	h["read_text_files"] = read_text_files
	h["write_script"] = write_script
	h["edit_script"] = edit_script
	h["create_script"] = create_script
	h["attach_script"] = attach_script
	h["detach_script"] = detach_script
	# Test-only: exists only when the editor was started with `-- --mcp-test-hooks`.
	if "--mcp-test-hooks" in OS.get_cmdline_user_args():
		h["_test_make_unsaved"] = _test_make_unsaved


func read_script(p: Dictionary) -> Variant:
	var path := Paths.normalize(String(p.get("path", "")))
	if path == "":
		return invalid(Paths.describe_bad(String(p.get("path", ""))))
	if not Paths.is_text_file(path):
		return invalid("'%s' is not a text file this tool reads (%s)." % [path, ", ".join(Paths.TEXT_EXTENSIONS)])
	if not FileAccess.file_exists(path):
		return fail("No file at '%s'." % path)
	var text := FileAccess.get_file_as_string(path)
	var lines := text.split("\n")
	if lines.size() > 0 and lines[lines.size() - 1] == "":
		lines.remove_at(lines.size() - 1)
	var total := lines.size()
	var start: int = max(1, int(p.get("start_line", 1)))
	var end_line := int(p.get("end_line", 0))
	if end_line <= 0 or end_line > total:
		end_line = total
	var truncated := false
	if end_line - start + 1 > MAX_LINES:
		end_line = start + MAX_LINES - 1
		truncated = true
	var width := str(end_line).length()
	var numbered: PackedStringArray = []
	for i in range(start - 1, end_line):
		numbered.append("%*d| %s" % [width, i + 1, lines[i]])
	var out := {"path": path, "total_lines": total, "start_line": start, "end_line": end_line, "text": "\n".join(numbered)}
	if truncated:
		out["truncated"] = true
		out["hint"] = "Showing %d lines; pass start_line=%d for more." % [MAX_LINES, end_line + 1]
	var class_name_hint := _global_class_for(path)
	if class_name_hint != "":
		out["class_name"] = class_name_hint
	return out


func _global_class_for(path: String) -> String:
	for entry in ProjectSettings.get_global_class_list():
		if entry["path"] == path:
			return String(entry["class"])
	return ""


func list_script_files(p: Dictionary) -> Variant:
	var root := Paths.normalize(String(p.get("path", "res://")))
	if root == "":
		return invalid(Paths.describe_bad(String(p.get("path", ""))))
	var files: Array[String] = []
	_walk(root, files)
	var out := {"project_path": ProjectSettings.globalize_path("res://"), "files": files}
	if files.size() >= MAX_FILES:
		out["truncated"] = true
	return out


func _walk(dir_path: String, out: Array[String]) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for f in dir.get_files():
		if dir.is_link(f):
			continue
		if f.get_extension() == "gd" and out.size() < MAX_FILES:
			out.append(dir_path.path_join(f))
	for d in dir.get_directories():
		if not Paths.skip_dir(dir_path, d):
			_walk(dir_path.path_join(d), out)


func read_text_files(p: Dictionary) -> Variant:
	var out := {}
	for raw: Variant in p.get("paths", []):
		var path := Paths.normalize(String(raw))
		if path == "" or not Paths.is_text_file(path) or not FileAccess.file_exists(path):
			out[String(raw)] = null
			continue
		out[path] = FileAccess.get_file_as_string(path)
	return {"project_path": ProjectSettings.globalize_path("res://"), "files": out}


# --- writing ------------------------------------------------------------------------------


func _writable(raw: String) -> Variant:
	var path := Paths.normalize(raw)
	if path == "":
		return invalid(Paths.describe_bad(raw))
	var problem := Paths.writable_problem(path)
	if problem != "":
		return invalid("Can't write '%s': %s." % [path, problem])
	return path


func _unsaved_in_editor(path: String) -> bool:
	return path in EditorInterface.get_script_editor().get_unsaved_files()


## Writes the file and makes the editor pick it up: reloads a loaded Script, registers
## new files / class_names with the filesystem, refreshes open script tabs.
func _write(path: String, text: String) -> Variant:
	var existed := FileAccess.file_exists(path)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return fail("Could not write '%s' (%s)." % [path, error_string(FileAccess.get_open_error())])
	f.store_string(text)
	f.close()
	if ResourceLoader.has_cached(path):
		var res := load(path)
		if res is Script:
			(res as Script).source_code = text
			(res as Script).reload(true)
	var efs := EditorInterface.get_resource_filesystem()
	efs.update_file(path)
	await wait_for_filesystem()
	await _wait_for_class_name(path, text)
	var editor := EditorInterface.get_script_editor()
	if editor.get_unsaved_files().is_empty():
		for s in editor.get_open_scripts():
			if s.resource_path == path:
				editor.reload_open_files()
				break
	return {"path": path, "created": not existed, "lines": text.count("\n") + (0 if text.ends_with("\n") else 1)}


## A new or renamed class_name is registered a little after update_file(); wait for it
## (rescanning if needed) so the next tool call can already use the class.
func _wait_for_class_name(path: String, text: String) -> void:
	var re := RegEx.create_from_string("(?m)^class_name\\s+([A-Za-z_][A-Za-z0-9_]*)")
	var m := re.search(text)
	if m == null:
		return
	var cls := m.get_string(1)
	for attempt in 2:
		for i in 60:
			if Paths.global_class_path(cls) == path:
				return
			await plugin.get_tree().process_frame
		EditorInterface.get_resource_filesystem().scan()
		await plugin.get_tree().process_frame
		await wait_for_filesystem()


func write_script(p: Dictionary) -> Variant:
	var path: Variant = _writable(String(p.get("path", "")))
	if path is McpError:
		return path
	if _unsaved_in_editor(path) and not p.get("force", false):
		return fail("'%s' has unsaved changes in Godot's script editor; they'd be lost. Ask the user to save, or pass force=true." % path)
	return await _write(path, String(p.get("content", "")))


func edit_script(p: Dictionary) -> Variant:
	var path: Variant = _writable(String(p.get("path", "")))
	if path is McpError:
		return path
	if not FileAccess.file_exists(path):
		return fail("No file at '%s' (use write_script or create_script to make one)." % path)
	if _unsaved_in_editor(path) and not p.get("force", false):
		return fail("'%s' has unsaved changes in Godot's script editor; they'd be lost. Ask the user to save, or pass force=true." % path)
	var old_text := String(p.get("old_text", ""))
	if old_text == "":
		return invalid("`old_text` must not be empty")
	var text := FileAccess.get_file_as_string(path)
	var count := text.count(old_text)
	if count == 0:
		var hint := ""
		if text.count(old_text.strip_edges()) > 0:
			hint = " (it matches after trimming whitespace; check indentation: GDScript files usually use tabs)"
		return fail("`old_text` was not found in %s%s. Read the file again with read_script and copy the text exactly." % [path, hint])
	if count > 1 and not p.get("replace_all", false):
		return fail("`old_text` occurs %d times in %s; include more surrounding lines so it is unique, or pass replace_all=true." % [count, path])
	var new_text := text.replace(old_text, String(p.get("new_text", "")))
	var out: Variant = await _write(path, new_text)
	if out is Dictionary:
		out["replacements"] = count
	return out


const PHYSICS_BASES := ["CharacterBody2D", "CharacterBody3D", "RigidBody2D", "RigidBody3D", "AnimatableBody2D", "AnimatableBody3D", "VehicleBody3D"]


func create_script(p: Dictionary) -> Variant:
	var path: Variant = _writable(String(p.get("path", "")))
	if path is McpError:
		return path
	if String(path).get_extension() != "gd":
		return invalid("create_script makes GDScript (.gd) files; for other files use write_script.")
	if FileAccess.file_exists(path):
		return fail("'%s' already exists; use edit_script or write_script." % path)
	var base := String(p.get("extends", "Node")).strip_edges()
	var base_is_path := base.begins_with("res://")
	if base_is_path:
		if not FileAccess.file_exists(base):
			return fail("No script '%s' to extend." % base)
	elif not ClassDB.class_exists(base) and not _is_global_class(base):
		return invalid("Unknown base class '%s' (engine class, project class_name or res:// script)." % base)
	var cls := String(p.get("class_name", "")).strip_edges()
	if cls != "":
		if not cls.is_valid_identifier():
			return invalid("'%s' is not a valid class_name." % cls)
		if ClassDB.class_exists(cls) or _is_global_class(cls):
			return fail("A class named '%s' already exists." % cls)
	var lines: PackedStringArray = []
	if cls != "":
		lines.append("class_name " + cls)
	lines.append("extends " + ("\"%s\"" % base if base_is_path else base))
	var template := String(p.get("template", "default"))
	if template == "default":
		var native := base
		if base_is_path or not ClassDB.class_exists(base):
			native = ""
		var physics := native in PHYSICS_BASES
		lines.append("")
		lines.append("")
		lines.append("func _ready() -> void:")
		lines.append("\tpass")
		lines.append("")
		lines.append("")
		lines.append("func %s(delta: float) -> void:" % ("_physics_process" if physics else "_process"))
		lines.append("\tpass")
	elif template != "empty":
		return invalid("`template` must be default or empty")
	var out: Variant = await _write(path, "\n".join(lines) + "\n")
	if not (out is Dictionary):
		return out
	var attach_to := String(p.get("attach_to", ""))
	if attach_to != "":
		var attached: Variant = await attach_script({"node": attach_to, "path": path, "scene": p.get("scene", "")})
		if attached is McpError:
			out["attach_error"] = attached.message
		else:
			out["attached_to"] = attached["node"]
	return out


func _is_global_class(cls: String) -> bool:
	return Paths.global_class_path(cls) != ""


func attach_script(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var path := Paths.normalize(String(p.get("path", "")))
	if path == "" or not ResourceLoader.exists(path):
		return fail("No script at '%s'." % p.get("path", ""))
	var script := load(path) as Script
	if script == null:
		return fail("'%s' is not a script." % path)
	var base := String(script.get_instance_base_type())
	if base != "" and not node.is_class(base):
		return fail("%s extends %s, but %s is a %s. Use a script that extends %s (or a base class of it)." % [path, base, node_path(root, node), node.get_class(), node.get_class()])
	var ur := begin_action("attach_script", root)
	ur.add_do_method(node, "set_script", script)
	ur.add_undo_method(node, "set_script", node.get_script())
	commit_action(ur, "attach_script", root)
	return {"node": node_path(root, node), "script": path}


func detach_script(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var old: Script = node.get_script()
	if old == null:
		return fail("%s has no script." % node_path(root, node))
	var ur := begin_action("detach_script", root)
	ur.add_do_method(node, "set_script", null)
	ur.add_undo_method(node, "set_script", old)
	commit_action(ur, "detach_script", root)
	return {"node": node_path(root, node), "detached": old.resource_path}


## Test hook: opens a script in the script editor and types into it, leaving unsaved
## changes, so the unsaved-buffer guard can be tested.
func _test_make_unsaved(p: Dictionary) -> Variant:
	var script := load(String(p.get("path", ""))) as Script
	if script == null:
		return fail("no script")
	EditorInterface.edit_script(script)
	await plugin.get_tree().process_frame
	var editor := EditorInterface.get_script_editor().get_current_editor()
	if editor == null:
		return fail("the script editor did not open the script")
	var code := editor.get_base_editor() as CodeEdit
	code.insert_text_at_caret("# typed by a human\n")
	await plugin.get_tree().process_frame
	return {"unsaved": Array(EditorInterface.get_script_editor().get_unsaved_files())}
