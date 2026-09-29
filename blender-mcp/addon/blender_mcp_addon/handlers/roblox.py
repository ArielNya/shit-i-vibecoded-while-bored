"""Roblox avatar assets: bake to one texture, and check against Roblox's specifications.

Units: 1 Blender unit = 1 stud (export FBX with "FBX Unit Scale", or glTF). Axes: Blender's
Z up and -Y front become Roblox's Y up and front on export. Numbers come from Roblox's
creator docs (avatar/rigid-accessories, layered-accessories, character-bodies specs)."""

from __future__ import annotations

import math
from typing import Any

import bmesh
import bpy
from mathutils import Vector

from . import paths
from .files import _ops_context, _selection
from .undo import ensure_object_mode, mutation
from .util import get_object, num, vec

MAX_TRIS = 4000  # rigid and layered accessories
MAX_TEXTURE = 2048  # Marketplace
MAX_INFLUENCES = 4

# Rigid accessory size limits in studs, centred on the attachment unless split:
# type -> scale -> (width, (up, down), (front, behind)).
_C = lambda w, h, d: (w, (h / 2, h / 2), (d / 2, d / 2))  # noqa: E731
RIGID_SIZES: dict[str, dict[str, tuple]] = {
    "hat": {"normal": _C(1.87, 2.5, 1.87), "slender": _C(1.78, 2.5, 1.78),
            "classic": _C(3, 4, 3)},
    "hair": {"normal": (1.87, (1.25, 1.875), (0.9375, 1.25)),
             "slender": (1.78, (1.25, 1.875), (1.892, 1.189)),
             "classic": (3, (2, 3), (1.5, 2))},
    "face": {"normal": _C(1.87, 1.25, 1.25), "slender": _C(1.78, 1.25, 1.18),
             "classic": _C(3, 2, 2)},
    "neck": {"normal": _C(2.95, 3.68, 2.16), "slender": _C(2.59, 3.39, 1.92),
             "classic": _C(3, 3, 2)},
    "shoulder_neck": {"normal": _C(6.90, 3.68, 3.24), "slender": _C(6.05, 3.39, 2.88),
                      "classic": _C(7, 3, 3)},
    "shoulder_collar": {"normal": _C(2.95, 3.68, 3.24), "slender": _C(2.59, 3.39, 2.88),
                        "classic": _C(3, 3, 3)},
    "shoulder": {"normal": _C(2.67, 4.40, 3.09), "slender": _C(2.37, 3.96, 2.75),
                 "classic": _C(3, 3, 3)},
    "front": {"normal": _C(2.95, 3.68, 3.24), "slender": _C(2.59, 3.39, 2.88),
              "classic": _C(3, 3, 3)},
    "back": {"normal": (9.86, (4.295, 4.295), (1.623, 3.246)),
             "slender": (8.64, (3.955, 3.955), (1.443, 2.886)),
             "classic": (10, (3.5, 3.5), (1.5, 3))},
    "waist": {"normal": (3.94, (1.842, 2.457), (3.785, 3.785)),
              "slender": (3.76, (1.414, 1.885), (3.365, 3.365)),
              "classic": (4, (1.5, 2), (3.5, 3.5))},
}  # fmt: skip
ATTACHMENTS = {
    "hat": "HatAttachment", "hair": "HairAttachment", "face": "FaceFrontAttachment",
    "neck": "NeckAttachment", "shoulder_neck": "NeckAttachment",
    "shoulder_collar": "LeftCollarAttachment / RightCollarAttachment",
    "shoulder": "LeftShoulderAttachment / RightShoulderAttachment",
    "front": "BodyFrontAttachment", "back": "BodyBackAttachment",
    "waist": "WaistFrontAttachment / WaistCenterAttachment / WaistBackAttachment",
}  # fmt: skip
LAYERED_SIZE = 8.0  # shirts, jackets, pants, dresses...: 8 x 8 x 8 studs

