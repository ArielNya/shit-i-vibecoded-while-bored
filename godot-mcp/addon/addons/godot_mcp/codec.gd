@tool
extends RefCounted
## Variant <-> JSON conversion used by every handler.
##
## Encoding rules (documented for the model in the server instructions):
## - null, bools, ints, finite floats, strings: plain JSON.
## - Other built-in values (Vector2, Color, Transform3D, NodePath, Rect2, ...): the GDScript
##   literal as a string, exactly what `var_to_str` prints, e.g. "Vector2(1, 2)".
## - Resources: {"_type": "Resource", "class": ..., "path": "res://..."}; embedded
##   (sub-)resources have "embedded": true instead of a path.
## - Nodes: {"_type": "Node", "class": ..., "path": <NodePath from the scene root>}.
## - Large arrays are cut to their first items with a {"_truncated": total} marker.

const MAX_DEPTH := 6
const MAX_ITEMS := 64
const PACKED_TYPES := [
	TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY,
	TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY,
	TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, TYPE_PACKED_COLOR_ARRAY,
	TYPE_PACKED_VECTOR4_ARRAY,
]


## `scene_root` (optional) makes Node paths relative to the edited scene.
static func encode(value: Variant, scene_root: Node = null, depth: int = 0) -> Variant:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return value
		TYPE_FLOAT:
			return value if is_finite(value) else var_to_str(value)
		TYPE_STRING_NAME:
			return String(value)
		TYPE_OBJECT:
			return encode_object(value, scene_root)
		TYPE_ARRAY:
			return _encode_list(value, scene_root, depth)
		TYPE_DICTIONARY:
			if depth >= MAX_DEPTH:
				return {"_truncated": value.size()}
			var out := {}
			var n := 0
			for key: Variant in value:
				if n >= MAX_ITEMS:
					out["_truncated"] = value.size()
					break
				var k: String = key if key is String else (String(key) if key is StringName else var_to_str(key))
				out[k] = encode(value[key], scene_root, depth + 1)
				n += 1
			return out
		TYPE_CALLABLE, TYPE_SIGNAL, TYPE_RID:
			return {"_type": type_string(typeof(value)), "text": str(value)}
	if typeof(value) in PACKED_TYPES:
		return _encode_list(value, scene_root, depth)
	return var_to_str(value)


static func _encode_list(value: Variant, scene_root: Node, depth: int) -> Variant:
	if depth >= MAX_DEPTH:
		return [{"_truncated": value.size()}]
	var out := []
	var n: int = min(value.size(), MAX_ITEMS)
	for i in n:
		out.append(encode(value[i], scene_root, depth + 1))
	if value.size() > n:
		out.append({"_truncated": value.size()})
	return out


static func encode_object(obj: Object, scene_root: Node = null) -> Variant:
	if obj == null or not is_instance_valid(obj):
		return null
	var cls := class_label(obj)
	if obj is InputEvent:
		return {"_type": "InputEvent", "class": cls, "text": (obj as InputEvent).as_text()}
	if obj is Resource:
		var res := obj as Resource
		if res.resource_path != "" and not res.resource_path.contains("::"):
			return {"_type": "Resource", "class": cls, "path": res.resource_path}
		var out := {"_type": "Resource", "class": cls, "embedded": true}
		if res.resource_name != "":
			out["name"] = res.resource_name
		return out
	if obj is Node:
		var node := obj as Node
		var path := String(node.get_path())
		if scene_root != null and (node == scene_root or scene_root.is_ancestor_of(node)):
			path = String(scene_root.get_path_to(node))
		return {"_type": "Node", "class": cls, "path": path}
	return {"_type": "Object", "class": cls}


## The script's class_name if it has one, else the native class.
static func class_label(obj: Object) -> String:
	var script: Script = obj.get_script()
	if script != null:
		var global_name := String(script.get_global_name())
		if global_name != "":
			return global_name
	return obj.get_class()


## A readable type name for a property/argument dictionary from get_property_list().
static func type_label(info: Dictionary) -> String:
	var t: int = info.get("type", TYPE_NIL)
	var cls := String(info.get("class_name", ""))
	var usage: int = info.get("usage", 0)
	if t == TYPE_NIL:
		return "Variant" if usage & PROPERTY_USAGE_NIL_IS_VARIANT else "void"
	if t == TYPE_OBJECT:
		if cls != "":
			return cls
		var hint_string := String(info.get("hint_string", ""))
		if info.get("hint", 0) == PROPERTY_HINT_RESOURCE_TYPE and hint_string != "":
			return hint_string
		return "Object"
	if t == TYPE_INT and cls != "" and usage & (PROPERTY_USAGE_CLASS_IS_ENUM | PROPERTY_USAGE_CLASS_IS_BITFIELD):
		return cls
	if t == TYPE_ARRAY and info.get("hint", 0) == PROPERTY_HINT_ARRAY_TYPE:
		return "Array[%s]" % info.get("hint_string", "")
	if t == TYPE_DICTIONARY and info.get("hint", 0) == PROPERTY_HINT_DICTIONARY_TYPE:
		return "Dictionary[%s]" % String(info.get("hint_string", "")).replace(";", ", ")
	return type_string(t)


# --- decoding (JSON from the model -> Variant of a known target type) ---------------------

