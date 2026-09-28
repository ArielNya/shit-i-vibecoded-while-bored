extends Node
## Autoload "McpRuntime": the running game's side of godot-mcp.
##
## Only active when the game was started from the editor with the debugger attached
## (EngineDebugger.is_active()); otherwise it does nothing, and exported builds don't
## include it at all (see export_plugin.gd).
##
## Messages ride Godot's own editor<->game debugger connection:
##   editor -> game  "mcp:req"  [{id, method, params}]
##   game -> editor  "mcp:res"  [{id, result} | {id, error}]
##                   "mcp:log"  [[entries...]]   printed output, warnings, errors
##                   "mcp:hello" [info]           once the runtime is ready

const Codec := preload("../codec.gd")
const LogCapture := preload("../log_capture.gd")

const MAX_LIVE_NODES := 2000

var _logger: LogCapture
var _sent_seq := 0
var _handlers := {}


func _ready() -> void:
	if not EngineDebugger.is_active():
		set_process(false)
		set_physics_process(false)
		return
	process_mode = Node.PROCESS_MODE_ALWAYS  # keep answering while the game is paused
	_logger = LogCapture.new()
	OS.add_logger(_logger)
	_handlers = {
		"ping": _ping,
		"get_tree": _get_tree,
		"get_properties": _get_properties,
		"set_properties": _set_properties,
		"screenshot": _screenshot,
		"input": _input_events,
		"wait": _wait,
		"performance": _performance,
	}
	EngineDebugger.register_message_capture("mcp", _on_message)
	# Say hello once the main scene is in the tree.
	await get_tree().process_frame
	EngineDebugger.send_message("mcp:hello", [_info()])


func _exit_tree() -> void:
	if _logger != null:
		_flush_logs()
		OS.remove_logger(_logger)
	if EngineDebugger.is_active() and EngineDebugger.has_capture("mcp"):
		EngineDebugger.unregister_message_capture("mcp")


func _process(_delta: float) -> void:
	_flush_logs()


func _flush_logs() -> void:
	if _logger == null:
		return
	var entries := _logger.entries_since(_sent_seq)
	if entries.is_empty():
		return
	_sent_seq = int(entries[entries.size() - 1]["seq"])
	EngineDebugger.send_message("mcp:log", [entries])


func _info() -> Dictionary:
	var scene := get_tree().current_scene
	return {
		"pid": OS.get_process_id(),
		"scene": scene.scene_file_path if scene != null else "",
		"headless": DisplayServer.get_name() == "headless",
		"godot_version": Engine.get_version_info()["string"],
	}


func _on_message(message: String, data: Array) -> bool:
	if message != "req" or data.is_empty() or not (data[0] is Dictionary):
		return false
	_handle(data[0])
	return true


func _handle(req: Dictionary) -> void:
	var id: Variant = req.get("id")
	var method := String(req.get("method", ""))
	var reply := {"id": id}
	if not _handlers.has(method):
		reply["error"] = "unknown runtime method '%s'" % method
	else:
		var mark := _logger.mark()
		var value: Variant = await (_handlers[method] as Callable).call(req.get("params", {}))
		if value is String and String(value).begins_with("ERROR: "):
			reply["error"] = String(value).substr(7)
		elif value == null:
			var logged := _logger.errors_since(mark)
			reply["error"] = "internal error in the game-side runtime" + ("" if logged.is_empty() else ": " + logged[0]["message"])
		else:
			reply["result"] = value
	_flush_logs()
	EngineDebugger.send_message("mcp:res", [reply])


static func _err(message: String) -> String:
	return "ERROR: " + message


# --- nodes ---------------------------------------------------------------------------------


func _scene_root() -> Node:
	var scene := get_tree().current_scene
	return scene if scene != null else get_tree().root


## "" or "." = current scene; "/root/..." absolute; otherwise relative to the current scene.
func _find(path: String) -> Node:
	var p := path.strip_edges()
	var root := _scene_root()
	if p == "" or p == ".":
		return root
	if p.begins_with("/"):
		return get_tree().root.get_node_or_null(p)
	return root.get_node_or_null(p)


func _path_of(node: Node) -> String:
	var root := _scene_root()
	if node == root:
		return "."
	if root.is_ancestor_of(node):
		return String(root.get_path_to(node))
	return String(node.get_path())


func _ping(_p: Dictionary) -> Variant:
	var info := _info()
	info["frame"] = Engine.get_process_frames()
	info["fps"] = Engine.get_frames_per_second()
	info["paused"] = get_tree().paused
	return info