R15_BONES = [
    "Root", "HumanoidRootNode", "LowerTorso", "UpperTorso", "Head",
    "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot",
]  # fmt: skip
BODY_PARTS = R15_BONES[2:]  # the 15 meshes, as <Part>_Geo
BODY_BUDGETS = {  # asset -> (parts, max triangles)
    "DynamicHead": (["Head"], 4000),
    "Torso": (["UpperTorso", "LowerTorso"], 1750),
    "LeftArm": (["LeftUpperArm", "LeftLowerArm", "LeftHand"], 1248),
    "RightArm": (["RightUpperArm", "RightLowerArm", "RightHand"], 1248),
    "LeftLeg": (["LeftUpperLeg", "LeftLowerLeg", "LeftFoot"], 1248),
    "RightLeg": (["RightUpperLeg", "RightLowerLeg", "RightFoot"], 1248),
}
BODY_MAX = {"normal": (8.6, 9.5, 2.25), "slender": (6, 9.5, 2), "classic": (8, 9.1, 2)}
BODY_MIN = (1.35, 3.6, 0.7)
BODY_ATTACHMENTS = [
    "FaceCenter", "FaceFront", "Hat", "Hair", "LeftCollar", "RightCollar", "Neck", "BodyBack",
    "BodyFront", "Root", "WaistFront", "WaistBack", "WaistCenter", "RightShoulder",
    "RightGrip", "LeftShoulder", "LeftGrip", "RightFoot", "LeftFoot",
]  # fmt: skip


# --- bake ---------------------------------------------------------------------------------


def _mesh(name: str) -> bpy.types.Object:
    obj = get_object(name)
    if obj.type != "MESH":
        raise ValueError(f"{obj.name!r} is a {obj.type}, not a MESH")
    return obj


def _smart_unwrap(obj: bpy.types.Object, island_margin: float) -> None:
    with _selection([obj]), _ops_context():
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=island_margin)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")


@mutation("bake texture")
def bake_texture(params: dict[str, Any]) -> dict[str, Any]:
    """Unwrap to a fresh UV map, bake every material's colour into one image, save it,
    and replace the materials with a single one using that image."""
    ensure_object_mode()
    obj = _mesh(params["object"])
    size = int(params.get("size", 1024))
    if not 16 <= size <= 4096:
        raise ValueError("size must be 16-4096 (Marketplace items: at most 2048)")
    target = paths.resolve(params["path"], {".png"}, overwrite=bool(params.get("overwrite")))
    sources = [m for m in obj.data.materials if m is not None]
    if not sources:
        raise ValueError(f"{obj.name!r} has no materials to bake; assign_material first")
    if len(obj.data.uv_layers) >= 8:
        raise ValueError("the mesh already has 8 UV maps (Blender's limit)")

    # Bake into a new UV map; source textures keep sampling their own (render) UV map.
    old_uvs = [uv.name for uv in obj.data.uv_layers]
    uv = obj.data.uv_layers.new(name="RobloxUV")
    obj.data.uv_layers.active = uv
    _smart_unwrap(obj, float(params.get("island_margin", 0.02)))

    image = bpy.data.images.new(f"{obj.name}_baked", size, size, alpha=False)
    added: list[tuple[bpy.types.Material, bpy.types.Node]] = []
    scene = bpy.context.scene
    engine = scene.render.engine
    try:
        for mat in sources:
            mat.use_nodes = True
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = image
            mat.node_tree.nodes.active = node
            added.append((mat, node))
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = int(params.get("samples", 4))
        with _selection([obj]), _ops_context():
            bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"},
                                margin=int(params.get("margin", 8)), use_clear=True)  # fmt: skip
    finally:
        scene.render.engine = engine
        for mat, node in added:
            mat.node_tree.nodes.remove(node)

    paths.prepare_write(target)
    image.filepath_raw = str(target)
    image.file_format = "PNG"
    image.save()

    baked = bpy.data.materials.new(f"{obj.name}_Baked")
    baked.use_nodes = True
    tree = baked.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.8
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.location = (-400, 300)
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(baked)
    obj.data.polygons.foreach_set("material_index", [0] * len(obj.data.polygons))
    for name in old_uvs:  # Roblox reads one UV set
        obj.data.uv_layers.remove(obj.data.uv_layers[name])
    obj.data.uv_layers.active = obj.data.uv_layers["RobloxUV"]
    obj.data.uv_layers["RobloxUV"].active_render = True
    obj.data.update()
    return {
        "object": obj.name,
        "image": str(target),
        "size": [size, size],
        "material": baked.name,
        "replaced_materials": [m.name for m in sources],
        "uv_map": "RobloxUV",
    }


