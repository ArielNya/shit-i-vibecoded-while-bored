@tool
extends "base.gd"
## Screenshots of the editor so the model can see the scene.


func register(h: Dictionary) -> void:
	h["get_editor_screenshot"] = get_editor_screenshot


func get_editor_screenshot(p: Dictionary) -> Variant:
	if DisplayServer.get_name() == "headless":
		return fail("The editor is running headless (no window), so there is nothing to capture. Screenshots need the editor running with a display; on a server, run it under Xvfb.")
	await wait_for_filesystem()  # don't capture the "Scanning files" progress dialog
	var view := String(p.get("view", "auto"))
	var size := int(p.get("size", 768))
	if view == "auto":
		var root := EditorInterface.get_edited_scene_root()
		if root is Node3D:
			view = "3d"
		elif root is CanvasItem:
			view = "2d"
		else:
			view = "editor"
	var viewport: Viewport
	match view:
		"2d":
			EditorInterface.set_main_screen_editor("2D")
			viewport = EditorInterface.get_editor_viewport_2d()
		"3d":
			EditorInterface.set_main_screen_editor("3D")
			viewport = EditorInterface.get_editor_viewport_3d(int(p.get("viewport_index", 0)))
		"editor":
			viewport = EditorInterface.get_base_control().get_viewport()
		_:
			return invalid("`view` must be auto, 2d, 3d or editor")
	if viewport == null:
		return fail("No %s viewport is available." % view)
	# Let the editor draw at least one frame after switching screens.
	for i in 2:
		await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	if image == null or image.is_empty():
		return fail("The %s viewport returned no image (is the editor window minimized?)." % view)
	var w := image.get_width()
	var h := image.get_height()
	var long_edge: int = max(w, h)
	if long_edge > size:
		var scale := float(size) / long_edge
		image.resize(max(1, roundi(w * scale)), max(1, roundi(h * scale)), Image.INTERPOLATE_LANCZOS)
	if image.get_format() != Image.FORMAT_RGBA8 and image.get_format() != Image.FORMAT_RGB8:
		image.convert(Image.FORMAT_RGBA8)
	var png := image.save_png_to_buffer()
	var edited := EditorInterface.get_edited_scene_root()
	return {
		"image_base64": Marshalls.raw_to_base64(png),
		"mime_type": "image/png",
		"view": view,
		"width": image.get_width(),
		"height": image.get_height(),
		"scene": edited.scene_file_path if edited != null else "",
	}
