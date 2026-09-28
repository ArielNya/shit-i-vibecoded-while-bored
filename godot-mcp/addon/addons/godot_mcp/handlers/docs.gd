@tool
extends "base.gd"
## API reference from the running engine (ClassDB) and the project's own classes, so the
## model works from Godot 4.7's real API instead of half-remembered Godot 3.


## Classes renamed or removed since Godot 3 that models still reach for.
const GODOT3_RENAMES := {
	"KinematicBody2D": "CharacterBody2D", "KinematicBody": "CharacterBody3D",
	"KinematicCollision": "KinematicCollision3D", "Spatial": "Node3D",
	"SpatialMaterial": "StandardMaterial3D", "Sprite": "Sprite2D",
	"AnimatedSprite": "AnimatedSprite2D", "Position2D": "Marker2D", "Position3D": "Marker3D",
	"MeshInstance": "MeshInstance3D", "Area": "Area3D", "RigidBody": "RigidBody3D",
	"StaticBody": "StaticBody3D", "CollisionShape": "CollisionShape3D",
	"CollisionPolygon": "CollisionPolygon3D", "RayCast": "RayCast3D", "Camera": "Camera3D",
	"Listener": "AudioListener3D", "Listener2D": "AudioListener2D",
	"Particles": "GPUParticles3D", "Particles2D": "GPUParticles2D", "CPUParticles": "CPUParticles3D",
	"Light2D": "PointLight2D", "DirectionalLight": "DirectionalLight3D", "OmniLight": "OmniLight3D",
	"SpotLight": "SpotLight3D", "GIProbe": "VoxelGI", "BakedLightmap": "LightmapGI",
	"VisibilityNotifier2D": "VisibleOnScreenNotifier2D", "VisibilityNotifier": "VisibleOnScreenNotifier3D",
	"VisibilityEnabler2D": "VisibleOnScreenEnabler2D", "YSort": "Node2D with y_sort_enabled = true",
	"ViewportContainer": "SubViewportContainer", "ToolButton": "Button with flat = true",
	"Navigation2D": "NavigationRegion2D / NavigationServer2D", "Navigation": "NavigationRegion3D / NavigationServer3D",
	"NavigationMeshInstance": "NavigationRegion3D", "Path": "Path3D", "PathFollow": "PathFollow3D",
	"Skeleton": "Skeleton3D", "BoneAttachment": "BoneAttachment3D", "Joint": "Joint3D",
	"VehicleBody": "VehicleBody3D", "VehicleWheel": "VehicleWheel3D", "SoftBody": "SoftBody3D",
	"ARVROrigin": "XROrigin3D", "ARVRCamera": "XRCamera3D", "ARVRController": "XRController3D",
	"VisualServer": "RenderingServer", "Physics2DServer": "PhysicsServer2D",
	"PhysicsServer": "PhysicsServer3D", "Physics2DDirectSpaceState": "PhysicsDirectSpaceState2D",
	"PhysicsDirectSpaceState": "PhysicsDirectSpaceState3D", "Quat": "Quaternion",
	"Transform": "Transform3D", "PoolStringArray": "PackedStringArray",
	"PoolIntArray": "PackedInt32Array / PackedInt64Array", "PoolRealArray": "PackedFloat32Array",
	"PoolVector2Array": "PackedVector2Array", "PoolVector3Array": "PackedVector3Array",
	"PoolColorArray": "PackedColorArray", "PoolByteArray": "PackedByteArray",
	"TileMap": "TileMapLayer (TileMap is deprecated)", "Reference": "RefCounted",
	"File": "FileAccess", "Directory": "DirAccess", "JSONParseResult": "JSON (instance .parse())",
	"Funcref": "Callable", "GDScriptFunctionState": "await", "EditorSpatialGizmo": "EditorNode3DGizmo",
	"ProximityGroup": "Area3D", "InterpolatedCamera": "Camera3D + interpolation in script",
	"ClippedCamera": "Camera3D + SpringArm3D", "Tabs": "TabBar", "LineShape2D": "WorldBoundaryShape2D",
	"PlaneShape": "WorldBoundaryShape3D", "RayShape": "SeparationRayShape3D",
	"RayShape2D": "SeparationRayShape2D", "CubeMesh": "BoxMesh",
}


func register(h: Dictionary) -> void:
	h["get_class_docs"] = get_class_docs
	h["search_docs"] = search_docs


func get_class_docs(p: Dictionary) -> Variant:
	var cls := String(p.get("class_name", "")).strip_edges()
	var inherited: bool = p.get("include_inherited", false)
	if cls == "":
		return invalid("`class_name` is required")
	if ClassDB.class_exists(cls):
		return _native_docs(cls, inherited)
	var script_path := _user_class_path(cls)
	if script_path == "" and GODOT3_RENAMES.has(cls):
		return fail("'%s' is Godot 3 API; in Godot 4 use %s." % [cls, GODOT3_RENAMES[cls]])
	if script_path == "":
		var similar := _similar_classes(cls)
		var hint := " Did you mean: %s?" % ", ".join(similar) if not similar.is_empty() else ""
		return fail("No class '%s' in Godot %s or this project.%s" % [cls, Engine.get_version_info()["string"], hint])
	return _script_docs(cls, script_path)


