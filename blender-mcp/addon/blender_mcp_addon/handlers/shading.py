"""Materials, world, cameras and lights."""

from __future__ import annotations

import math
from typing import Any

import bpy
from mathutils import Vector

from . import paths
from .materials import get_material_info
from .objects import _summary
from .undo import mutation
from .util import get_material, get_object, rna_props, set_rna_props, vec

GENERATED_TEXTURES = {"CHECKER", "COLOR_GRID", "BLANK"}
TEXTURE_SIZE = 1024


def _rgba(value: Any, name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list | tuple) or len(value) not in (3, 4):
        raise ValueError(f"{name} must be [r, g, b] or [r, g, b, a] with values 0-1")
    rgba = [float(v) for v in value] + ([1.0] if len(value) == 3 else [])
    return tuple(rgba)  # type: ignore[return-value]


def _node(tree: bpy.types.NodeTree, node_type: str, name: str, location: tuple[int, int]):
    node = tree.nodes.get(name)
    if node is None:
        node = tree.nodes.new(node_type)
        node.name = node.label = name
        node.location = location
    return node


def _set_texture(mat: bpy.types.Material, bsdf: bpy.types.Node, params: dict[str, Any]) -> None:
    tree = mat.node_tree
    path = params.get("base_color_texture")
    generated = params.get("generated_texture")
    if path and generated:
        raise ValueError("give either base_color_texture or generated_texture, not both")
    if path:
        real = paths.resolve(path, paths.IMAGE_SUFFIXES, must_exist=True)
        image = bpy.data.images.load(str(real), check_existing=True)
    else:
        kind = str(generated).upper()
        if kind not in GENERATED_TEXTURES:
            raise ValueError(f"generated_texture must be one of {sorted(GENERATED_TEXTURES)}")
        image = bpy.data.images.new(f"{mat.name}_{kind.lower()}", TEXTURE_SIZE, TEXTURE_SIZE)
        image.generated_type = "UV_GRID" if kind == "CHECKER" else kind
    tex = _node(tree, "ShaderNodeTexImage", "MCP Base Color Texture", (-400, 300))
    tex.image = image
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    scale = params.get("texture_scale")
    if scale is not None:
        mapping = _node(tree, "ShaderNodeMapping", "MCP Texture Mapping", (-600, 300))
        coords = _node(tree, "ShaderNodeTexCoord", "MCP Texture Coordinates", (-800, 300))
        mapping.inputs["Scale"].default_value = (
            (scale, scale, scale) if isinstance(scale, int | float) else scale
        )
        tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])


def _apply_material_params(mat: bpy.types.Material, params: dict[str, Any]) -> None:
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        raise ValueError(f"{mat.name!r} has no Principled BSDF node to edit")
    inputs = bsdf.inputs

    if "base_color" in params:
        color = _rgba(params["base_color"], "base_color")
        if inputs["Base Color"].is_linked and not params.get("base_color_texture"):
            for link in list(inputs["Base Color"].links):
                tree.links.remove(link)
        inputs["Base Color"].default_value = color
        mat.diffuse_color = color  # viewport/Workbench display color
    for key, socket in (
        ("metallic", "Metallic"),
        ("roughness", "Roughness"),
        ("ior", "IOR"),
        ("transmission", "Transmission Weight"),
        ("emission_strength", "Emission Strength"),
    ):
        if key in params:
            inputs[socket].default_value = float(params[key])
    if "metallic" in params:
        mat.metallic = float(params["metallic"])
    if "roughness" in params:
        mat.roughness = float(params["roughness"])
    if "emission_color" in params:
        inputs["Emission Color"].default_value = _rgba(params["emission_color"], "emission_color")
        if "emission_strength" not in params and inputs["Emission Strength"].default_value == 0:
            inputs["Emission Strength"].default_value = 1.0
    if "alpha" in params:
        alpha = float(params["alpha"])
        inputs["Alpha"].default_value = alpha
        mat.diffuse_color[3] = alpha
        if hasattr(mat, "surface_render_method"):  # EEVEE Next (4.2+)
            mat.surface_render_method = "BLENDED" if alpha < 1 else "DITHERED"
        else:
            mat.blend_method = "BLEND" if alpha < 1 else "OPAQUE"
    if params.get("base_color_texture") or params.get("generated_texture"):
        _set_texture(mat, bsdf, params)


@mutation("create material")
def create_material(params: dict[str, Any]) -> dict[str, Any]:
    name = params["name"]
    if bpy.data.materials.get(name) is not None and not params.get("replace", False):
        raise ValueError(
            f"material {name!r} exists; use update_material, or replace=true to start over"
        )
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_fake_user = True  # keep it through save/reopen even before it is assigned
    try:
        _apply_material_params(mat, params)
    except Exception:
        bpy.data.materials.remove(mat)
        raise
    return get_material_info({"name": mat.name})