const _CONSTRUCTOR_TYPES := {
	TYPE_VECTOR2: "Vector2", TYPE_VECTOR2I: "Vector2i", TYPE_RECT2: "Rect2",
	TYPE_RECT2I: "Rect2i", TYPE_VECTOR3: "Vector3", TYPE_VECTOR3I: "Vector3i",
	TYPE_TRANSFORM2D: "Transform2D", TYPE_VECTOR4: "Vector4", TYPE_VECTOR4I: "Vector4i",
	TYPE_PLANE: "Plane", TYPE_QUATERNION: "Quaternion", TYPE_AABB: "AABB", TYPE_BASIS: "Basis",
	TYPE_TRANSFORM3D: "Transform3D", TYPE_PROJECTION: "Projection", TYPE_COLOR: "Color",
	TYPE_NODE_PATH: "NodePath",
}


## Converts `value` (parsed JSON) to `target_type`. Returns [ok: bool, value_or_message].
## TYPE_NIL means "no known type": JSON values are kept as they are.
static func decode(value: Variant, target_type: int) -> Array:
	if target_type == TYPE_NIL:
		return [true, _decode_untyped(value)]
	if value == null:
		if target_type == TYPE_OBJECT:
			return [true, null]
		return [false, "null is not a valid %s" % type_string(target_type)]
	match target_type:
		TYPE_BOOL:
			if value is bool:
				return [true, value]
		TYPE_INT:
			if value is float and value == floorf(value):
				return [true, int(value)]
			if value is int:
				return [true, value]
		TYPE_FLOAT:
			if value is float or value is int:
				return [true, float(value)]
		TYPE_STRING:
			if value is String:
				return [true, value]
		TYPE_STRING_NAME:
			if value is String:
				return [true, StringName(value)]
		TYPE_COLOR:
			if value is String and not value.begins_with("Color("):
				var c := Color.from_string(value, Color(0, 0, 0, -1))
				if c.a >= 0:
					return [true, c]
			if value is Array and value.size() in [3, 4]:
				return [true, Color(value[0], value[1], value[2], value[3] if value.size() == 4 else 1.0)]
		TYPE_NODE_PATH:
			if value is String and not value.begins_with("NodePath("):
				return [true, NodePath(value)]
		TYPE_OBJECT:
			if value is String:
				return _load_resource(value)
			if value is Dictionary and value.has("path"):
				return _load_resource(String(value["path"]))
		TYPE_ARRAY:
			if value is Array:
				return [true, value.map(_decode_untyped)]
		TYPE_DICTIONARY:
			if value is Dictionary:
				return [true, _decode_untyped(value)]
	if value is Array and target_type in [TYPE_VECTOR2, TYPE_VECTOR2I, TYPE_VECTOR3, TYPE_VECTOR3I, TYPE_VECTOR4, TYPE_VECTOR4I]:
		var parsed: Variant = _parse_literal("%s(%s)" % [_CONSTRUCTOR_TYPES[target_type], ", ".join(value.map(func(x: Variant) -> String: return str(x)))], target_type)
		if parsed != null:
			return [true, parsed]
	if value is String and _CONSTRUCTOR_TYPES.has(target_type):
		var parsed: Variant = _parse_literal(value, target_type)
		if parsed != null:
			return [true, parsed]
		return [false, "expected a %s literal like %s" % [type_string(target_type), _example(target_type)]]
	if typeof(value) in PACKED_TYPES or target_type in PACKED_TYPES:
		if value is Array:
			var converted: Variant = type_convert(value, target_type)
			return [true, converted]
	return [false, "can't convert %s to %s" % [JSON.stringify(value), type_string(target_type)]]


static func _decode_untyped(value: Variant) -> Variant:
	if value is float and value == floorf(value) and absf(value) < 9.0e15:
		return int(value)
	if value is Array:
		return value.map(_decode_untyped)
	if value is Dictionary:
		var out := {}
		for k: Variant in value:
			out[k] = _decode_untyped(value[k])
		return out
	return value


## Parses a GDScript literal, but only for the expected built-in type: str_to_var() can
## also build Objects, which we never want from model input.
static func _parse_literal(text: String, target_type: int) -> Variant:
	var t := text.strip_edges()
	var type_name: String = _CONSTRUCTOR_TYPES.get(target_type, "")
	if type_name == "" or not t.begins_with(type_name + "(") or not t.ends_with(")"):
		return null
	var inner := t.substr(type_name.length() + 1, t.length() - type_name.length() - 2)
	if inner.contains("(") or inner.contains(")"):
		return null  # no nested constructors, so no Object(...) or Resource(...)
	var parsed: Variant = str_to_var(t)
	if typeof(parsed) != target_type:
		return null
	return parsed


static func _load_resource(path: String) -> Array:
	if path == "":
		return [true, null]
	var norm := preload("paths.gd").normalize(path) if not path.begins_with("uid://") else path
	if norm == "" or not ResourceLoader.exists(norm):
		return [false, "no resource at '%s'" % path]
	return [true, load(norm)]


static func _example(target_type: int) -> String:
	match target_type:
		TYPE_VECTOR2:
			return "\"Vector2(1, 2)\" or [1, 2]"
		TYPE_VECTOR3:
			return "\"Vector3(1, 2, 3)\" or [1, 2, 3]"
		TYPE_COLOR:
			return "\"Color(1, 0, 0, 1)\", \"#ff0000\" or \"red\""
	return "\"%s(...)\"" % _CONSTRUCTOR_TYPES.get(target_type, type_string(target_type))