func _get_tree(p: Dictionary) -> Variant:
	var start := _find(String(p.get("node", "")))
	if start == null:
		return _err("No node '%s' in the running game." % p.get("node", ""))
	var max_depth := int(p.get("max_depth", 8))
	var max_nodes := int(p.get("max_nodes", 300))
	var nodes: Array = []
	var stack: Array = [[start, 0]]
	var truncated := false
	while not stack.is_empty():
		var item: Array = stack.pop_back()
		var node: Node = item[0]
		var depth: int = item[1]
		if nodes.size() >= min(max_nodes, MAX_LIVE_NODES):
			truncated = true
			break
		var entry := {"path": _path_of(node), "type": Codec.class_label(node)}
		if node is CanvasItem:
			if not (node as CanvasItem).visible:
				entry["visible"] = false
			if node is Node2D:
				entry["position"] = var_to_str((node as Node2D).global_position)
		elif node is Node3D:
			if not (node as Node3D).visible:
				entry["visible"] = false
			entry["position"] = var_to_str((node as Node3D).global_position)
		var groups: Array = []
		for g in node.get_groups():
			if not String(g).begins_with("_"):
				groups.append(String(g))
		if not groups.is_empty():
			entry["groups"] = groups
		var children := node.get_children()
		if depth >= max_depth and not children.is_empty():
			entry["children_not_shown"] = children.size()
		nodes.append(entry)
		if depth < max_depth:
			for i in range(children.size() - 1, -1, -1):
				stack.append([children[i], depth + 1])
	var autoloads: Array = []
	for child in get_tree().root.get_children():
		if child != get_tree().current_scene and child != self:
			autoloads.append(String(child.name))
	var out := {"scene": _info()["scene"], "nodes": nodes, "autoloads": autoloads}
	if truncated:
		out["truncated"] = true
	return out


func _get_properties(p: Dictionary) -> Variant:
	var node := _find(String(p.get("node", "")))
	if node == null:
		return _err("No node '%s' in the running game." % p.get("node", ""))
	var out := Codec.describe_properties(node, _scene_root(), String(p.get("filter", "")), p.get("include_defaults", false))
	out["node"] = _path_of(node)
	out["type"] = Codec.class_label(node)
	return out


func _set_properties(p: Dictionary) -> Variant:
	var node := _find(String(p.get("node", "")))
	if node == null:
		return _err("No node '%s' in the running game." % p.get("node", ""))
	var props: Variant = p.get("properties", {})
	if not (props is Dictionary) or props.is_empty():
		return _err("`properties` must be a non-empty object")
	var infos := Codec.property_infos(node)
	var decoded := {}
	for key: Variant in props:
		var pname := String(key)
		if not infos.has(pname):
			return _err(Codec.unknown_property_message(node, pname, infos))
		var conv := Codec.decode_property(props[key], infos[pname])
		if not conv[0]:
			return _err("%s: %s" % [pname, conv[1]])
		decoded[pname] = conv[1]
	var values := {}
	for pname: String in decoded:
		node.set(pname, decoded[pname])
		values[pname] = Codec.encode(node.get(pname), _scene_root())
	return {"node": _path_of(node), "values": values}


# --- screenshot ----------------------------------------------------------------------------


func _screenshot(p: Dictionary) -> Variant:
	if DisplayServer.get_name() == "headless":
		return _err("The game is running headless, so it renders nothing to capture. Run it with a window: run_project display=window, from an editor that has a display (e.g. under Xvfb).")
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image == null or image.is_empty():
		return _err("The game viewport returned no image.")
	var size := int(p.get("size", 768))
	var w := image.get_width()
	var h := image.get_height()
	if maxi(w, h) > size:
		var scale := float(size) / maxi(w, h)
		image.resize(max(1, roundi(w * scale)), max(1, roundi(h * scale)), Image.INTERPOLATE_LANCZOS)
	if image.get_format() != Image.FORMAT_RGBA8 and image.get_format() != Image.FORMAT_RGB8:
		image.convert(Image.FORMAT_RGBA8)
	return {
		"image_base64": Marshalls.raw_to_base64(image.save_png_to_buffer()),
		"mime_type": "image/png",
		"width": image.get_width(),
		"height": image.get_height(),
		"frame": Engine.get_process_frames(),
	}


# --- input ---------------------------------------------------------------------------------

