@tool
extends "base.gd"
## Read-only scene tools: tree and node properties.


func register(h: Dictionary) -> void:
	h["get_scene_tree"] = get_scene_tree
	h["get_node_properties"] = get_node_properties


func get_scene_tree(p: Dictionary) -> Variant:
	var resolved: Variant = resolve_scene(String(p.get("scene", "")))
	if resolved is McpError:
		return resolved
	var root: Node = resolved[0]
	var temporary: bool = resolved[1]
	var start := find_node(root, String(p.get("node", "")))
	if start == null:
		if temporary:
			root.free()
		return fail("No node '%s' in the scene. Paths are relative to the scene root, e.g. 'Player/Sprite2D'." % p.get("node"))
	var max_depth := int(p.get("max_depth", 8))
	var max_nodes := int(p.get("max_nodes", 300))
	var include_internal: bool = p.get("include_internal", false)
	var nodes: Array[Dictionary] = []
	var state := {"truncated": false}
	_walk(root, start, 0, max_depth, max_nodes, include_internal, nodes, state)
	var out := {
		"scene": root.scene_file_path,
		"root_type": root.get_class(),
		# "editor": the live scene open in the editor (may have unsaved changes);
		# "file": loaded from disk just for this call.
		"source": "file" if temporary else "editor",
		"nodes": nodes,
	}
	if state["truncated"]:
		out["truncated"] = true
		out["hint"] = "Stopped at max_nodes=%d. Pass `node` to look at a subtree." % max_nodes
	if temporary:
		root.free()
	return out


func _walk(root: Node, node: Node, depth: int, max_depth: int, max_nodes: int, include_internal: bool, out: Array[Dictionary], state: Dictionary) -> void:
	if out.size() >= max_nodes:
		state["truncated"] = true
		return
	var entry := {"path": node_path(root, node), "type": Codec.class_label(node)}
	if Codec.class_label(node) != node.get_class():
		entry["native_type"] = node.get_class()
	var script: Script = node.get_script()
	if script != null:
		entry["script"] = script.resource_path
	if node != root and node.scene_file_path != "":
		entry["instance_of"] = node.scene_file_path
	var groups: Array[String] = []
	for g in node.get_groups():
		if not String(g).begins_with("_"):
			groups.append(String(g))
	if not groups.is_empty():
		entry["groups"] = groups
	if node is CanvasItem and not (node as CanvasItem).visible:
		entry["visible"] = false
	elif node is Node3D and not (node as Node3D).visible:
		entry["visible"] = false
	var children := _visible_children(root, node, include_internal)
	if depth >= max_depth and not children.is_empty():
		entry["children_not_shown"] = children.size()
	out.append(entry)
	if depth >= max_depth:
		return
	for child in children:
		_walk(root, child, depth + 1, max_depth, max_nodes, include_internal, out, state)


## Children as the Scene dock shows them: nodes inside an instanced sub-scene are hidden
## unless the instance has "Editable Children" on (or include_internal is set).
func _visible_children(root: Node, node: Node, include_internal: bool) -> Array[Node]:
	var out: Array[Node] = []
	for child in node.get_children():
		if include_internal or child.owner == root or (child.owner != null and root.is_editable_instance(child.owner)):
			out.append(child)
	return out


func get_node_properties(p: Dictionary) -> Variant:
	var resolved: Variant = resolve_scene(String(p.get("scene", "")))
	if resolved is McpError:
		return resolved
	var root: Node = resolved[0]
	var temporary: bool = resolved[1]
	var node := find_node(root, String(p.get("node", "")))
	if node == null:
		if temporary:
			root.free()
		return fail("No node '%s' in the scene." % p.get("node"))
	var result := Codec.describe_properties(node, root, String(p.get("filter", "")), p.get("include_defaults", false))
	result["node"] = node_path(root, node)
	result["type"] = Codec.class_label(node)
	if temporary:
		root.free()
	return result
