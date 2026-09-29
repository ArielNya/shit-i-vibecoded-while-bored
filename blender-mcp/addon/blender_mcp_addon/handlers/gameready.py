"""Game-ready output: UV seams and unwrapping, baking high-poly detail, validation."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import bmesh
import bpy
import mathutils
import mathutils.kdtree

from . import paths
from .mesh_edit import _edit, _mesh_object, _refresh, select
from .undo import mutation, window_override
from .util import num

UNWRAP_METHODS = {"smart", "seams", "cube"}
BAKE_TYPES = {"normal": "NORMAL", "ao": "AO", "color": "DIFFUSE", "roughness": "ROUGHNESS"}
MAX_BAKE_SIZE = 8192


# --- seams and unwrapping -------------------------------------------------------------------


@mutation("mark seams")
def mark_seams(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    clear = bool(params.get("clear", False))
    with _edit(obj) as bm:
        kind = params.get("type", "edges")
        edges = select(bm, obj, params["select"], kind)
        if kind == "faces":  # the edges around the faces
            edges = list({e for face in edges for e in face.edges})
        for e in edges:
            e.seam = not clear
        total = sum(1 for e in bm.edges if e.seam)
    return {"name": obj.name, "edges_changed": len(edges), "seams_total": total}


@contextmanager
def _edit_mode(obj: bpy.types.Object) -> Iterator[None]:
    view_layer = bpy.context.view_layer
    previous = view_layer.objects.active
    view_layer.objects.active = obj
    override = {
        **window_override(),
        "active_object": obj,
        "object": obj,
        "selected_objects": [obj],
        "selected_editable_objects": [obj],
    }
    with bpy.context.temp_override(**override):
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            yield
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
    if previous is not None and previous.name in view_layer.objects:
        view_layer.objects.active = previous


def uv_report(obj: bpy.types.Object) -> dict[str, Any]:
    """Islands, how much of the 0-1 square they cover, and faces outside it."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        layer = bm.loops.layers.uv.active
        if layer is None:
            return {"uv_layer": None}
        _refresh(bm)
        parent = list(range(len(bm.faces)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for edge in bm.edges:
            faces = edge.link_faces
            if len(faces) != 2 or edge.seam:
                continue
            a, b = faces

            def uvs(face, edge=edge):
                return {
                    loop.vert.index: tuple(round(c, 5) for c in loop[layer].uv)
                    for loop in face.loops
                    if loop.vert in edge.verts
                }

            if uvs(a) == uvs(b):  # the edge isn't split in UV space
                parent[find(a.index)] = find(b.index)
        islands = len({find(f.index) for f in bm.faces})
        area, outside = 0.0, 0
        for face in bm.faces:
            pts = [loop[layer].uv for loop in face.loops]
            area += (
                abs(sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:] + pts[:1], strict=True)))
                / 2
            )
            if any(not (-1e-4 <= c <= 1 + 1e-4) for p in pts for c in p):
                outside += 1
        report: dict[str, Any] = {
            "uv_layer": obj.data.uv_layers.active.name,
            "islands": islands,
            "coverage": num(area),  # fraction of the 0-1 square used; 0.6-0.8 is good packing
            "faces_outside_0_1": outside,
            "seams": sum(1 for e in bm.edges if e.seam),
        }
        if area > 1.0 + 1e-3:
            report["note"] = (
                "islands overlap (coverage > 1): fine for tiling textures, wrong for baking "
                "or hand-painted textures; use method='smart' or 'seams'"
            )
        elif outside:
            report["note"] = "some faces lie outside the 0-1 square; unwrap again with pack"
        return report
    finally:
        bm.free()


@mutation("uv unwrap")
def uv_unwrap(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    method = params.get("method", "smart")
    if method not in UNWRAP_METHODS:
        raise ValueError(f"method must be one of {sorted(UNWRAP_METHODS)}")
    if obj.data.users > 1:
        raise ValueError(f"{obj.name!r} shares its mesh with other objects")
    margin = float(params.get("island_margin", 0.02))
    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")
    spec = params.get("select") or {"all": True}
    with _edit(obj) as bm:
        chosen = set(select(bm, obj, spec, "faces"))
        for face in bm.faces:
            face.select_set(face in chosen)
    if not chosen:
        raise ValueError("the selection matched no faces")
    with _edit_mode(obj):
        if method == "smart":
            bpy.ops.uv.smart_project(
                angle_limit=math.radians(float(params.get("angle_limit", 66))),
                island_margin=margin,
            )
        elif method == "seams":
            bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=margin)
        else:
            bpy.ops.uv.cube_project(cube_size=float(params.get("cube_size", 1.0)))
        if method != "smart" and params.get("pack", True):
            bpy.ops.uv.select_all(action="SELECT")
            bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    return {"name": obj.name, "method": method, "faces": len(chosen), **uv_report(obj)}