## Each event: {"action": "jump"} | {"key": "Space"} | {"mouse_button": "left", "position": [x, y]}
## | {"mouse_motion": [x, y]} (+ "strength" for actions). mode: "tap" (press, hold for
## `frames`, release), "press", or "release".
func _input_events(p: Dictionary) -> Variant:
	var events: Array = p.get("events", [])
	var mode := String(p.get("mode", "tap"))
	var frames: int = max(1, int(p.get("frames", 1)))
	if events.is_empty():
		return _err("`events` must list at least one input")
	var built: Array = []
	for spec: Variant in events:
		if not (spec is Dictionary):
			return _err("each event must be an object")
		var made: Variant = _build_event(spec)
		if made is String:
			return _err(made)
		built.append(made)
	if mode in ["tap", "press"]:
		for ev: InputEvent in built:
			_send(ev, true)
	if mode == "tap":
		for i in frames:
			await get_tree().physics_frame
		for ev: InputEvent in built:
			_send(ev, false)
		await get_tree().physics_frame
	elif mode == "release":
		for ev: InputEvent in built:
			_send(ev, false)
	elif mode != "press":
		return _err("`mode` must be tap, press or release")
	return {"sent": events.size(), "mode": mode, "frames": frames if mode == "tap" else 0, "frame": Engine.get_physics_frames()}


func _build_event(spec: Dictionary) -> Variant:
	if spec.has("action"):
		var action := String(spec["action"])
		if not InputMap.has_action(action):
			var known: Array = InputMap.get_actions().filter(func(a: StringName) -> bool: return not String(a).begins_with("ui_"))
			return "unknown input action '%s' (project actions: %s)" % [action, ", ".join(known.map(func(a: StringName) -> String: return String(a)))]
		var ev := InputEventAction.new()
		ev.action = action
		ev.strength = float(spec.get("strength", 1.0))
		return ev
	if spec.has("key"):
		var code := OS.find_keycode_from_string(String(spec["key"]))
		if code == KEY_NONE:
			return "unknown key '%s'" % spec["key"]
		var k := InputEventKey.new()
		k.keycode = code
		k.physical_keycode = code
		for flag: String in ["ctrl", "shift", "alt", "meta"]:
			if spec.get(flag, false):
				k.set(flag + "_pressed", true)
		return k
	if spec.has("mouse_button"):
		var b := MouseButton.MOUSE_BUTTON_NONE
		var raw: Variant = spec["mouse_button"]
		b = Codec.MOUSE_BUTTONS.get(raw, MOUSE_BUTTON_NONE) if raw is String else int(raw)
		if b == MOUSE_BUTTON_NONE:
			return "unknown mouse button '%s'" % raw
		var mb := InputEventMouseButton.new()
		mb.button_index = b
		var pos: Variant = _vec(spec.get("position", [0, 0]))
		if pos == null:
			return "`position` must be [x, y]"
		mb.position = pos
		mb.global_position = pos
		return mb
	if spec.has("mouse_motion"):
		var to: Variant = _vec(spec["mouse_motion"])
		if to == null:
			return "`mouse_motion` must be [x, y]"
		var mm := InputEventMouseMotion.new()
		mm.position = to
		mm.global_position = to
		return mm
	return "an event needs one of: action, key, mouse_button, mouse_motion"


## [x, y] or "Vector2(x, y)" -> Vector2, or null.
static func _vec(v: Variant) -> Variant:
	var parsed := Codec.decode(v, TYPE_VECTOR2)
	return parsed[1] if parsed[0] else null


func _send(ev: InputEvent, pressed: bool) -> void:
	if ev is InputEventMouseMotion:
		if pressed:
			get_viewport().warp_mouse(ev.position)
			Input.parse_input_event(ev)
		return
	var copy: InputEvent = ev.duplicate()
	copy.set("pressed", pressed)
	Input.parse_input_event(copy)
	if ev is InputEventAction:
		# parse_input_event feeds _input handlers; action_press keeps the action held
		# for Input.is_action_pressed / get_axis between frames.
		if pressed:
			Input.action_press(ev.action, ev.strength)
		else:
			Input.action_release(ev.action)


# --- wait ----------------------------------------------------------------------------------


