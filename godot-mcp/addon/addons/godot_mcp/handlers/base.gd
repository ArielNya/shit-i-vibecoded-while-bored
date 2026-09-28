@tool
extends RefCounted
## Common helpers for handler modules. Each module overrides register().

const McpError := preload("../mcp_error.gd")
const Protocol := preload("../protocol.gd")
const Codec := preload("../codec.gd")
const Paths := preload("../paths.gd")
const History := preload("../history.gd")
const DebuggerPlugin := preload("../debugger_plugin.gd")

var plugin: EditorPlugin
## Shared history.gd instance: the MCP actions available to undo/redo.
var history: History
## The editor side of the running-game bridge.
var debugger: DebuggerPlugin


## Adds this module's methods to `handlers` (method name -> Callable).
func register(_handlers: Dictionary) -> void:
	pass


func fail(message: String) -> McpError:
	return McpError.new(message)


func invalid(message: String) -> McpError:
	return McpError.new(message, Protocol.INVALID_PARAMS)


## Starts an undoable editor action named "MCP: <name>". `context` picks the history:
## a node of the edited scene -> that scene's history, anything else -> global.
func begin_action(action_name: String, context: Object) -> EditorUndoRedoManager:
	var ur := plugin.get_undo_redo()
	ur.create_action("MCP: " + action_name, UndoRedo.MERGE_DISABLE, context)
	return ur


func commit_action(ur: EditorUndoRedoManager, action_name: String, context: Object) -> void:
	ur.commit_action()
	history.record(ur.get_object_history_id(context), "MCP: " + action_name)


## The scene to edit: the edited scene, or `scene` (a res:// path), which is opened in the
## editor (or switched to) first. Returns the scene root or an McpError.
func edited_root(scene: String) -> Variant:
	var current := EditorInterface.get_edited_scene_root()
	if scene == "":
		if current == null:
			return fail("No scene is open in the editor. Open one with open_scene or create one with new_scene.")
		return current
	var path := Paths.normalize(scene)
	if path == "":
		return invalid(Paths.describe_bad(scene))
	if current != null and current.scene_file_path == path:
		return current
	if not ResourceLoader.exists(path):
		return fail("No scene at '%s'." % path)
	EditorInterface.open_scene_from_path(path)
	await plugin.get_tree().process_frame
	current = EditorInterface.get_edited_scene_root()
	if current == null or current.scene_file_path != path:
		return fail("Could not open '%s' in the editor (see Godot's Output panel)." % path)
	return current


## [root, node] for p.node in the scene to edit, or an McpError.
func target_node(p: Dictionary, key: String = "node") -> Variant:
	var root: Variant = await edited_root(String(p.get("scene", "")))
	if root is McpError:
		return root
	var path := String(p.get(key, ""))
	var node := find_node(root, path)
	if node == null:
		return fail("No node '%s' in %s. Node paths are relative to the scene root ('.' is the root), e.g. 'Player/Sprite2D'." % [path, root.scene_file_path])
	return [root, node]


## Waits until the editor's resource filesystem has finished (re)scanning, so newly
## created files are visible.
func wait_for_filesystem() -> void:
	var efs := EditorInterface.get_resource_filesystem()
	var frames := 0
	while efs.is_scanning() and frames < 3600:
		await plugin.get_tree().process_frame
		frames += 1


## The scene a tool should work on: the edited scene, or `scene` loaded read-only.
## Returns [root: Node, temporary: bool] or an McpError. Free temporary roots when done.
func resolve_scene(scene: String) -> Variant:
	if scene == "":
		var root := EditorInterface.get_edited_scene_root()
		if root == null:
			return fail("No scene is open in the editor. Pass `scene` (a res:// .tscn path) or open one.")
		return [root, false]
	var path := Paths.normalize(scene)
	if path == "":
		return invalid(Paths.describe_bad(scene))
	var edited := EditorInterface.get_edited_scene_root()
	if edited != null and edited.scene_file_path == path:
		return [edited, false]  # prefer the live (possibly unsaved) version
	if not ResourceLoader.exists(path, "PackedScene"):
		return fail("No scene at '%s'." % path)
	var packed := load(path) as PackedScene
	if packed == null:
		return fail("'%s' is not a scene." % path)
	var root := packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	if root == null:
		return fail("Could not instantiate '%s' (see Godot's Output panel)." % path)
	return [root, true]


## Resolves a NodePath relative to the scene root ("" or "." is the root itself).
func find_node(root: Node, path: String) -> Node:
	var p := path.strip_edges()
	if p == "" or p == "." or p == "/root/" + String(root.name) or p == String(root.name):
		return root
	if p.begins_with(String(root.name) + "/"):
		var direct := root.get_node_or_null(p.substr(String(root.name).length() + 1))
		if direct != null:
			return direct
	return root.get_node_or_null(p)


func node_path(root: Node, node: Node) -> String:
	return "." if node == root else String(root.get_path_to(node))


func uid_to_path(value: String) -> String:
	if value.begins_with("uid://"):
		var id := ResourceUID.text_to_id(value)
		if ResourceUID.has_id(id):
			return ResourceUID.get_id_path(id)
	return value


static func page(items: Array, offset: int, limit: int) -> Dictionary:
	var out := {"items": items.slice(offset, offset + limit), "total": items.size()}
	if offset + limit < items.size():
		out["next_offset"] = offset + limit
	return out
