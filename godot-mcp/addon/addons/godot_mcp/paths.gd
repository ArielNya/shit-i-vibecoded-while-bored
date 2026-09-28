@tool
extends RefCounted
## res:// path checks shared by the handlers. Tools only ever see project paths.

## Text files the script/search tools may read.
const TEXT_EXTENSIONS := [
	"gd", "cs", "gdshader", "gdshaderinc", "tscn", "tres", "godot", "cfg", "json",
	"md", "txt", "csv", "import", "gdextension", "xml", "yaml", "yml", "ini", "glsl",
]


## Normalizes a user-supplied path to "res://..." or returns "" if it is not a safe
## project path. Accepts "res://a/b", "a/b" and "/a/b" (relative to the project).
## Hidden segments are refused: .godot/ holds export_credentials.cfg (keystore
## passwords), and .git/, .env etc. are none of the agent's business. So are paths that
## pass through a symlink, which could lead outside the project.
static func normalize(path: String) -> String:
	var p := path.strip_edges().replace("\\", "/")
	if p.begins_with("res://"):
		p = p.substr(6)
	elif p.contains("://"):
		return ""
	while p.begins_with("/"):
		p = p.substr(1)
	var parts: PackedStringArray = []
	for part in p.split("/", false):
		if part == ".":
			continue
		if part == ".." or part.begins_with("."):
			return ""
		parts.append(part)
	var result := "res://" + "/".join(parts)
	if _through_link(parts):
		return ""
	return result


static func _through_link(parts: PackedStringArray) -> bool:
	var dir_path := "res://"
	for part in parts:
		var dir := DirAccess.open(dir_path)
		if dir == null:
			return false  # doesn't exist (yet): nothing to follow
		if dir.is_link(part):
			return true
		dir_path = dir_path.path_join(part)
	return false


## For error messages: "is outside the project" vs. "does not exist".
static func describe_bad(path: String) -> String:
	return "'%s' is not an allowed project path (use res://..., no '..', hidden folders or symlinks)" % path


## Files the script tools may create or overwrite. Scenes/resources go through the scene
## tools; project.godot through the settings tools; this plugin can't edit itself.
const WRITABLE_EXTENSIONS := ["gd", "cs", "gdshader", "gdshaderinc", "glsl", "json", "md", "txt", "csv"]


static func writable_problem(path: String) -> String:
	if path.begins_with("res://addons/godot_mcp/") or path == "res://addons/godot_mcp":
		return "the godot_mcp plugin's own files can't be edited through MCP"
	if path.get_extension().to_lower() not in WRITABLE_EXTENSIONS:
		return "only %s files can be written with this tool (scenes and resources: use the scene tools)" % ", ".join(WRITABLE_EXTENSIONS)
	return ""


static func is_text_file(path: String) -> bool:
	return path.get_extension().to_lower() in TEXT_EXTENSIONS


## Hidden or engine-internal folders that tools never walk into.
static func skip_dir(dir_path: String, name: String) -> bool:
	if name.begins_with("."):
		return true
	var dir := DirAccess.open(dir_path)
	if dir != null and dir.is_link(name):
		return true
	return FileAccess.file_exists(dir_path.path_join(name).path_join(".gdignore"))


## res:// path of a uid:// reference (other values are returned unchanged).
static func uid_to_path(value: String) -> String:
	if value.begins_with("uid://"):
		var id := ResourceUID.text_to_id(value)
		if ResourceUID.has_id(id):
			return ResourceUID.get_id_path(id)
	return value


## Script path of a project `class_name`, or "" if there is none.
static func global_class_path(cls: String) -> String:
	for entry in ProjectSettings.get_global_class_list():
		if String(entry["class"]) == cls:
			return String(entry["path"])
	return ""
