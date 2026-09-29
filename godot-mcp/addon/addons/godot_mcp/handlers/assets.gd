@tool
extends "base.gd"
## Resources (.tres), imported assets, TileSets from sprite sheets, and TileMapLayer cells.

## File types import_asset may write into the project.
const ASSET_EXTENSIONS := [
	"png", "jpg", "jpeg", "webp", "svg", "bmp", "tga",
	"wav", "ogg", "mp3",
	"ttf", "otf", "woff", "woff2",
	"glb", "gltf", "obj",
]
const MAX_GRID := 256  # get_tiles grid side limit


func register(h: Dictionary) -> void:
	h["create_resource"] = create_resource
	h["get_resource"] = get_resource
	h["set_resource_properties"] = set_resource_properties
	h["import_asset"] = import_asset
	h["reimport"] = reimport
	h["create_tileset"] = create_tileset
	h["get_tiles"] = get_tiles
	h["set_tiles"] = set_tiles


# --- resources -----------------------------------------------------------------------------


func _res_path(raw: String, must_exist: bool) -> Variant:
	var path := Paths.normalize(raw)
	if path == "":
		return invalid(Paths.describe_bad(raw))
	if path.begins_with("res://addons/godot_mcp/"):
		return invalid("The godot_mcp plugin's own files can't be changed through MCP.")
	if must_exist and not ResourceLoader.exists(path):
		return fail("No resource at '%s'." % path)
	return path


func _save(res: Resource, path: String) -> Variant:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var err := ResourceSaver.save(res, path)
	if err != OK:
		return fail("Could not save '%s' (%s)." % [path, error_string(err)])
	EditorInterface.get_resource_filesystem().update_file(path)
	await wait_for_filesystem()
	return null


func create_resource(p: Dictionary) -> Variant:
	var path: Variant = _res_path(String(p.get("path", "")), false)
	if path is McpError:
		return path
	if String(path).get_extension() not in ["tres", "res"]:
		return invalid("Resources are saved as .tres (or .res), e.g. res://data/enemy_stats.tres")
	if FileAccess.file_exists(path) and not p.get("overwrite", false):
		return fail("'%s' already exists. Pass overwrite=true to replace it, or set_resource_properties to edit it." % path)
	var made := Codec.decode_property({"_type": "Resource", "class": String(p.get("type", "")), "properties": p.get("properties", {})}, {"type": TYPE_OBJECT})
	if not made[0]:
		return invalid(made[1])
	var saved: Variant = await _save(made[1], path)
	if saved is McpError:
		return saved
	return _describe(load(path), path)


func _describe(res: Resource, path: String) -> Dictionary:
	var out := Codec.describe_properties(res, null, "", false)
	out["path"] = path
	out["type"] = Codec.class_label(res)
	return out


func get_resource(p: Dictionary) -> Variant:
	var path: Variant = _res_path(String(p.get("path", "")), true)
	if path is McpError:
		return path
	var res := load(path)
	if res == null:
		return fail("Could not load '%s'." % path)
	var out := Codec.describe_properties(res, null, String(p.get("filter", "")), p.get("include_defaults", false))
	out["path"] = path
	out["type"] = Codec.class_label(res)
	return out


func set_resource_properties(p: Dictionary) -> Variant:
	var path: Variant = _res_path(String(p.get("path", "")), true)
	if path is McpError:
		return path
	if String(path).get_extension() not in ["tres", "res"]:
		return invalid("'%s' is an imported asset; change how it's imported with reimport (import options) instead." % path)
	var res := load(path)
	var props: Variant = p.get("properties", {})
	if not (props is Dictionary) or props.is_empty():
		return invalid("`properties` must be an object like {\"max_health\": 10}")
	var infos := Codec.property_infos(res)
	var decoded := {}
	for key: Variant in props:
		var pname := String(key)
		if not infos.has(pname):
			return invalid("Nothing was changed. " + Codec.unknown_property_message(res, pname, infos))
		var conv := Codec.decode_property(props[key], infos[pname])
		if not conv[0]:
			return invalid("Nothing was changed. %s: %s" % [pname, conv[1]])
		decoded[pname] = conv[1]
	var ur := begin_action("set_resource_properties", res)
	for pname: String in decoded:
		ur.add_do_property(res, pname, decoded[pname])
		ur.add_undo_property(res, pname, res.get(pname))
	ur.add_do_method(ResourceSaver, "save", res, path)
	ur.add_undo_method(ResourceSaver, "save", res, path)
	commit_action(ur, "set_resource_properties", res)
	var values := {}
	for pname: String in decoded:
		values[pname] = Codec.encode(res.get(pname))
	return {"path": path, "values": values}