# --- check --------------------------------------------------------------------------------


def _bounds(objs: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    if not points:
        raise ValueError("no vertices")
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    return lo, hi


def _mesh_stats(obj: bpy.types.Object) -> dict[str, Any]:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        open_edges = sum(1 for e in bm.edges if not e.is_manifold)
        loose = sum(1 for v in bm.verts if not v.link_faces)
    finally:
        bm.free()
    polys = obj.data.polygons
    stats = {
        "triangles": sum(len(p.vertices) - 2 for p in polys),
        "ngons": sum(1 for p in polys if len(p.vertices) > 4),
        "non_manifold_edges": open_edges,
        "loose_vertices": loose,
        "uv_maps": len(obj.data.uv_layers),
        "materials": len([m for m in obj.data.materials if m]),
    }
    if obj.data.uv_layers:
        uv = obj.data.uv_layers.active.data
        stats["uvs_outside_0_1"] = sum(
            1 for d in uv if not (-1e-4 <= d.uv[0] <= 1.0001 and -1e-4 <= d.uv[1] <= 1.0001)
        )
    return stats


def _textures(obj: bpy.types.Object) -> list[dict[str, Any]]:
    out = []
    for mat in obj.data.materials:
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    out.append({"material": mat.name, "image": node.image.name,
                                "size": list(node.image.size)})  # fmt: skip
    return out


def _mesh_problems(obj: bpy.types.Object, errors: list[str], warnings: list[str],
                   max_tris: int | None) -> dict[str, Any]:  # fmt: skip
    """The custom-mesh rules every avatar mesh shares."""
    s = _mesh_stats(obj)
    s["textures"] = _textures(obj)
    n = obj.name
    if max_tris is not None and s["triangles"] > max_tris:
        errors.append(f"{n}: {s['triangles']} triangles, the limit is {max_tris}")
    if s["non_manifold_edges"]:
        errors.append(f"{n}: not watertight ({s['non_manifold_edges']} open or non-manifold "
                      "edges); close the holes or merge_by_distance")  # fmt: skip
    if s["loose_vertices"]:
        warnings.append(f"{n}: {s['loose_vertices']} loose vertices; delete them")
    if s["ngons"]:
        warnings.append(f"{n}: {s['ngons']} faces with 5+ sides; use quads or triangles")
    if s["materials"] > 1:
        errors.append(f"{n}: {s['materials']} materials; Roblox meshes take one "
                      "(bake_texture merges them)")  # fmt: skip
    if s["uv_maps"] > 1:
        errors.append(f"{n}: {s['uv_maps']} UV maps; Roblox reads one")
    if s["uv_maps"] == 0 and s["textures"]:
        errors.append(f"{n}: textured but has no UV map")
    if s.get("uvs_outside_0_1"):
        warnings.append(f"{n}: {s['uvs_outside_0_1']} UVs outside 0-1")
    for t in s["textures"]:
        if max(t["size"]) > MAX_TEXTURE:
            errors.append(f"{n}: texture {t['image']} is {t['size']}; the Marketplace limit "
                          f"is {MAX_TEXTURE}x{MAX_TEXTURE}")  # fmt: skip
    if len(s["textures"]) > 1:
        warnings.append(f"{n}: {len(s['textures'])} image textures; only one colour map "
                        "comes through as TextureID")  # fmt: skip
    if any(abs(v - 1) > 1e-4 for v in obj.scale) or any(abs(a) > 1e-4 for a in
                                                         obj.rotation_euler):  # fmt: skip
        warnings.append(f"{n}: unapplied rotation/scale; apply_transform before export")
    if any(m.type != "ARMATURE" for m in obj.modifiers):
        warnings.append(f"{n}: has modifiers; they're applied on export, but check the "
                        "triangle count after applying")  # fmt: skip
    return s


def _influences(obj: bpy.types.Object, bones: set[str]) -> tuple[int, int, int]:
    """(vertices over the influence limit, unweighted vertices, vertices on Root)."""
    groups = {g.index: g.name for g in obj.vertex_groups}
    over = unweighted = on_root = 0
    for v in obj.data.vertices:
        used = [g for g in v.groups if g.weight > 1e-4 and groups.get(g.group) in bones]
        over += len(used) > MAX_INFLUENCES
        unweighted += not used
        on_root += any(groups.get(g.group) == "Root" for g in used)
    return over, unweighted, on_root


def _armature_of(obj: bpy.types.Object) -> bpy.types.Object | None:
    mod = next((m for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
    if mod:
        return mod.object
    return obj.parent if obj.parent and obj.parent.type == "ARMATURE" else None


def _check_rigid(params, errors, warnings) -> dict[str, Any]:
    obj = _mesh(params["object"])
    kind = params.get("accessory_type", "hat")
    scale = params.get("body_scale", "normal")
    if kind not in RIGID_SIZES or scale not in RIGID_SIZES[kind]:
        raise ValueError(f"accessory_type must be one of {sorted(RIGID_SIZES)}, body_scale "
                         "normal / slender / classic")  # fmt: skip
    stats = _mesh_problems(obj, errors, warnings, MAX_TRIS)
    width, (up, down), (front, behind) = RIGID_SIZES[kind][scale]
    lo, hi = _bounds([obj])
    at = params.get("attachment")
    if at is None:
        at = (lo + hi) / 2
        warnings.append("no attachment point given: the size is checked around the mesh's "
                        "centre; pass attachment (e.g. Hat_Att from the rig template)")  # fmt: skip
    at = Vector(at)
    # Blender: X width, Z up, -Y front.
    reach = {
        "left/right": (max(at.x - lo.x, hi.x - at.x), width / 2),
        "up": (hi.z - at.z, up),
        "down": (at.z - lo.z, down),
        "front": (at.y - lo.y, front),
        "behind": (hi.y - at.y, behind),
    }
    for side, (got, limit) in reach.items():
        if got > limit + 1e-4:
            errors.append(f"{obj.name}: reaches {got:.3f} studs {side} of the attachment; "
                          f"a {scale} {kind} may reach {limit:.3f}")  # fmt: skip
    # Studio centres an imported MeshPart on its bounds. Blender (x, y, z) with the front
    # at -Y becomes Roblox (-x, z, y) with the front at -Z, as characters face.
    offset = at - (lo + hi) / 2
    stats.update(
        size_studs=vec(hi - lo),
        attachment=vec(at),
        handle_attachment_position=vec((-offset.x, offset.z, offset.y)),
        reach={k: num(v[0]) for k, v in reach.items()},
        limits={k: num(v[1]) for k, v in reach.items()},
        roblox_attachment=ATTACHMENTS[kind],
    )
    return {obj.name: stats}


def _check_layered(params, errors, warnings) -> dict[str, Any]:
    obj = _mesh(params["object"])
    stats = _mesh_problems(obj, errors, warnings, MAX_TRIS)
    lo, hi = _bounds([obj])
    size = hi - lo
    if max(size) > LAYERED_SIZE + 1e-4:
        errors.append(f"{obj.name}: {vec(size)} studs; layered clothing fits in "
                      f"{LAYERED_SIZE:g} x {LAYERED_SIZE:g} x {LAYERED_SIZE:g}")  # fmt: skip
    cages = {}
    for suffix in ("_InnerCage", "_OuterCage"):
        cage = bpy.data.objects.get(obj.name + suffix)
        if cage is None or cage.type != "MESH":
            errors.append(f"missing cage mesh {obj.name}{suffix} (start from Roblox's cage "
                          "templates; don't delete cage vertices or edit their UVs)")  # fmt: skip
        else:
            cages[suffix] = cage
    if len(cages) == 2:
        inner, outer = cages["_InnerCage"], cages["_OuterCage"]
        if len(inner.data.vertices) != len(outer.data.vertices):
            errors.append("inner and outer cages have different vertex counts; they must "
                          "stay the same template mesh")  # fmt: skip
        stats["cage_vertices"] = len(inner.data.vertices)
        clo, chi = _bounds([outer])
        if any(clo[i] > lo[i] + 1e-3 or chi[i] < hi[i] - 1e-3 for i in range(3)):
            warnings.append("the outer cage doesn't enclose the clothing's bounds; inflate it "
                            "over the mesh")  # fmt: skip
    if _armature_of(obj) is None:
        warnings.append(f"{obj.name}: not skinned; fine with Automatic Skinning Transfer "
                        "(WrapLayer.AutoSkin = EnabledOverride in Studio), or bind it to the "
                        "R15 rig")  # fmt: skip
    else:
        _check_skin(obj, stats, errors, warnings)
    return {obj.name: stats}


def _check_skin(obj, stats, errors, warnings) -> None:
    arm = _armature_of(obj)
    if arm is None:
        errors.append(f"{obj.name}: not skinned to the R15 armature")
        return
    bones = {b.name for b in arm.data.bones}
    missing = [b for b in R15_BONES if b not in bones]
    if missing:
        errors.append(f"armature {arm.name} lacks R15 bones {missing[:6]}; use Roblox's "
                      "Rig_and_Attachments_Template")  # fmt: skip
    over, unweighted, on_root = _influences(obj, bones)
    if over:
        errors.append(f"{obj.name}: {over} vertices have more than {MAX_INFLUENCES} bone "
                      "influences")  # fmt: skip
    if unweighted:
        errors.append(f"{obj.name}: {unweighted} vertices have no bone weights")
    if on_root:
        errors.append(f"{obj.name}: {on_root} vertices are weighted to Root")
    stats["armature"] = arm.name


def _check_body(params, errors, warnings) -> dict[str, Any]:
    scale = params.get("body_scale", "normal")
    if scale not in BODY_MAX:
        raise ValueError("body_scale must be normal, slender or classic")
    parts = {p: bpy.data.objects.get(f"{p}_Geo") for p in BODY_PARTS}
    missing = [f"{p}_Geo" for p, o in parts.items() if o is None or o.type != "MESH"]
    if missing:
        errors.append(f"missing body meshes: {missing}")
    found = {p: o for p, o in parts.items() if o is not None and o.type == "MESH"}
    report: dict[str, Any] = {}
    for part, obj in found.items():
        report[obj.name] = _mesh_problems(obj, errors, warnings, None)
        _check_skin(obj, report[obj.name], errors, warnings)
        if f"{part}_OuterCage" not in bpy.data.objects:
            errors.append(f"missing {part}_OuterCage (from Roblox's body cage templates)")
    for asset, (members, budget) in BODY_BUDGETS.items():
        tris = sum(report[f"{m}_Geo"]["triangles"] for m in members if f"{m}_Geo" in report)
        if tris > budget:
            errors.append(f"{asset}: {tris} triangles, the budget is {budget}")
    if found:
        lo, hi = _bounds(list(found.values()))
        size = hi - lo  # Roblox X, Y(up), Z = Blender X, Z, Y
        dims = (size.x, size.z, size.y)
        for axis, got, most, least in zip("XYZ", dims, BODY_MAX[scale], BODY_MIN, strict=True):
            if got > most + 1e-4 or got < least - 1e-4:
                errors.append(f"body {axis} is {got:.2f} studs; a {scale} body is "
                              f"{least}-{most}")  # fmt: skip
        report["size_studs"] = [num(d) for d in dims]
    atts = [a for a in BODY_ATTACHMENTS if f"{a}_Att" not in bpy.data.objects]
    if atts:
        errors.append(f"missing attachment meshes: {[a + '_Att' for a in atts]}")
    return report


def check_roblox_asset(params: dict[str, Any]) -> dict[str, Any]:
    ensure_object_mode()
    errors: list[str] = []
    warnings: list[str] = []
    kind = params.get("kind", "rigid")
    checks = {"rigid": _check_rigid, "layered": _check_layered, "body": _check_body}
    if kind not in checks:
        raise ValueError("kind must be rigid, layered or body")
    if abs(bpy.context.scene.unit_settings.scale_length - 1) > 1e-6:
        warnings.append("scene Unit Scale isn't 1: sizes below assume 1 unit = 1 stud")
    report = checks[kind](params, errors, warnings)
    return {"ok": not errors, "kind": kind, "errors": errors, "warnings": warnings,
            "objects": report}  # fmt: skip
