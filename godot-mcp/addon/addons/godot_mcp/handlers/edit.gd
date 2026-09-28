@tool
extends "base.gd"
## Scene editing: open/new/save/close scenes, add/remove/move/duplicate nodes, set
## properties, signals, groups, save branch as scene, and undo/redo of MCP actions.
##
## Every change to a scene is one EditorUndoRedoManager action named "MCP: <tool>", so
## the user can Ctrl+Z it and the agent can call `undo`.

const SCENE_EXTENSIONS := ["tscn", "scn"]


func register(h: Dictionary) -> void:
	h["open_scene"] = open_scene
	h["new_scene"] = new_scene
	h["save_scene"] = save_scene
	h["close_scene"] = close_scene
	h["add_node"] = add_node
	h["remove_node"] = remove_node
	h["rename_node"] = rename_node
	h["move_node"] = move_node
	h["duplicate_node"] = duplicate_node
	h["set_node_properties"] = set_node_properties
	h["list_signals"] = list_signals
	h["connect_signal"] = connect_signal
	h["disconnect_signal"] = disconnect_signal
	h["set_groups"] = set_groups
	h["save_branch_as_scene"] = save_branch_as_scene
	h["undo"] = undo
	h["redo"] = redo


# --- scenes -------------------------------------------------------------------------------


func _scene_summary(root: Node) -> Dictionary:
	var count := 0
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		count += 1
		for c in n.get_children():
			if c.owner == root:
				stack.append(c)
	return {
		"scene": root.scene_file_path,
		"root": String(root.name),
		"root_type": Codec.class_label(root),
		"node_count": count,
		"unsaved": root.scene_file_path in EditorInterface.get_unsaved_scenes(),
		"open_scenes": Array(EditorInterface.get_open_scenes()),
	}


func _scene_path(raw: String) -> Variant:
	var path := Paths.normalize(raw)
	if path == "":
		return invalid(Paths.describe_bad(raw))
	if path.get_extension().to_lower() not in SCENE_EXTENSIONS:
		return invalid("'%s' must end in .tscn (or .scn)." % raw)
	return path


func open_scene(p: Dictionary) -> Variant:
	if String(p.get("path", "")) == "":
		return invalid("`path` is required")
	var root: Variant = await edited_root(String(p["path"]))
	if root is McpError:
		return root
	return _scene_summary(root)


## Makes a node of `type`: a native class, a project class_name, or a script path.
func _instantiate_type(type: String) -> Variant:
	if type == "":
		return "a node type is required"
	if ClassDB.class_exists(type):
		if not ClassDB.is_parent_class(type, "Node"):
			return "'%s' is not a Node type" % type
		if not ClassDB.can_instantiate(type):
			return "'%s' is abstract and can't be created; use a concrete subclass" % type
		return ClassDB.instantiate(type)
	var script_path := ""
	if type.begins_with("res://") or type.ends_with(".gd") or type.ends_with(".cs"):
		script_path = Paths.normalize(type)
	else:
		script_path = Paths.global_class_path(type)
	if script_path == "" or not ResourceLoader.exists(script_path):
		return "unknown node type '%s' (not an engine class or project class_name)" % type
	var script := load(script_path) as Script
	if script == null:
		return "'%s' is not a script" % type
	# Like the editor: create the native base and attach the script (non-@tool scripts
	# can't be instantiated inside the editor).
	var base := String(script.get_instance_base_type())
	if base == "" or not ClassDB.is_parent_class(base, "Node"):
		return "'%s' is not a Node type (does the script have errors?)" % type
	var node: Node = ClassDB.instantiate(base)
	node.set_script(script)
	return node


