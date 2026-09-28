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
## Mouse button names used by the input-map tools and send_input.
const MOUSE_BUTTONS := {
	"left": MOUSE_BUTTON_LEFT, "right": MOUSE_BUTTON_RIGHT, "middle": MOUSE_BUTTON_MIDDLE,
	"wheel_up": MOUSE_BUTTON_WHEEL_UP, "wheel_down": MOUSE_BUTTON_WHEEL_DOWN,
	"wheel_left": MOUSE_BUTTON_WHEEL_LEFT, "wheel_right": MOUSE_BUTTON_WHEEL_RIGHT,
	"xbutton1": MOUSE_BUTTON_XBUTTON1, "xbutton2": MOUSE_BUTTON_XBUTTON2,
}
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


# --- property-aware decoding (set_node_properties, create_resource, ...) ------------------


## Like decode(), but uses the full property info from get_property_list():
## - enums accept option names ("Floating", "MOTION_MODE_FLOATING") as well as ints;
## - Object properties accept "res://..." paths, {"path": ...}, or a new embedded
##   resource {"_type": "Resource", "class": "RectangleShape2D", "properties": {...}},
##   and the result must match the property's class (e.g. Shape2D).
## Returns [ok: bool, value_or_message].
static func decode_property(value: Variant, info: Dictionary) -> Array:
	var t: int = info.get("type", TYPE_NIL)
	var hint: int = info.get("hint", PROPERTY_HINT_NONE)
	var hint_string := String(info.get("hint_string", ""))
	if t == TYPE_INT and hint == PROPERTY_HINT_ENUM and value is String:
		var n: Variant = _enum_value(value, hint_string)
		if n == null:
			return [false, "'%s' is not one of: %s" % [value, hint_string]]
		return [true, n]
	if t == TYPE_OBJECT:
		var result: Array
		if value is Dictionary and not value.has("path"):
			result = _new_resource(value)
		else:
			result = decode(value, TYPE_OBJECT)
		if not result[0] or result[1] == null:
			return result
		var allowed := String(info.get("class_name", ""))
		if allowed == "" and hint == PROPERTY_HINT_RESOURCE_TYPE:
			allowed = hint_string
		if allowed != "" and not _is_any_class(result[1], allowed.split(",")):
			return [false, "needs a %s, got a %s" % [allowed, class_label(result[1])]]
		return result
	return decode(value, t)


static func _enum_value(name: String, hint_string: String) -> Variant:
	var wanted := name.to_lower().replace("_", "").replace(" ", "")
	var next_value := 0
	for option in hint_string.split(","):
		var label := option
		var value := next_value
		if option.contains(":"):
			label = option.get_slice(":", 0)
			value = int(option.get_slice(":", 1))
		next_value = value + 1
		var norm := label.to_lower().replace("_", "").replace(" ", "")
		if norm != "" and (wanted == norm or wanted.ends_with(norm)):
			return value
	return null


static func _is_any_class(obj: Object, classes: PackedStringArray) -> bool:
	for c in classes:
		var cls := c.strip_edges()
		if cls == "" or obj.is_class(cls) or class_label(obj) == cls:
			return true
		var script: Script = obj.get_script()
		while script != null:
			if String(script.get_global_name()) == cls:
				return true
			script = script.get_base_script()
	return false


## {"class": "RectangleShape2D", "properties": {"size": "Vector2(32, 48)"}} -> new resource.
static func _new_resource(spec: Dictionary) -> Array:
	var cls := String(spec.get("class", ""))
	if cls == "":
		return [false, "a new resource needs a \"class\", e.g. {\"_type\": \"Resource\", \"class\": \"RectangleShape2D\", \"properties\": {...}}"]
	var res: Resource
	if ClassDB.class_exists(cls):
		if not ClassDB.is_parent_class(cls, "Resource") or not ClassDB.can_instantiate(cls):
			return [false, "'%s' is not a resource class that can be created" % cls]
		res = ClassDB.instantiate(cls)
	else:
		var script_path := preload("paths.gd").global_class_path(cls)
		if script_path == "":
			return [false, "unknown resource class '%s'" % cls]
		var obj: Variant = load(script_path).new()
		if not (obj is Resource):
			return [false, "'%s' is not a Resource" % cls]
		res = obj
	var props: Variant = spec.get("properties", {})
	if not (props is Dictionary):
		return [false, "\"properties\" must be an object"]
	var err := set_properties_on(res, props)
	if err != "":
		return [false, "%s: %s" % [cls, err]]
	return [true, res]