def get_uv_info(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    return {"name": obj.name, **uv_report(obj)}


# --- baking --------------------------------------------------------------------------------


def _bake_image(name: str, size: int, non_color: bool) -> bpy.types.Image:
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    image = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    return image


def _target_node(mat: bpy.types.Material, image: bpy.types.Image) -> bpy.types.Node:
    nodes = mat.node_tree.nodes
    node = nodes.new("ShaderNodeTexImage")
    node.name = node.label = f"bake {image.name}"
    node.image = image
    node.location = (-700, -300)
    for n in nodes:
        n.select = False
    node.select = True
    nodes.active = node
    return node


def _principled(mat: bpy.types.Material) -> bpy.types.Node | None:
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _wire(mat: bpy.types.Material, node: bpy.types.Node, kind: str) -> None:
    bsdf = _principled(mat)
    if bsdf is None:
        return
    links = mat.node_tree.links
    if kind == "normal":
        normal_map = mat.node_tree.nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-350, -300)
        links.new(node.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    elif kind == "color":
        links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    elif kind == "roughness":
        links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
    # AO is left unlinked: engines take it as a separate map (glTF occlusion / ORM).


@mutation("bake maps")
def bake_maps(params: dict[str, Any]) -> dict[str, Any]:
    low = _mesh_object(params["low"])
    high = [_mesh_object(n) for n in params.get("high") or []]
    if low in high:
        raise ValueError("the low-poly object can't also be a high-poly source")
    kinds = params.get("maps") or ["normal"]
    unknown = [k for k in kinds if k not in BAKE_TYPES]
    if unknown:
        raise ValueError(f"unknown map types {unknown}; use {sorted(BAKE_TYPES)}")
    if "normal" in kinds and not high:
        raise ValueError("a normal map needs `high` (the detailed mesh to bake from)")
    if not low.data.uv_layers:
        raise ValueError(f"{low.name!r} has no UVs; run uv_unwrap first")
    size = int(params.get("size", 1024))
    if not 16 <= size <= MAX_BAKE_SIZE:
        raise ValueError(f"size must be between 16 and {MAX_BAKE_SIZE}")
    folder = params.get("folder", "bakes")
    overwrite = bool(params.get("overwrite", False))
    targets = {
        k: paths.resolve(f"{folder}/{low.name}_{k}.png", {".png"}, overwrite=overwrite)
        for k in kinds
    }
    if not low.data.materials or low.data.materials[0] is None:
        mat = bpy.data.materials.new(f"{low.name}_baked")
        mat.use_nodes = True
        low.data.materials.append(mat)
    mats = [m for m in low.data.materials if m is not None]
    for m in mats:
        m.use_nodes = True

    scene = bpy.context.scene
    saved = {
        "engine": scene.render.engine,
        "samples": scene.cycles.samples,
        "device": scene.cycles.device,
    }
    view_layer = bpy.context.view_layer
    selection = [o for o in view_layer.objects if o.select_get()]
    active = view_layer.objects.active
    results: dict[str, Any] = {}
    try:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = int(params.get("samples", 16))
        bake = scene.render.bake
        bake.use_selected_to_active = bool(high)
        bake.cage_extrusion = float(params.get("cage_extrusion", 0.02))
        bake.max_ray_distance = float(params.get("max_ray_distance", 0.0))
        bake.margin = int(params.get("margin", 8))
        for o in selection:
            o.select_set(False)
        for o in [*high, low]:
            o.hide_set(False)
            o.hide_render = False
            o.select_set(True)
        view_layer.objects.active = low
        for kind in kinds:
            image = _bake_image(f"{low.name}_{kind}", size, non_color=kind != "color")
            nodes = [(m, _target_node(m, image)) for m in mats]
            override = {
                **window_override(),
                "active_object": low,
                "object": low,
                "selected_objects": [*high, low],
                "selected_editable_objects": [*high, low],
            }
            extra: dict[str, Any] = {}
            if kind == "color":
                extra = {"pass_filter": {"COLOR"}}
            with bpy.context.temp_override(**override):
                bpy.ops.object.bake(type=BAKE_TYPES[kind], **extra)
            paths.prepare_write(targets[kind])
            image.filepath_raw = str(targets[kind])
            image.file_format = "PNG"
            image.save()
            wire = bool(params.get("wire", True))
            for m, node in nodes:
                if wire:
                    _wire(m, node, kind)
                else:
                    m.node_tree.nodes.remove(node)
            results[kind] = {
                "file": targets[kind].name,
                "image": image.name,
                # AO stays an unlinked texture node: engines want it as its own map.
                "linked": wire and kind != "ao",
            }
    finally:
        scene.render.engine = saved["engine"]
        scene.cycles.samples = saved["samples"]
        scene.cycles.device = saved["device"]
        for o in view_layer.objects:
            o.select_set(o in selection)
        view_layer.objects.active = active
    return {
        "low": low.name,
        "high": [h.name for h in high],
        "size": size,
        "maps": results,
        "folder": str(targets[kinds[0]].parent),
    }


# --- validation ----------------------------------------------------------------------------


def _mirror_ratio(bm: bmesh.types.BMesh, tolerance: float) -> float:
    """Share of vertices that have a partner mirrored across X (1.0 = symmetric)."""
    tree = mathutils.kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        tree.insert(v.co, v.index)
    tree.balance()
    matched = 0
    for v in bm.verts:
        _, _, dist = tree.find(mathutils.Vector((-v.co.x, v.co.y, v.co.z)))
        matched += dist is not None and dist <= tolerance
    return matched / max(len(bm.verts), 1)


def _signed_volume(bm: bmesh.types.BMesh) -> float:
    total = 0.0
    for face in bm.faces:
        verts = [v.co for v in face.verts]
        for i in range(1, len(verts) - 1):
            total += verts[0].dot(verts[i].cross(verts[i + 1])) / 6
    return total


def _weights_report(obj: bpy.types.Object, arm: bpy.types.Object, max_influences: int):
    bones = set(arm.data.bones.keys())
    names = {g.index: g.name for g in obj.vertex_groups}
    unweighted = too_many = not_normalized = 0
    for v in obj.data.vertices:
        ws = [g.weight for g in v.groups if names.get(g.group) in bones and g.weight > 1e-4]
        if not ws:
            unweighted += 1
            continue
        too_many += len(ws) > max_influences
        not_normalized += abs(sum(ws) - 1) > 0.01
    return unweighted, too_many, not_normalized


def _where(points: list, obj: bpy.types.Object, limit: int = 3) -> str:
    """A few world positions, rounded: enough to aim a position-bounded selection."""
    shown = [
        "[" + ", ".join(f"{c:.2f}" for c in obj.matrix_world @ p) + "]" for p in points[:limit]
    ]
    more = f" +{len(points) - limit} more" if len(points) > limit else ""
    return ", ".join(shown) + more


def check_game_ready(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    kind = params.get("kind", "character")
    if kind not in {"character", "prop", "part"}:
        raise ValueError("kind must be 'character', 'prop' or 'part'")
    budget = params.get("max_triangles")
    max_influences = int(params.get("max_influences", 4))
    fails: list[str] = []
    warnings: list[str] = []
    mesh = obj.data

    # Transforms: engines and rigs expect applied rotation/scale.
    if any(abs(a) > 1e-4 for a in obj.rotation_euler):
        fails.append("rotation not applied: apply_transform(rotation=true)")
    if any(abs(s - 1) > 1e-4 for s in obj.scale):
        fails.append("scale not applied: apply_transform(scale=true)")
    # Rest shape (not the posed/animated one): the raw mesh in world space.
    corners = [obj.matrix_world @ v.co for v in mesh.vertices] or [obj.matrix_world.translation]
    low = mathutils.Vector([min(c[i] for c in corners) for i in range(3)])
    high = mathutils.Vector([max(c[i] for c in corners) for i in range(3)])
    if kind == "character":
        if abs(low.z) > 0.01:
            fails.append(f"feet at z={low.z:.3f}, not on the ground (z=0)")
        if abs((low.x + high.x) / 2) > 0.02:
            fails.append("not centred on x=0 (mirror/rig symmetry breaks)")
        if (obj.matrix_world.translation - mathutils.Vector((0, 0, 0))).length > 1e-3:
            warnings.append("origin isn't at the world origin (between the feet)")
    live = [m.type for m in obj.modifiers if m.type not in {"ARMATURE"}]
    if live:
        warnings.append(f"unapplied modifiers {live}: apply before export/rigging if needed")

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        _refresh(bm)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        ngon_faces = [f for f in bm.faces if len(f.verts) > 4]
        open_edges = [e for e in bm.edges if not e.is_manifold]
        non_manifold = len(open_edges)
        loose_verts = sum(1 for v in bm.verts if not v.link_edges)
        loose_edges = sum(1 for e in bm.edges if not e.link_faces)
        degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        tree = mathutils.kdtree.KDTree(len(bm.verts))
        for v in bm.verts:
            tree.insert(v.co, v.index)
        tree.balance()
        doubled = [v for v in bm.verts if len(tree.find_range(v.co, 1e-5)) > 1]
        # Faces lying on top of each other: the caps left inside when touching basic
        # shapes are joined (a head on a neck, an ear on a head).
        face_tree = mathutils.kdtree.KDTree(len(bm.faces))
        for f in bm.faces:
            face_tree.insert(f.calc_center_median(), f.index)
        face_tree.balance()
        coincident = [
            f
            for f in bm.faces
            if any(
                i != f.index and abs(abs(bm.faces[i].normal.dot(f.normal)) - 1) < 1e-3
                for _, i, _ in face_tree.find_range(f.calc_center_median(), 1e-4)
            )
        ]
        rigid = kind in {"prop", "part"}
        if ngon_faces:
            where = _where([f.calc_center_median() for f in ngon_faces], obj)
            if kind == "character":
                fails.append(
                    f"{len(ngon_faces)} n-gons (at {where}): they triangulate unpredictably "
                    "and deform badly"
                )
            else:
                warnings.append(
                    f"{len(ngon_faces)} n-gons (at {where}): fine on flat caps that never "
                    "deform; split them if they shade oddly"
                )
        if coincident:
            (warnings if rigid else fails).append(
                f"{len(coincident)} faces lie on top of other faces (at "
                f"{_where([f.calc_center_median() for f in coincident], obj)}): hidden caps "
                "from joining touching parts. delete_elements them (select by position), "
                "then merge_by_distance"
            )
        if non_manifold:
            (warnings if rigid else fails).append(
                f"{non_manifold} non-manifold edges (holes or internal faces) at "
                f"{_where([(e.verts[0].co + e.verts[1].co) / 2 for e in open_edges], obj)}"
            )
        if loose_verts or loose_edges:
            fails.append(f"{loose_verts} loose vertices, {loose_edges} loose edges")
        if degenerate:
            fails.append(f"{degenerate} zero-area faces")
        if doubled:
            fails.append(
                f"{len(doubled)} doubled vertices (at {_where([v.co for v in doubled], obj)}): "
                "merge_by_distance; if parts were joined, delete the hidden caps first"
            )
        if not non_manifold and bm.faces and _signed_volume(bm) < 0:
            fails.append("normals point inward: recalc_normals")
        symmetry = None
        if kind == "character" and params.get("symmetric", True):
            symmetry = round(_mirror_ratio(bm, float(params.get("symmetry_tolerance", 1e-3))), 3)
            if symmetry < 0.98:
                warnings.append(
                    f"only {symmetry:.0%} of vertices are mirrored across X; asymmetric "
                    "characters are fine, but mirrored weights/poses need symmetry"
                )
    finally:
        bm.free()
    if budget is not None and tris > int(budget):
        fails.append(f"{tris} triangles, over the budget of {budget}")

    uv = uv_report(obj)
    if uv.get("uv_layer") is None:
        fails.append("no UVs: uv_unwrap")
    elif uv.get("note"):
        warnings.append(f"UVs: {uv['note']}")
    slots = [s.material for s in obj.material_slots]
    if not slots or any(m is None for m in slots):
        warnings.append("empty or missing material slots")
    elif len(slots) > 3:
        warnings.append(f"{len(slots)} materials = {len(slots)} draw calls; merge or atlas")

    rig: dict[str, Any] | None = None
    arm_mod = next((m for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
    if arm_mod is not None:
        arm = arm_mod.object
        unweighted, too_many, not_norm = _weights_report(obj, arm, max_influences)
        rig = {"armature": arm.name, "bones": len(arm.data.bones)}
        if unweighted:
            fails.append(f"{unweighted} vertices have no bone weight: set_vertex_weights")
        if too_many:
            warnings.append(
                f"{too_many} vertices use more than {max_influences} bones (engines keep the "
                "strongest; fine for glTF, check for mobile)"
            )
        if not_norm:
            warnings.append(
                f"{not_norm} vertices' weights don't sum to 1 (Blender and glTF normalise, "
                "some engines don't): bind_to_armature again"
            )
        if any(abs(a) > 1e-4 for a in arm.rotation_euler) or any(
            abs(s - 1) > 1e-4 for s in arm.scale
        ):
            fails.append("armature has unapplied rotation/scale")
        left = [b for b in arm.data.bones if b.name.endswith((".L", "_L", ".l"))]
        if left and sum((arm.matrix_world @ b.head_local).x < -1e-3 for b in left) > 0:
            fails.append("some .L bones are on -X: the character's left must be +X")
    elif kind in {"character", "part"} and params.get("expect_rig", False):
        fails.append("not bound to an armature: bind_to_armature")

    return {
        "name": obj.name,
        "ok": not fails,
        "fails": fails,
        "warnings": warnings,
        "stats": {
            "triangles": tris,
            "vertices": len(mesh.vertices),
            "materials": len(slots),
            "size": [num(v) for v in high - low],
            "symmetry": symmetry,
            "uv": {k: uv.get(k) for k in ("islands", "coverage")},
            "rig": rig,
        },
    }