# --- imported assets -------------------------------------------------------------------------


## The MCP server reads the file (from a folder the user allowed) and sends its bytes.
func import_asset(p: Dictionary) -> Variant:
	var path: Variant = _res_path(String(p.get("path", "")), false)
	if path is McpError:
		return path
	if String(path).get_extension().to_lower() not in ASSET_EXTENSIONS:
		return invalid("import_asset takes %s files." % ", ".join(ASSET_EXTENSIONS))
	if FileAccess.file_exists(path) and not p.get("overwrite", false):
		return fail("'%s' already exists. Pass overwrite=true to replace it." % path)
	var data := Marshalls.base64_to_raw(String(p.get("data_base64", "")))
	if data.is_empty():
		return invalid("no file data received")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(String(path).get_base_dir()))
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return fail("Could not write '%s' (%s)." % [path, error_string(FileAccess.get_open_error())])
	f.store_buffer(data)
	f.close()
	var efs := EditorInterface.get_resource_filesystem()
	efs.update_file(path)
	efs.scan()
	# The import runs a few frames later; wait until it has produced the .import file.
	for i in 1200:
		await plugin.get_tree().process_frame
		if FileAccess.file_exists(String(path) + ".import") and not efs.is_scanning() and not efs.is_importing():
			break
	if not FileAccess.file_exists(String(path) + ".import"):
		return fail("Godot didn't import '%s' (unsupported or corrupt file? see the Output panel)." % path)
	var options: Variant = p.get("import_options", {})
	if options is Dictionary and not options.is_empty():
		var result: Variant = await _reimport([path], options)
		if result is McpError:
			return result
	return _asset_info(path)


func _asset_info(path: String) -> Dictionary:
	var res := load(path)
	# (the filesystem cache may not know the type yet right after an import)
	var out := {"path": path, "type": res.get_class() if res != null else "", "bytes": FileAccess.get_file_as_bytes(path).size()}
	if res is Texture2D:
		out["size"] = "%dx%d" % [(res as Texture2D).get_width(), (res as Texture2D).get_height()]
	elif res is AudioStream:
		out["seconds"] = snappedf((res as AudioStream).get_length(), 0.01)
	var cfg := ConfigFile.new()
	if cfg.load(path + ".import") == OK:
		out["importer"] = cfg.get_value("remap", "importer", "")
		var params := {}
		for key in cfg.get_section_keys("params") if cfg.has_section("params") else PackedStringArray():
			params[key] = Codec.encode(cfg.get_value("params", key))
		out["import_options"] = params
	return out


func reimport(p: Dictionary) -> Variant:
	var paths: Array = []
	for raw: Variant in p.get("paths", []):
		var path: Variant = _res_path(String(raw), true)
		if path is McpError:
			return path
		if not FileAccess.file_exists(String(path) + ".import"):
			return fail("'%s' is not an imported asset (no .import file)." % path)
		paths.append(path)
	if paths.is_empty():
		return invalid("`paths` must list at least one imported file")
	var result: Variant = await _reimport(paths, p.get("import_options", {}))
	if result is McpError:
		return result
	return {"assets": paths.map(_asset_info)}


