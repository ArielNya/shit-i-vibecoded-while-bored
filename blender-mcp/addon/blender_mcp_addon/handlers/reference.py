"""Reference sheets: front/side images placed behind the model at true scale."""

from __future__ import annotations

from typing import Any

import bpy

from . import paths
from .undo import mutation
from .util import get_object, num

COLLECTION = "References"
VIEWS = {"front", "side", "back"}


def _collection() -> bpy.types.Collection:
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _material(name: str, image: bpy.types.Image, opacity: float) -> bpy.types.Material:
    """Unlit image, optionally see-through, that looks the same in every engine."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    emit = tree.nodes.new("ShaderNodeEmission")
    tree.links.new(tex.outputs["Color"], emit.inputs["Color"])
    shader = emit.outputs["Emission"]
    if opacity < 1:
        clear = tree.nodes.new("ShaderNodeBsdfTransparent")
        mix = tree.nodes.new("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = opacity
        tree.links.new(clear.outputs[0], mix.inputs[1])
        tree.links.new(shader, mix.inputs[2])
        shader = mix.outputs[0]
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    tree.links.new(shader, out.inputs["Surface"])
    mat.diffuse_color = (1, 1, 1, opacity)
    return mat


@mutation("add reference image")
def add_reference_image(params: dict[str, Any]) -> dict[str, Any]:
    view = params.get("view", "front")
    if view not in VIEWS:
        raise ValueError(f"view must be one of {sorted(VIEWS)}")
    real = paths.resolve(params["path"], paths.IMAGE_SUFFIXES, must_exist=True)
    image = bpy.data.images.load(str(real), check_existing=True)
    width_px, height_px = image.size
    if not width_px or not height_px:
        raise ValueError(f"could not read the image size of {real.name}")

    # Many character sheets hold every view in one image: `crop` picks this view's
    # region [left, top, right, bottom] in image pixels. All other pixel values are in
    # full-image coordinates too.
    crop = params.get("crop") or [0, 0, width_px, height_px]
    if len(crop) != 4:
        raise ValueError("crop must be [left, top, right, bottom] in pixels")
    c_left, c_top, c_right, c_bottom = (float(c) for c in crop)
    if not (0 <= c_left < c_right <= width_px and 0 <= c_top < c_bottom <= height_px):
        raise ValueError(
            f"crop must lie inside the image (0..{width_px} × 0..{height_px}) with "
            "left < right and top < bottom"
        )
    char_height = float(params.get("character_height", 1.8))
    top = float(params.get("pixel_top", c_top))  # rows counted from the image top
    bottom = float(params.get("pixel_bottom", c_bottom))
    center = float(params.get("pixel_center", (c_left + c_right) / 2))
    if not 0 <= top < bottom <= height_px:
        raise ValueError(f"need 0 <= pixel_top < pixel_bottom <= {height_px} (image height)")
    if char_height <= 0:
        raise ValueError("character_height must be > 0")

    scale = char_height / (bottom - top)  # world units per pixel
    w, h = (c_right - c_left) * scale, (c_bottom - c_top) * scale
    # Plane corners in its own 2D frame (u to the right, v up), feet row at v = 0.
    left = (c_left - center) * scale
    base = (bottom - c_bottom) * scale
    flip = view == "side" and params.get("facing", "left") == "right"
    distance = float(params.get("distance", char_height))  # behind the model
    offset = float(params.get("offset", 0.0))  # shift along the image's horizontal axis

    def place(u: float, v: float) -> tuple[float, float, float]:
        if view == "front":  # seen from -Y: screen right is +X
            return (u + offset, distance, v)
        if view == "back":  # seen from +Y: screen right is -X
            return (-(u + offset), -distance, v)
        # side, seen from +X (Blender's Right view): screen right is +Y, so a character
        # facing screen-left faces -Y like the model.
        return (-distance, (-u if flip else u) + offset, v)

    corners = [(left, base), (left + w, base), (left + w, base + h), (left, base + h)]
    verts = [place(u, v) for u, v in corners]
    u0, u1 = c_left / width_px, c_right / width_px
    v0, v1 = 1 - c_bottom / height_px, 1 - c_top / height_px
    uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if flip:
        uvs = [(u0 + u1 - x, y) for x, y in uvs]

    name = params.get("name") or f"Ref {view}"
    old = bpy.data.objects.get(name)
    if old is not None and old.get("mcp_reference"):
        bpy.data.objects.remove(old, do_unlink=True)  # re-adding replaces it
    mesh = bpy.data.meshes.new(name)
    faces = [(0, 1, 2, 3)] if view != "side" or not flip else [(3, 2, 1, 0)]
    mesh.from_pydata(verts, [], faces)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        uv_layer.data[loop.index].uv = uvs[loop.vertex_index]
    opacity = float(params.get("opacity", 1.0))
    mesh.materials.append(_material(name, image, max(0.05, min(opacity, 1.0))))
    obj = bpy.data.objects.new(name, mesh)
    obj["mcp_reference"] = view
    obj.hide_select = True  # so clicking in the viewport doesn't grab it
    _collection().objects.link(obj)
    return {
        "name": obj.name,
        "view": view,
        "image": {"file": real.name, "width": width_px, "height": height_px},
        "crop": [num(c) for c in (c_left, c_top, c_right, c_bottom)],
        "world_per_pixel": num(scale),
        "covers": {"width": num(w), "height": num(h)},
        "note": "Feet row is at z=0, head row at z=character_height, center column on the "
        "model's middle. Compare with render_preview(view='%s', ortho=True, textures=True)."
        % ("right" if view == "side" else view),
    }


@mutation("set visibility")
def set_visibility(params: dict[str, Any]) -> dict[str, Any]:
    names = params["names"] if isinstance(params["names"], list) else [params["names"]]
    objects = [get_object(n) for n in names]
    changed = []
    for obj in objects:
        if params.get("viewport") is not None:
            obj.hide_set(not params["viewport"])
        if params.get("render") is not None:
            obj.hide_render = not params["render"]
        changed.append(
            {"name": obj.name, "viewport": obj.visible_get(), "render": not obj.hide_render}
        )
    return {"objects": changed}