func _native_docs(cls: String, inherited: bool) -> Dictionary:
	var chain: Array[String] = []
	var parent := String(ClassDB.get_parent_class(cls))
	while parent != "":
		chain.append(parent)
		parent = String(ClassDB.get_parent_class(parent))
	var no_inh := not inherited

	var method_info := {}
	for m in ClassDB.class_get_method_list(cls, false):
		method_info[m["name"]] = m
	var accessors := {}
	var properties: Array[String] = []
	for prop in ClassDB.class_get_property_list(cls, no_inh):
		var usage: int = prop["usage"]
		if usage & (PROPERTY_USAGE_CATEGORY | PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
			continue
		var pname: String = prop["name"]
		var owner := cls
		if inherited:
			owner = _declaring_class(cls, pname)
		var setter := String(ClassDB.class_get_property_setter(owner, pname))
		var getter := String(ClassDB.class_get_property_getter(owner, pname))
		if setter != "":
			accessors[setter] = true
		if getter != "":
			accessors[getter] = true
		var type_info: Dictionary = prop
		if prop["type"] == TYPE_INT and method_info.has(getter):
			type_info = method_info[getter]["return"]  # carries the enum name, e.g. MotionMode
		var line := "%s: %s" % [pname, Codec.type_label(type_info)]
		var default: Variant = ClassDB.class_get_property_default_value(owner, pname)
		if default != null:
			line += " = " + _literal(default)
		properties.append(line)

	var methods: Array[String] = []
	var virtuals: Array[String] = []
	for m in ClassDB.class_get_method_list(cls, no_inh):
		var mname: String = m["name"]
		if accessors.has(mname):
			continue
		if int(m["flags"]) & METHOD_FLAG_VIRTUAL:
			virtuals.append(_signature(m))
		elif not mname.begins_with("_"):
			methods.append(_signature(m))

	var signals: Array[String] = []
	for s in ClassDB.class_get_signal_list(cls, no_inh):
		signals.append(_signature(s, false))

	var enums := {}
	var in_enum := {}
	for e in ClassDB.class_get_enum_list(cls, no_inh):
		var values: Array[String] = []
		for c in ClassDB.class_get_enum_constants(cls, e, no_inh):
			values.append("%s = %d" % [c, ClassDB.class_get_integer_constant(cls, c)])
			in_enum[c] = true
		enums[e] = values
	var constants: Array[String] = []
	for c in ClassDB.class_get_integer_constant_list(cls, no_inh):
		if not in_enum.has(c):
			constants.append("%s = %d" % [c, ClassDB.class_get_integer_constant(cls, c)])

	var out := {
		"class_name": cls,
		"kind": "native",
		"inherits": chain,
		"can_instantiate": ClassDB.can_instantiate(cls),
		"properties": properties,
		"methods": methods,
		"virtual_methods": virtuals,
		"signals": signals,
	}
	if not enums.is_empty():
		out["enums"] = enums
	if not constants.is_empty():
		out["constants"] = constants
	if ClassDB.class_get_api_type(cls) == ClassDB.API_EDITOR:
		out["editor_only"] = true
	if Engine.has_singleton(cls):
		out["singleton"] = true
	if not inherited:
		out["note"] = "Own members only; inherited ones are in the classes listed under `inherits` (or pass include_inherited)."
	return out


func _declaring_class(cls: String, pname: String) -> String:
	var c := cls
	while c != "":
		for prop in ClassDB.class_get_property_list(c, true):
			if prop["name"] == pname:
				return c
		c = String(ClassDB.get_parent_class(c))
	return cls


func _signature(m: Dictionary, with_return: bool = true) -> String:
	var args: PackedStringArray = []
	var arg_list: Array = m.get("args", [])
	var defaults: Array = m.get("default_args", [])
	var first_default := arg_list.size() - defaults.size()
	for i in arg_list.size():
		var a: Dictionary = arg_list[i]
		var s := "%s: %s" % [a["name"], Codec.type_label(a)]
		if i >= first_default:
			s += " = " + _literal(defaults[i - first_default])
		args.append(s)
	var flags := int(m.get("flags", 0))
	if flags & METHOD_FLAG_VARARG:
		args.append("...")
	var text := "%s(%s)" % [m["name"], ", ".join(args)]
	if with_return and m.has("return"):
		text += " -> " + Codec.type_label(m["return"])
	if flags & METHOD_FLAG_STATIC:
		text = "static " + text
	if flags & METHOD_FLAG_CONST:
		text += " const"
	return text


func _literal(v: Variant) -> String:
	if v == null:
		return "null"
	if v is String:
		return JSON.stringify(v)
	if v is StringName:
		return "&" + JSON.stringify(String(v))
	if v is Object:
		return "<%s>" % (v as Object).get_class()
	return var_to_str(v).replace("\n", " ")


func _user_class_path(cls: String) -> String:
	if cls.begins_with("res://") and FileAccess.file_exists(cls):
		return cls
	for entry in ProjectSettings.get_global_class_list():
		if String(entry["class"]) == cls:
			return String(entry["path"])
	return ""


func _script_docs(cls: String, path: String) -> Variant:
	var script := load(path) as Script
	if script == null:
		return fail("Could not load '%s' (it may have errors; try get_diagnostics)." % path)
	var chain: Array[String] = []
	var base := script.get_base_script()
	while base != null:
		var n := String(base.get_global_name())
		chain.append(n if n != "" else base.resource_path)
		base = base.get_base_script()
	var native := String(script.get_instance_base_type())
	while native != "":
		chain.append(native)
		native = String(ClassDB.get_parent_class(native))
	var properties: Array[String] = []
	for prop in script.get_script_property_list():
		if not (prop["usage"] & PROPERTY_USAGE_SCRIPT_VARIABLE):
			continue
		var line := "%s: %s" % [prop["name"], Codec.type_label(prop)]
		if prop["usage"] & PROPERTY_USAGE_EDITOR:
			line = "@export " + line
		var default: Variant = script.get_property_default_value(prop["name"])
		if default != null:
			line += " = " + _literal(default)
		properties.append(line)
	var methods: Array[String] = []
	for m in script.get_script_method_list():
		if not String(m["name"]).begins_with("@"):
			methods.append(_signature(m))
	var signals: Array[String] = []
	for s in script.get_script_signal_list():
		signals.append(_signature(s, false))
	var constants := {}
	var const_map := script.get_script_constant_map()
	for c: String in const_map:
		constants[c] = Codec.encode(const_map[c])
	return {
		"class_name": cls if not cls.begins_with("res://") else String(script.get_global_name()),
		"kind": "script",
		"path": path,
		"inherits": chain,
		"is_tool": script.is_tool(),
		"properties": properties,
		"methods": methods,
		"signals": signals,
		"constants": constants,
		"note": "Project class. Read the source with read_script for doc comments and details.",
	}


func _similar_classes(cls: String) -> Array[String]:
	var lower := cls.to_lower()
	var scored: Array = []
	for c in ClassDB.get_class_list():
		var sim := lower.similarity(String(c).to_lower())
		if sim > 0.5:
			scored.append([sim, String(c)])
	scored.sort_custom(func(a: Array, b: Array) -> bool: return a[0] > b[0])
	var out: Array[String] = []
	for s in scored.slice(0, 5):
		out.append(s[1])
	return out


func search_docs(p: Dictionary) -> Variant:
	var query := String(p.get("query", "")).strip_edges().to_lower()
	if query == "":
		return invalid("`query` must not be empty")
	var limit := int(p.get("limit", 30))
	var include_editor: bool = p.get("include_editor", false)
	var tokens := query.replace("_", " ").split(" ", false)
	var scored: Array = []  # [score, entry]
	var classes: Array[String] = []
	for c in ClassDB.get_class_list():
		if include_editor or ClassDB.class_get_api_type(c) != ClassDB.API_EDITOR:
			classes.append(String(c))
	for entry in ProjectSettings.get_global_class_list():
		classes.append(String(entry["class"]))
	for cls in classes:
		var s := _score(cls, query, tokens)
		if s > 0:
			scored.append([s + 1, {"kind": "class", "name": cls}])
		if not ClassDB.class_exists(cls):
			continue
		for m in ClassDB.class_get_method_list(cls, true):
			var ms := _score(String(m["name"]), query, tokens)
			if ms > 0:
				scored.append([ms, {"kind": "method", "class": cls, "name": m["name"], "signature": _signature(m)}])
		for prop in ClassDB.class_get_property_list(cls, true):
			if prop["usage"] & (PROPERTY_USAGE_CATEGORY | PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
				continue
			var ps := _score(String(prop["name"]), query, tokens)
			if ps > 0:
				scored.append([ps, {"kind": "property", "class": cls, "name": prop["name"], "type": Codec.type_label(prop)}])
		for sig in ClassDB.class_get_signal_list(cls, true):
			var ss := _score(String(sig["name"]), query, tokens)
			if ss > 0:
				scored.append([ss, {"kind": "signal", "class": cls, "name": sig["name"]}])
	scored.sort_custom(func(a: Array, b: Array) -> bool: return a[0] > b[0])
	var results: Array = []
	for s in scored.slice(0, limit):
		results.append(s[1])
	var out := {"query": query, "results": results, "total_matches": scored.size()}
	if scored.is_empty():
		out["hint"] = "Try fewer or different words, e.g. a node name ('RayCast2D') or a method fragment ('intersect')."
	return out


## 0 = no match; higher = better. Every query word must appear in the name.
static func _score(name: String, query: String, tokens: PackedStringArray) -> int:
	var lower := name.to_lower()
	var squashed := lower.replace("_", "")
	if lower == query or squashed == query.replace(" ", "").replace("_", ""):
		return 100
	for t in tokens:
		if not squashed.contains(t) and not lower.contains(t):
			return 0
	var score := 10
	if lower.begins_with(tokens[0]):
		score += 5
	return score + max(0, 5 - (lower.length() - query.length()) / 5)