## Writes import options into each .import file (keys as shown by import_asset, e.g.
## "compress/mode", "mipmaps/generate") and reimports.
func _reimport(paths: Array, options: Variant) -> Variant:
	if not (options is Dictionary):
		return invalid("`import_options` must be an object")
	for path: String in paths:
		var cfg := ConfigFile.new()
		if cfg.load(path + ".import") != OK:
			return fail("Could not read '%s.import'." % path)
		for key: Variant in options:
			var k := String(key)
			if not cfg.has_section_key("params", k):
				var known := Array(cfg.get_section_keys("params")) if cfg.has_section("params") else []
				return invalid("'%s' is not an import option of %s. Options: %s" % [k, path, ", ".join(known)])
			var target := typeof(cfg.get_value("params", k))
			var conv := Codec.decode(options[key], target)
			if not conv[0]:
				return invalid("%s: %s" % [k, conv[1]])
			cfg.set_value("params", k, conv[1])
		cfg.save(path + ".import")
	EditorInterface.get_resource_filesystem().reimport_files(PackedStringArray(paths))
	await wait_for_filesystem()
	return null


# --- tilesets --------------------------------------------------------------------------------


func create_tileset(p: Dictionary) -> Variant:
	var path: Variant = _res_path(String(p.get("path", "")), false)
	if path is McpError:
		return path
	if String(path).get_extension() != "tres":
		return invalid("Save the TileSet as .tres, e.g. res://tiles/world.tres")
	if FileAccess.file_exists(path) and not p.get("overwrite", false):
		return fail("'%s' already exists. Pass overwrite=true to replace it." % path)
	var tex_path: Variant = _res_path(String(p.get("texture", "")), true)
	if tex_path is McpError:
		return tex_path
	var texture := load(tex_path) as Texture2D
	if texture == null:
		return fail("'%s' is not a texture." % tex_path)
	var size_arg: Variant = p.get("tile_size", [16, 16])
	var conv := Codec.decode(size_arg, TYPE_VECTOR2I)
	if not conv[0] or conv[1].x <= 0 or conv[1].y <= 0:
		return invalid("`tile_size` must be [width, height] in pixels, e.g. [16, 16]")
	var tile_size: Vector2i = conv[1]
	var cols := texture.get_width() / tile_size.x
	var rows := texture.get_height() / tile_size.y
	if cols == 0 or rows == 0:
		return invalid("The texture (%dx%d) is smaller than one tile." % [texture.get_width(), texture.get_height()])

	var tileset := TileSet.new()
	tileset.tile_size = tile_size
	var source := TileSetAtlasSource.new()
	source.texture = texture
	source.texture_region_size = tile_size
	var image := texture.get_image()
	if image != null and image.is_compressed():
		image.decompress()
	var created: Array = []
	for y in rows:
		for x in cols:
			if image != null and _is_blank(image, Rect2i(Vector2i(x, y) * tile_size, tile_size)):
				continue  # empty cell in the sheet
			source.create_tile(Vector2i(x, y))
			created.append(Vector2i(x, y))
	var source_id := tileset.add_source(source)

	var solid: Variant = p.get("collision", "none")
	var solid_tiles: Array = []
	if solid is String and solid == "all":
		solid_tiles = created
	elif solid is Array:
		for c: Variant in solid:
			var v := Codec.decode(c, TYPE_VECTOR2I)
			if not v[0] or not (v[1] in created):
				return invalid("collision tile %s is not a tile of the sheet (tiles are [column, row], from [0, 0] to [%d, %d])" % [JSON.stringify(c), cols - 1, rows - 1])
			solid_tiles.append(v[1])
	elif not (solid is String and solid == "none"):
		return invalid("`collision` must be \"none\", \"all\" or a list of [column, row]")
	if not solid_tiles.is_empty():
		tileset.add_physics_layer()
		var h := Vector2(tile_size) / 2.0
		var square := PackedVector2Array([Vector2(-h.x, -h.y), Vector2(h.x, -h.y), Vector2(h.x, h.y), Vector2(-h.x, h.y)])
		for coords: Vector2i in solid_tiles:
			var data := source.get_tile_data(coords, 0)
			data.add_collision_polygon(0)
			data.set_collision_polygon_points(0, 0, square)

	var saved: Variant = await _save(tileset, path)
	if saved is McpError:
		return saved
	return {
		"path": path,
		"source_id": source_id,
		"tile_size": [tile_size.x, tile_size.y],
		"atlas_grid": [cols, rows],
		"tiles": created.map(func(c: Vector2i) -> Array: return [c.x, c.y]),
		"solid_tiles": solid_tiles.size(),
	}