@mutation("update material")
def update_material(params: dict[str, Any]) -> dict[str, Any]:
    mat = get_material(params["name"])
    _apply_material_params(mat, params)
    return get_material_info({"name": mat.name})


@mutation("assign material")
def assign_material(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    mat = get_material(params["material"])
    if obj.data is None or not hasattr(obj.data, "materials"):
        raise ValueError(f"{obj.name!r} ({obj.type}) can't have materials")
    faces = params.get("faces")
    if params.get("select") is not None:
        if obj.type != "MESH":
            raise ValueError("select can only be given for meshes")
        from .mesh_edit import select_face_indices

        picked = select_face_indices(obj, params["select"])
        faces = sorted(set(picked) | set(faces or []))
        if not faces:
            raise ValueError("the selection matched no faces")
    slots = obj.data.materials
    if faces is None:
        # Whole object: this becomes its only material.
        slots.clear()
        slots.append(mat)
        if obj.type == "MESH":
            obj.data.polygons.foreach_set("material_index", [0] * len(obj.data.polygons))
    else:
        if obj.type != "MESH":
            raise ValueError("faces can only be given for meshes")
        count = len(obj.data.polygons)
        bad = [i for i in faces if not isinstance(i, int) or not 0 <= i < count]
        if bad:
            raise ValueError(f"face indices out of range 0..{count - 1}: {bad[:10]}")
        index = next((i for i, m in enumerate(slots) if m == mat), None)
        if index is None:
            slots.append(mat)
            index = len(slots) - 1
        for i in faces:
            obj.data.polygons[i].material_index = index
    obj.data.update()
    return {
        "object": obj.name,
        "slots": [m.name if m else None for m in slots],
        "faces_assigned": len(faces) if faces is not None else "all",
    }


@mutation("set world")
def set_world(params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    background = next((n for n in tree.nodes if n.type == "BACKGROUND"), None)
    output = next((n for n in tree.nodes if n.type == "OUTPUT_WORLD"), None)
    if background is None:
        background = tree.nodes.new("ShaderNodeBackground")
    if output is None:
        output = tree.nodes.new("ShaderNodeOutputWorld")
        tree.links.new(background.outputs["Background"], output.inputs["Surface"])

    if params.get("hdri_path"):
        real = paths.resolve(params["hdri_path"], paths.IMAGE_SUFFIXES, must_exist=True)
        env = _node(tree, "ShaderNodeTexEnvironment", "MCP Environment", (-300, 300))
        env.image = bpy.data.images.load(str(real), check_existing=True)
        tree.links.new(env.outputs["Color"], background.inputs["Color"])
        mapping = _node(tree, "ShaderNodeMapping", "MCP Environment Mapping", (-500, 300))
        coords = _node(tree, "ShaderNodeTexCoord", "MCP Environment Coordinates", (-700, 300))
        tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        mapping.inputs["Rotation"].default_value[2] = math.radians(
            float(params.get("hdri_rotation", 0))
        )
    elif "color" in params:
        for link in list(background.inputs["Color"].links):
            tree.links.remove(link)
        background.inputs["Color"].default_value = _rgba(params["color"], "color")
        world.color = _rgba(params["color"], "color")[:3]
    if "strength" in params:
        background.inputs["Strength"].default_value = float(params["strength"])

    color = background.inputs["Color"]
    return {
        "world": world.name,
        "color": {"linked_from": color.links[0].from_node.name}
        if color.is_linked
        else vec(color.default_value),
        "strength": round(background.inputs["Strength"].default_value, 4),
    }


@mutation("look at")
def look_at(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["name"])
    target = params["target"]
    if isinstance(target, str):
        point = get_object(target).matrix_world.translation.copy()
    elif isinstance(target, list | tuple) and len(target) == 3:
        point = Vector(target)
    else:
        raise ValueError("target must be an object name or [x, y, z]")
    direction = point - obj.matrix_world.translation
    if direction.length < 1e-6:
        raise ValueError("object is already at the target point")
    # Cameras, lights and most things "look" down their local -Z axis.
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return _summary(obj)


@mutation("set active camera")
def set_active_camera(params: dict[str, Any]) -> dict[str, Any]:
    cam = get_object(params["name"])
    if cam.type != "CAMERA":
        raise ValueError(f"{cam.name!r} is a {cam.type}, not a CAMERA")
    bpy.context.scene.camera = cam
    return {"camera": cam.name}


@mutation("set data params")
def set_data_params(params: dict[str, Any]) -> dict[str, Any]:
    """Generic setter for an object's data block: camera lens, light energy/size, ..."""
    obj = get_object(params["name"])
    if obj.data is None:
        raise ValueError(f"{obj.name!r} is an {obj.type} and has no data settings")
    set_rna_props(obj.data, params["params"])
    skip = {"animation_data", "shape_keys", "texture_mesh", "cycles"}
    return {"name": obj.name, "type": obj.type, "data": rna_props(obj.data, skip=skip)}