## Decodes and sets each property directly (no undo): for objects that aren't in a
## scene yet (new nodes, new resources). Returns "" or an error message.
static func set_properties_on(obj: Object, props: Dictionary) -> String:
	var infos := property_infos(obj)
	for key: Variant in props:
		var pname := String(key)
		if not infos.has(pname):
			return unknown_property_message(obj, pname, infos)
		var conv := decode_property(props[key], infos[pname])
		if not conv[0]:
			return "%s: %s" % [pname, conv[1]]
		obj.set(pname, conv[1])
	return ""


## name -> property info, for properties a user could set (editor-visible or script vars).
static func property_infos(obj: Object) -> Dictionary:
	var out := {}
	for prop in obj.get_property_list():
		var usage: int = prop["usage"]
		if usage & (PROPERTY_USAGE_CATEGORY | PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
			continue
		if usage & (PROPERTY_USAGE_EDITOR | PROPERTY_USAGE_SCRIPT_VARIABLE | PROPERTY_USAGE_STORAGE):
			out[prop["name"]] = prop
	return out


static func unknown_property_message(obj: Object, pname: String, infos: Dictionary) -> String:
	var close: Array[String] = []
	for k: String in infos:
		if k.similarity(pname) > 0.6 or k.ends_with("/" + pname):
			close.append(k)
	var hint := " Did you mean: %s?" % ", ".join(close.slice(0, 5)) if not close.is_empty() else ""
	return "%s has no property '%s'.%s" % [class_label(obj), pname, hint]


# --- property listings (editor and running game) ------------------------------------------


## Editor-visible properties of `obj`. By default only values that differ from the class /
## script default, which is what the Inspector would show in bold.
static func describe_properties(obj: Object, scene_root: Node, filter: String, include_defaults: bool) -> Dictionary:
	var props: Array[Dictionary] = []
	var section := ""
	var skipped_defaults := 0
	var filter_lower := filter.to_lower()
	var script: Script = obj.get_script()
	var native_props := {}
	for prop in ClassDB.class_get_property_list(obj.get_class()):
		native_props[prop["name"]] = true
	for prop in obj.get_property_list():
		var usage: int = prop["usage"]
		var pname: String = prop["name"]
		if usage & PROPERTY_USAGE_CATEGORY:
			section = pname
			continue
		if usage & (PROPERTY_USAGE_GROUP | PROPERTY_USAGE_SUBGROUP):
			continue
		if not (usage & PROPERTY_USAGE_EDITOR) or pname.begins_with("metadata/_"):
			continue
		if filter_lower != "" and not pname.to_lower().contains(filter_lower):
			continue
		var value: Variant = obj.get(pname)
		if not include_defaults and _is_default(obj, script, native_props, pname, value):
			skipped_defaults += 1
			continue
		var entry := {"name": pname, "type": type_label(prop), "value": encode(value, scene_root)}
		if prop.get("hint", 0) in [PROPERTY_HINT_ENUM, PROPERTY_HINT_FLAGS]:
			entry["options"] = prop.get("hint_string", "")
		if section != "" and section != obj.get_class():
			entry["section"] = section
		props.append(entry)
	var out := {"properties": props}
	if skipped_defaults > 0:
		out["default_values_hidden"] = skipped_defaults
	return out


static func _is_default(obj: Object, script: Script, native_props: Dictionary, pname: String, value: Variant) -> bool:
	var default: Variant = null
	var known := false
	if script != null:
		var script_default: Variant = script.get_property_default_value(pname)
		if script_default != null or _script_has_property(script, pname):
			default = script_default
			known = true
	if not known and native_props.has(pname):
		default = ClassDB.class_get_property_default_value(obj.get_class(), pname)
		known = true
	if not known and obj.property_can_revert(pname):
		default = obj.property_get_revert(pname)
		known = true
	if not known:
		return false
	if typeof(default) != typeof(value):
		return false
	if value is float:
		return is_equal_approx(value, default)
	return value == default


static func _script_has_property(script: Script, pname: String) -> bool:
	for prop in script.get_script_property_list():
		if prop["name"] == pname:
			return true
	return false