func new_scene(p: Dictionary) -> Variant:
	var path: Variant = _scene_path(String(p.get("path", "")))
	if path is McpError:
		return path
	if FileAccess.file_exists(path):
		if not p.get("overwrite", false):
			return fail("'%s' already exists. Pass overwrite=true to replace it, or open_scene to edit it." % path)
		if path in EditorInterface.get_open_scenes():
			return fail("'%s' is open in the editor; close it before overwriting." % path)
	var made: Variant = _instantiate_type(String(p.get("root_type", "Node2D")))
	if made is String:
		return invalid(made)
	var root: Node = made
	var root_name := String(p.get("root_name", ""))
	if root_name == "":
		root_name = String(path).get_file().get_basename().to_pascal_case()
	root.name = root_name
	var packed := PackedScene.new()
	var err := packed.pack(root)
	root.free()
	if err != OK:
		return fail("Could not create the scene (%s)." % error_string(err))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(String(path).get_base_dir()))
	err = ResourceSaver.save(packed, path)
	if err != OK:
		return fail("Could not save '%s' (%s)." % [path, error_string(err)])
	EditorInterface.get_resource_filesystem().update_file(path)
	await wait_for_filesystem()
	var opened: Variant = await edited_root(path)
	if opened is McpError:
		return opened
	return _scene_summary(opened)


func save_scene(p: Dictionary) -> Variant:
	var root: Variant = await edited_root(String(p.get("scene", "")))
	if root is McpError:
		return root
	var target := String(p.get("path", ""))
	var saved_to := String(root.scene_file_path)
	if target == "":
		if saved_to == "":
			return invalid("This scene has never been saved; pass `path`.")
		var err := EditorInterface.save_scene()
		if err != OK:
			return fail("Saving failed (%s)." % error_string(err))
	else:
		var path: Variant = _scene_path(target)
		if path is McpError:
			return path
		if path != saved_to and FileAccess.file_exists(path) and not p.get("overwrite", false):
			return fail("'%s' already exists. Pass overwrite=true to replace it." % path)
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(String(path).get_base_dir()))
		EditorInterface.save_scene_as(path)
		saved_to = path
	EditorInterface.get_resource_filesystem().update_file(saved_to)
	await wait_for_filesystem()
	var out := _scene_summary(EditorInterface.get_edited_scene_root())
	out["saved"] = saved_to
	return out


func close_scene(p: Dictionary) -> Variant:
	var root: Variant = await edited_root(String(p.get("scene", "")))
	if root is McpError:
		return root
	var path := String(root.scene_file_path)
	if path in EditorInterface.get_unsaved_scenes() and not p.get("discard_changes", false):
		return fail("'%s' has unsaved changes. Call save_scene first, or pass discard_changes=true." % path)
	var err := EditorInterface.close_scene()
	if err != OK:
		return fail("Could not close the scene (%s)." % error_string(err))
	await plugin.get_tree().process_frame
	var current := EditorInterface.get_edited_scene_root()
	return {
		"closed": path,
		"edited_scene": current.scene_file_path if current != null else "",
		"open_scenes": Array(EditorInterface.get_open_scenes()),
	}


# --- nodes --------------------------------------------------------------------------------


## node and every descendant owned by the scene, with their owners (to restore on undo).
func _owned(root: Node, node: Node) -> Array:
	var out := []
	var stack: Array[Node] = [node]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n == node or n.owner != null:
			out.append([n, n.owner])
		for c in n.get_children():
			stack.append(c)
	return out


func _set_owner_recursive(node: Node, owner: Node, root: Node) -> void:
	# Instanced sub-scenes keep their internal owners; everything else joins the scene.
	node.owner = owner
	if node.scene_file_path != "" and node != root:
		return
	for c in node.get_children():
		if c.owner == null:
			_set_owner_recursive(c, owner, root)


func add_node(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p, "parent")
	if target is McpError:
		return target
	var root: Node = target[0]
	var parent: Node = target[1]
	var node: Node
	var instance_path := String(p.get("instance", ""))
	if instance_path != "":
		var path: Variant = _scene_path(instance_path)
		if path is McpError:
			return path
		if not ResourceLoader.exists(path):
			return fail("No scene at '%s' to instance." % path)
		if path == root.scene_file_path:
			return invalid("A scene can't contain an instance of itself.")
		var packed := load(path) as PackedScene
		if packed == null:
			return fail("'%s' is not a scene." % path)
		node = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	else:
		var made: Variant = _instantiate_type(String(p.get("type", "")))
		if made is String:
			return invalid(made + ". Pass `type` (e.g. Sprite2D) or `instance` (a .tscn).")
		node = made
	var wanted := String(p.get("name", ""))
	if wanted != "":
		if wanted.validate_node_name() != wanted:
			node.free()
			return invalid("'%s' is not a valid node name (no . : @ / \" %%)." % wanted)
		node.name = wanted
	var props: Variant = p.get("properties", {})
	if props is Dictionary and not props.is_empty():
		var err := Codec.set_properties_on(node, props)
		if err != "":
			node.free()
			return invalid(err)
	var index := int(p.get("index", -1))
	var ur := begin_action("add_node", root)
	ur.add_do_method(parent, "add_child", node, true)
	if index >= 0:
		ur.add_do_method(parent, "move_child", node, index)
	ur.add_do_method(self, "_set_owner_recursive", node, root, root)
	ur.add_do_reference(node)
	ur.add_undo_method(parent, "remove_child", node)
	commit_action(ur, "add_node", root)
	var out := {"path": node_path(root, node), "type": Codec.class_label(node)}
	if wanted != "" and String(node.name) != wanted:
		out["note"] = "A sibling is already called '%s', so the node was named '%s'." % [wanted, node.name]
	return out