static func _is_blank(image: Image, rect: Rect2i) -> bool:
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			if image.get_pixel(x, y).a > 0.01:
				return false
	return true


# --- tile maps ------------------------------------------------------------------------------


func _layer(p: Dictionary) -> Variant:
	var target: Variant = await target_node(p)
	if target is McpError:
		return target
	if not (target[1] is TileMapLayer):
		return fail("%s is a %s, not a TileMapLayer." % [node_path(target[0], target[1]), target[1].get_class()])
	return target


## Tiles as an ASCII grid (one char per distinct tile, legend included) or a cell list.
func get_tiles(p: Dictionary) -> Variant:
	var target: Variant = await _layer(p)
	if target is McpError:
		return target
	var layer: TileMapLayer = target[1]
	var used := layer.get_used_rect()
	var out := {"node": node_path(target[0], layer), "cells": layer.get_used_cells().size()}
	if layer.tile_set != null:
		out["tile_set"] = layer.tile_set.resource_path if layer.tile_set.resource_path != "" else "(embedded)"
		out["tile_size"] = [layer.tile_set.tile_size.x, layer.tile_set.tile_size.y]
	if used.size == Vector2i.ZERO:
		out["grid"] = []
		return out
	if String(p.get("format", "grid")) == "cells" or used.size.x > MAX_GRID or used.size.y > MAX_GRID:
		var cells: Array = []
		for c in layer.get_used_cells():
			var a := layer.get_cell_atlas_coords(c)
			cells.append([c.x, c.y, layer.get_cell_source_id(c), a.x, a.y, layer.get_cell_alternative_tile(c)])
		out["cell_format"] = "[x, y, source, atlas_x, atlas_y, alternative]"
		out["cell_list"] = cells
		return out
	const CHARS := "#=@%&*+ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
	var legend := {}
	var keys := {}
	var rows: Array[String] = []
	for y in range(used.position.y, used.end.y):
		var row := ""
		for x in range(used.position.x, used.end.x):
			var c := Vector2i(x, y)
			var src := layer.get_cell_source_id(c)
			if src == -1:
				row += "."
				continue
			var a := layer.get_cell_atlas_coords(c)
			var key := "%d:%d:%d:%d" % [src, a.x, a.y, layer.get_cell_alternative_tile(c)]
			if not keys.has(key):
				var ch := CHARS[keys.size()] if keys.size() < CHARS.length() else "?"
				keys[key] = ch
				legend[ch] = {"source": src, "atlas": [a.x, a.y], "alternative": layer.get_cell_alternative_tile(c)}
			row += keys[key]
		rows.append(row)
	out["origin"] = [used.position.x, used.position.y]
	out["grid"] = rows
	out["legend"] = legend
	out["note"] = "'.' = empty. Row 0 is y=%d, column 0 is x=%d." % [used.position.y, used.position.x]
	return out


func _tile(spec: Variant, default_source: int) -> Variant:
	## [ax, ay] / {"atlas": [ax, ay], "source": s, "alternative": a} -> [source, Vector2i, alt]
	if spec == null:
		return [-1, Vector2i(-1, -1), -1]  # erase
	var d: Dictionary = spec if spec is Dictionary else {"atlas": spec}
	var a := Codec.decode(d.get("atlas"), TYPE_VECTOR2I)
	if not a[0]:
		return "a tile is [atlas_column, atlas_row] or {\"atlas\": [c, r], \"source\": id}, got %s" % JSON.stringify(spec)
	return [int(d.get("source", default_source)), a[1], int(d.get("alternative", 0))]


