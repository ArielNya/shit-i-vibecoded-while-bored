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