func remove_node(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	if node == root:
		return invalid("The scene root can't be removed; use close_scene or new_scene instead.")
	var parent := node.get_parent()
	var path := node_path(root, node)
	var ur := begin_action("remove_node", root)
	ur.add_do_method(parent, "remove_child", node)
	ur.add_undo_method(parent, "add_child", node)
	ur.add_undo_method(parent, "move_child", node, node.get_index())
	for pair: Array in _owned(root, node):
		ur.add_undo_method(pair[0], "set_owner", pair[1])
	ur.add_undo_reference(node)
	commit_action(ur, "remove_node", root)
	return {"removed": path}


func rename_node(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var new_name := String(p.get("new_name", ""))
	if new_name == "" or new_name.validate_node_name() != new_name:
		return invalid("'%s' is not a valid node name (no . : @ / \" %%)." % new_name)
	var parent := node.get_parent()
	if parent != null and parent.has_node(NodePath(new_name)) and parent.get_node(NodePath(new_name)) != node:
		return fail("'%s' already has a child called '%s'." % [node_path(root, parent), new_name])
	var old_path := node_path(root, node)
	var ur := begin_action("rename_node", root)
	ur.add_do_method(node, "set_name", new_name)
	ur.add_undo_method(node, "set_name", String(node.name))
	commit_action(ur, "rename_node", root)
	return {"old_path": old_path, "path": node_path(root, node), "note": "NodePaths in scripts ($%s, get_node) are not updated automatically." % old_path}


func move_node(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	if node == root:
		return invalid("The scene root can't be moved.")
	var old_parent := node.get_parent()
	var old_index := node.get_index()
	var new_parent := old_parent
	var parent_path := String(p.get("new_parent", ""))
	if parent_path != "":
		new_parent = find_node(root, parent_path)
		if new_parent == null:
			return fail("No node '%s' to move into." % parent_path)
		if new_parent == node or node.is_ancestor_of(new_parent):
			return invalid("A node can't be moved into itself or its own children.")
	var index := int(p.get("index", -1))
	var keep: bool = p.get("keep_global_transform", true)
	var ur := begin_action("move_node", root)
	if new_parent != old_parent:
		ur.add_do_method(node, "reparent", new_parent, keep)
		ur.add_undo_method(node, "reparent", old_parent, keep)
		ur.add_undo_method(old_parent, "move_child", node, old_index)
		for pair: Array in _owned(root, node):
			ur.add_do_method(pair[0], "set_owner", pair[1])
			ur.add_undo_method(pair[0], "set_owner", pair[1])
	if index >= 0:
		ur.add_do_method(new_parent, "move_child", node, index)
		if new_parent == old_parent:
			ur.add_undo_method(old_parent, "move_child", node, old_index)
	commit_action(ur, "move_node", root)
	return {"path": node_path(root, node), "index": node.get_index()}


func duplicate_node(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	if node == root:
		return invalid("The scene root can't be duplicated; use save_scene with a new path.")
	var parent := node.get_parent()
	var parent_path := String(p.get("parent", ""))
	if parent_path != "":
		parent = find_node(root, parent_path)
		if parent == null:
			return fail("No node '%s' to put the copy into." % parent_path)
	var copy := node.duplicate(Node.DUPLICATE_SIGNALS | Node.DUPLICATE_GROUPS | Node.DUPLICATE_SCRIPTS | Node.DUPLICATE_USE_INSTANTIATION)
	var wanted := String(p.get("name", ""))
	if wanted != "":
		if wanted.validate_node_name() != wanted:
			copy.free()
			return invalid("'%s' is not a valid node name." % wanted)
		copy.name = wanted
	var ur := begin_action("duplicate_node", root)
	ur.add_do_method(parent, "add_child", copy, true)
	if parent == node.get_parent():
		ur.add_do_method(parent, "move_child", copy, node.get_index() + 1)
	ur.add_do_method(self, "_set_owner_recursive", copy, root, root)
	ur.add_do_reference(copy)
	ur.add_undo_method(parent, "remove_child", copy)
	commit_action(ur, "duplicate_node", root)
	return {"path": node_path(root, copy), "type": Codec.class_label(copy)}


func set_node_properties(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var props: Variant = p.get("properties", {})
	if not (props is Dictionary) or props.is_empty():
		return invalid("`properties` must be an object like {\"position\": \"Vector2(10, 20)\"}")
	var infos := Codec.property_infos(node)
	var decoded := {}
	var errors: Array[String] = []
	for key: Variant in props:
		var pname := String(key)
		if pname == "script":
			errors.append("script: use attach_script / detach_script")
			continue
		if pname == "name":
			errors.append("name: use rename_node")
			continue
		if not infos.has(pname):
			errors.append(Codec.unknown_property_message(node, pname, infos))
			continue
		var conv := Codec.decode_property(props[key], infos[pname])
		if not conv[0]:
			errors.append("%s: %s" % [pname, conv[1]])
			continue
		decoded[pname] = conv[1]
	if not errors.is_empty():
		return invalid("Nothing was changed. " + " | ".join(errors))
	var ur := begin_action("set_node_properties", root)
	for pname: String in decoded:
		ur.add_do_property(node, pname, decoded[pname])
		ur.add_undo_property(node, pname, node.get(pname))
		if decoded[pname] is Resource:
			ur.add_do_reference(decoded[pname])
	commit_action(ur, "set_node_properties", root)
	var changed := {}
	for pname: String in decoded:
		changed[pname] = Codec.encode(node.get(pname), root)
	return {"node": node_path(root, node), "values": changed}


# --- signals & groups ---------------------------------------------------------------------


func _connection_entry(root: Node, c: Dictionary) -> Dictionary:
	var callable: Callable = c["callable"]
	var target: Object = callable.get_object()
	var entry := {"signal": String((c["signal"] as Signal).get_name()), "method": String(callable.get_method())}
	if target is Node:
		entry["target"] = node_path(root, target) if (target == root or root.is_ancestor_of(target)) else String(target.get_path())
	var src: Object = (c["signal"] as Signal).get_object()
	if src is Node:
		entry["source"] = node_path(root, src) if (src == root or root.is_ancestor_of(src)) else String(src.get_path())
	var flags: int = c.get("flags", 0)
	if flags & CONNECT_DEFERRED:
		entry["deferred"] = true
	if flags & CONNECT_ONE_SHOT:
		entry["one_shot"] = true
	return entry


func list_signals(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var filter := String(p.get("filter", "")).to_lower()
	var signals: Array[String] = []
	var script: Script = node.get_script()
	var script_signals := {}
	if script != null:
		for s in script.get_script_signal_list():
			script_signals[s["name"]] = true
	for s in node.get_signal_list():
		var sname := String(s["name"])
		if filter != "" and not sname.to_lower().contains(filter):
			continue
		var args: PackedStringArray = []
		for a: Dictionary in s["args"]:
			args.append("%s: %s" % [a["name"], Codec.type_label(a)])
		signals.append("%s(%s)%s" % [sname, ", ".join(args), "  [script]" if script_signals.has(sname) else ""])
	var outgoing: Array = []
	for s in node.get_signal_list():
		for c in node.get_signal_connection_list(s["name"]):
			if int(c.get("flags", 0)) & CONNECT_PERSIST:
				outgoing.append(_connection_entry(root, c))
	var incoming: Array = []
	for c in node.get_incoming_connections():
		if int(c.get("flags", 0)) & CONNECT_PERSIST:
			incoming.append(_connection_entry(root, c))
	return {"node": node_path(root, node), "signals": signals, "connections": outgoing, "incoming_connections": incoming}


func _signal_args(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var sig := String(p.get("signal", ""))
	if not node.has_signal(sig):
		return fail("%s has no signal '%s'. See list_signals." % [node_path(root, node), sig])
	var receiver := find_node(root, String(p.get("target", "")))
	if receiver == null:
		return fail("No target node '%s'." % p.get("target", ""))
	var method := String(p.get("method", ""))
	if not method.is_valid_identifier():
		return invalid("`method` must be a function name, e.g. _on_button_pressed")
	return [root, node, sig, receiver, method]


func connect_signal(p: Dictionary) -> Variant:
	var args: Variant = await _signal_args(p)
	if args is McpError:
		return args
	var root: Node = args[0]
	var node: Node = args[1]
	var callable := Callable(args[3], args[4])
	if node.is_connected(args[2], callable):
		return fail("Already connected.")
	var flags := CONNECT_PERSIST
	if p.get("deferred", false):
		flags |= CONNECT_DEFERRED
	if p.get("one_shot", false):
		flags |= CONNECT_ONE_SHOT
	var ur := begin_action("connect_signal", root)
	ur.add_do_method(node, "connect", args[2], callable, flags)
	ur.add_undo_method(node, "disconnect", args[2], callable)
	commit_action(ur, "connect_signal", root)
	var out := {"connected": "%s.%s -> %s.%s" % [node_path(root, node), args[2], node_path(root, args[3]), args[4]]}
	if not (args[3] as Node).has_method(args[4]):
		out["warning"] = "%s has no method '%s' yet: add `func %s(...)` to its script, or the game will error when the signal fires." % [node_path(root, args[3]), args[4], args[4]]
	return out


func disconnect_signal(p: Dictionary) -> Variant:
	var args: Variant = await _signal_args(p)
	if args is McpError:
		return args
	var root: Node = args[0]
	var node: Node = args[1]
	var callable := Callable(args[3], args[4])
	if not node.is_connected(args[2], callable):
		return fail("There is no such connection.")
	var flags := CONNECT_PERSIST
	for c in node.get_signal_connection_list(args[2]):
		if c["callable"] == callable:
			flags = int(c["flags"])
	var ur := begin_action("disconnect_signal", root)
	ur.add_do_method(node, "disconnect", args[2], callable)
	ur.add_undo_method(node, "connect", args[2], callable, flags)
	commit_action(ur, "disconnect_signal", root)
	return {"disconnected": "%s.%s -> %s.%s" % [node_path(root, node), args[2], node_path(root, args[3]), args[4]]}


func set_groups(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	var add: Array = p.get("add", [])
	var remove: Array = p.get("remove", [])
	var ur := begin_action("set_groups", root)
	for g: Variant in add:
		var group := String(g).strip_edges()
		if group == "" or node.is_in_group(group):
			continue
		ur.add_do_method(node, "add_to_group", group, true)
		ur.add_undo_method(node, "remove_from_group", group)
	for g: Variant in remove:
		var group := String(g)
		if not node.is_in_group(group):
			continue
		ur.add_do_method(node, "remove_from_group", group)
		ur.add_undo_method(node, "add_to_group", group, true)
	commit_action(ur, "set_groups", root)
	var groups: Array[String] = []
	for g in node.get_groups():
		if not String(g).begins_with("_"):
			groups.append(String(g))
	return {"node": node_path(root, node), "groups": groups}


# --- save branch as scene -------------------------------------------------------------------


func save_branch_as_scene(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var node: Node = target[1]
	if node == root:
		return invalid("That's the whole scene; use save_scene with a new path instead.")
	var path: Variant = _scene_path(String(p.get("path", "")))
	if path is McpError:
		return path
	if FileAccess.file_exists(path) and not p.get("overwrite", false):
		return fail("'%s' already exists. Pass overwrite=true to replace it." % path)
	# Pack a copy whose nodes belong to the branch root instead of the scene root.
	var copy := node.duplicate(Node.DUPLICATE_SIGNALS | Node.DUPLICATE_GROUPS | Node.DUPLICATE_SCRIPTS | Node.DUPLICATE_USE_INSTANTIATION)
	for c in copy.get_children():
		_set_owner_recursive(c, copy, copy)
	var packed := PackedScene.new()
	var err := packed.pack(copy)
	copy.free()
	if err != OK:
		return fail("Could not pack the branch (%s)." % error_string(err))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(String(path).get_base_dir()))
	err = ResourceSaver.save(packed, path)
	if err != OK:
		return fail("Could not save '%s' (%s)." % [path, error_string(err)])
	EditorInterface.get_resource_filesystem().update_file(path)
	await wait_for_filesystem()
	# Swap the branch for an instance of the new scene.
	var instance := (load(path) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	instance.name = node.name
	var parent := node.get_parent()
	var index := node.get_index()
	var ur := begin_action("save_branch_as_scene", root)
	ur.add_do_method(parent, "remove_child", node)
	ur.add_do_method(parent, "add_child", instance, true)
	ur.add_do_method(parent, "move_child", instance, index)
	ur.add_do_method(instance, "set_owner", root)
	ur.add_do_reference(instance)
	ur.add_undo_method(parent, "remove_child", instance)
	ur.add_undo_method(parent, "add_child", node)
	ur.add_undo_method(parent, "move_child", node, index)
	for pair: Array in _owned(root, node):
		ur.add_undo_method(pair[0], "set_owner", pair[1])
	ur.add_undo_reference(node)
	commit_action(ur, "save_branch_as_scene", root)
	return {"saved": path, "instance": node_path(root, instance)}


# --- undo / redo ----------------------------------------------------------------------------


func undo(p: Dictionary) -> Variant:
	return _step(int(p.get("steps", 1)), true)


func redo(p: Dictionary) -> Variant:
	return _step(int(p.get("steps", 1)), false)


## Like the editor's Ctrl+Z: only the edited scene's history and the global one
## (project settings, input map) are candidates; MCP actions in other open scenes wait
## until that scene is current again.
func _step(steps: int, backwards: bool) -> Variant:
	var source: Array = history["done"] if backwards else history["undone"]
	var dest: Array = history["undone"] if backwards else history["done"]
	var manager := plugin.get_undo_redo()
	var allowed := [EditorUndoRedoManager.GLOBAL_HISTORY]
	var root := EditorInterface.get_edited_scene_root()
	if root != null:
		allowed.append(manager.get_object_history_id(root))
	var reverted: Array[String] = []
	for i in max(1, steps):
		var idx := -1
		for j in range(source.size() - 1, -1, -1):
			if source[j]["history"] in allowed:
				idx = j
				break
		if idx < 0:
			break
		var entry: Dictionary = source[idx]
		var ur := manager.get_history_undo_redo(entry["history"])
		if ur == null:
			source.remove_at(idx)
			continue
		if backwards:
			if not ur.has_undo() or ur.get_current_action_name() != entry["name"]:
				return _stale(entry, reverted, ur.get_current_action_name() if ur.has_undo() else "")
			ur.undo()
		else:
			if not ur.has_redo():
				return _stale(entry, reverted, "")
			ur.redo()
			if ur.get_current_action_name() != entry["name"]:
				ur.undo()  # that was someone else's action: put it back
				return _stale(entry, reverted, "another action")
		source.remove_at(idx)
		dest.append(entry)
		reverted.append(entry["name"])
	if reverted.is_empty():
		var where := " in %s" % root.scene_file_path if root != null else ""
		return fail("Nothing to %s: no MCP changes%s %s." % ["undo" if backwards else "redo", where, "left" if backwards else "were undone"])
	return {"undone" if backwards else "redone": reverted}


func _stale(entry: Dictionary, done_so_far: Array[String], newest: String) -> Variant:
	# That history moved on without us: forget our entries for it.
	for key in ["done", "undone"]:
		history[key] = history[key].filter(func(e: Dictionary) -> bool: return e["history"] != entry["history"])
	var msg := "Stopped: '%s' is no longer the newest change in its history" % entry["name"]
	if newest != "":
		msg += " (newest is '%s')" % newest
	msg += " — someone edited since. Undo in the editor instead."
	if not done_so_far.is_empty():
		msg += " Already done: %s." % ", ".join(done_so_far)
	return fail(msg)