func set_tiles(p: Dictionary) -> Variant:
	var target: Variant = await _layer(p)
	if target is McpError:
		return target
	var root: Node = target[0]
	var layer: TileMapLayer = target[1]
	if layer.tile_set == null:
		return fail("%s has no tile_set. Set one first: set_node_properties tile_set=\"res://....tres\" (create_tileset makes one from a sprite sheet)." % node_path(root, layer))
	var default_source := int(p.get("source", layer.tile_set.get_source_id(0) if layer.tile_set.get_source_count() > 0 else 0))
	var writes: Array = []  # [coords, source, atlas, alt]

	var rows: Array = p.get("grid", [])
	if not rows.is_empty():
		var legend: Dictionary = p.get("legend", {})
		var parsed := {}
		for ch: Variant in legend:
			var t: Variant = _tile(legend[ch], default_source)
			if t is String:
				return invalid("legend '%s': %s" % [ch, t])
			parsed[String(ch)] = t
		var origin := Codec.decode(p.get("origin", [0, 0]), TYPE_VECTOR2I)
		if not origin[0]:
			return invalid("`origin` must be [x, y]")
		for y in rows.size():
			var row := String(rows[y])
			for x in row.length():
				var ch := row[x]
				if parsed.has(ch):
					var t: Array = parsed[ch]
					writes.append([origin[1] + Vector2i(x, y)] + t)
				elif ch != " ":
					return invalid("'%s' (row %d) is not in the legend; use ' ' for cells to leave alone, or map it to null to erase." % [ch, y])

	for cell: Variant in p.get("cells", []):
		if not (cell is Array) or cell.size() < 4:
			return invalid("each cell is [x, y, atlas_column, atlas_row] (optionally + source, alternative)")
		writes.append([Vector2i(int(cell[0]), int(cell[1])), int(cell[4]) if cell.size() > 4 else default_source, Vector2i(int(cell[2]), int(cell[3])), int(cell[5]) if cell.size() > 5 else 0])

	for rect: Variant in p.get("fill_rects", []):
		if not (rect is Array) or rect.size() < 6:
			return invalid("each fill rect is [x, y, width, height, atlas_column, atlas_row]")
		for y in int(rect[3]):
			for x in int(rect[2]):
				writes.append([Vector2i(int(rect[0]) + x, int(rect[1]) + y), default_source, Vector2i(int(rect[4]), int(rect[5])), 0])

	for cell: Variant in p.get("erase", []):
		var c := Codec.decode(cell, TYPE_VECTOR2I)
		if not c[0]:
			return invalid("erase takes [x, y] cells")
		writes.append([c[1], -1, Vector2i(-1, -1), -1])

	if writes.is_empty():
		return invalid("Nothing to do: give `grid` + `legend`, `cells`, `fill_rects` or `erase`.")
	for w: Array in writes:
		if w[1] != -1:
			var src := layer.tile_set.get_source(w[1]) if layer.tile_set.has_source(w[1]) else null
			if src == null:
				return invalid("The tile set has no source %d." % w[1])
			if src is TileSetAtlasSource and not (src as TileSetAtlasSource).has_tile(w[2]):
				return invalid("Source %d has no tile at atlas %s (see create_tileset's `tiles`)." % [w[1], w[2]])

	var before: PackedByteArray = layer.tile_map_data
	for w: Array in writes:
		if w[1] == -1:
			layer.erase_cell(w[0])
		else:
			layer.set_cell(w[0], w[1], w[2], w[3])
	var after: PackedByteArray = layer.tile_map_data
	layer.tile_map_data = before
	var ur := begin_action("set_tiles", root)
	ur.add_do_property(layer, "tile_map_data", after)
	ur.add_undo_property(layer, "tile_map_data", before)
	commit_action(ur, "set_tiles", root)
	return {"node": node_path(root, layer), "changed": writes.size(), "cells": layer.get_used_cells().size()}