## Waits in the game until a condition holds (checked every physics frame) or timeout.
## p: frames | seconds | node_exists | node_gone | property {node, property, op, value}
## | signal {node, signal}; timeout (seconds, default 10).
func _wait(p: Dictionary) -> Variant:
	var timeout := float(p.get("timeout", 10.0))
	var start_ms := Time.get_ticks_msec()
	var start_frame := Engine.get_physics_frames()
	var check: Callable
	var describe := ""
	if p.has("frames"):
		var n := int(p["frames"])
		check = func() -> bool: return Engine.get_physics_frames() - start_frame >= n
		describe = "%d frames" % n
	elif p.has("seconds"):
		var s := float(p["seconds"])
		check = func() -> bool: return Time.get_ticks_msec() - start_ms >= s * 1000.0
		describe = "%s s" % s
		timeout = max(timeout, s + 1.0)
	elif p.has("node_exists"):
		var path := String(p["node_exists"])
		check = func() -> bool: return _find(path) != null
		describe = "node %s exists" % path
	elif p.has("node_gone"):
		var path := String(p["node_gone"])
		check = func() -> bool: return _find(path) == null
		describe = "node %s is gone" % path
	elif p.has("property"):
		var cond: Dictionary = p["property"]
		var made: Variant = _property_check(cond)
		if made is String:
			return _err(made)
		check = made
		describe = "%s.%s %s %s" % [cond.get("node", "."), cond.get("property", ""), cond.get("op", "=="), JSON.stringify(cond.get("value"))]
	elif p.has("signal"):
		var cond: Dictionary = p["signal"]
		var node := _find(String(cond.get("node", "")))
		if node == null:
			return _err("No node '%s' in the running game." % cond.get("node", ""))
		var sig := String(cond.get("signal", ""))
		if not node.has_signal(sig):
			return _err("%s has no signal '%s'." % [_path_of(node), sig])
		var fired := [false]
		var on_fire := func(_a: Variant = null, _b: Variant = null, _c: Variant = null, _d: Variant = null) -> void: fired[0] = true
		node.connect(sig, on_fire, CONNECT_ONE_SHOT)
		check = func() -> bool: return fired[0]
		describe = "%s emits %s" % [_path_of(node), sig]
	else:
		return _err("give one condition: frames, seconds, node_exists, node_gone, property or signal")
	var met := false
	while true:
		met = check.call()
		if met or Time.get_ticks_msec() - start_ms >= timeout * 1000.0:
			break
		await get_tree().physics_frame
	var out := {
		"met": met,
		"condition": describe,
		"waited_frames": Engine.get_physics_frames() - start_frame,
		"waited_seconds": snappedf((Time.get_ticks_msec() - start_ms) / 1000.0, 0.01),
	}
	if p.has("property"):
		var cond: Dictionary = p["property"]
		var node := _find(String(cond.get("node", "")))
		if node != null:
			out["value"] = Codec.encode(node.get_indexed(NodePath(String(cond.get("property", "")))), _scene_root())
	return out


const OPS := ["==", "!=", "<", "<=", ">", ">="]


func _property_check(cond: Dictionary) -> Variant:
	var path := String(cond.get("node", ""))
	var prop := String(cond.get("property", ""))
	var op := String(cond.get("op", "=="))
	if op not in OPS:
		return "`op` must be one of %s" % ", ".join(OPS)
	var node := _find(path)
	if node == null:
		return "No node '%s' in the running game." % path
	# property may be "position:x" (a component) like AnimationPlayer tracks.
	var parts := prop.split(":")
	var infos := Codec.property_infos(node)
	var base_value: Variant = node.get(parts[0])
	if base_value == null and not infos.has(parts[0]) and not (parts[0] in node):
		return Codec.unknown_property_message(node, parts[0], infos)
	var target_type := typeof(node.get_indexed(NodePath(prop)))
	var conv := Codec.decode(cond.get("value"), target_type if target_type != TYPE_NIL else TYPE_NIL)
	if not conv[0]:
		return "value: %s" % conv[1]
	var expected: Variant = conv[1]
	return func() -> bool:
		if not is_instance_valid(node):
			return false
		var v: Variant = node.get_indexed(NodePath(prop))
		if typeof(v) != typeof(expected) and not ((v is int or v is float) and (expected is int or expected is float)):
			return false
		match op:
			"==":
				return v == expected if not (v is float) else is_equal_approx(v, expected)
			"!=":
				return v != expected
			"<":
				return v < expected
			"<=":
				return v <= expected
			">":
				return v > expected
			">=":
				return v >= expected
		return false


# --- performance ---------------------------------------------------------------------------


func _performance(_p: Dictionary) -> Variant:
	return {
		"fps": Performance.get_monitor(Performance.TIME_FPS),
		"process_ms": snappedf(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, 0.01),
		"physics_ms": snappedf(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0, 0.01),
		"static_memory_mb": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, 0.1),
		"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
		"nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"orphan_nodes": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)),
		"resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
		"draw_calls": int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
		"objects_drawn": int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)),
		"physics_2d_active": int(Performance.get_monitor(Performance.PHYSICS_2D_ACTIVE_OBJECTS)),
		"physics_3d_active": int(Performance.get_monitor(Performance.PHYSICS_3D_ACTIVE_OBJECTS)),
		"frame": Engine.get_process_frames(),
	}
