"""Rigging: armatures (generic and humanoid), binding meshes, weights, posing.

Conventions: Z up, the character faces -Y (Blender's front view), its left side is +X,
so left bones are "*.L" on +X and right bones "*.R" on -X.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import bmesh
import bpy
from mathutils import Euler, Vector
from mathutils.geometry import intersect_point_line

from .editing import _make_active, _target_collection
from .mesh_edit import _refresh, select
from .undo import mutation, window_override
from .util import get_object, num, vec

MAX_BONES = 256
MIDLINE = 1e-4


def _armature(name: str) -> bpy.types.Object:
    obj = get_object(name)
    if obj.type != "ARMATURE":
        raise ValueError(f"{obj.name!r} is a {obj.type}, not an ARMATURE")
    return obj


@contextmanager
def _edit_bones(arm: bpy.types.Object) -> Iterator[Any]:
    """Edit mode on the armature for the duration, back to object mode after."""
    view_layer = bpy.context.view_layer
    previous = view_layer.objects.active
    view_layer.objects.active = arm
    override = {**window_override(), "active_object": arm, "object": arm}
    with bpy.context.temp_override(**override):
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            yield arm.data.edit_bones
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
    if previous is not None and previous.name in view_layer.objects:
        view_layer.objects.active = previous


def _vec(value: Any, what: str) -> Vector:
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise ValueError(f"{what} must be [x, y, z]")
    return Vector([float(v) for v in value])


def _validate_bones(bones: list[dict[str, Any]], existing: set[str] = frozenset()) -> None:
    if not bones:
        raise ValueError("no bones given")
    if len(bones) > MAX_BONES:
        raise ValueError(f"at most {MAX_BONES} bones")
    seen = set(existing)
    for b in bones:
        name = b.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("every bone needs a name")
        if name in seen:
            raise ValueError(f"duplicate bone name {name!r}")
        head, tail = _vec(b.get("head"), f"{name}.head"), _vec(b.get("tail"), f"{name}.tail")
        if (tail - head).length < 1e-5:
            raise ValueError(f"bone {name!r} has zero length")
        parent = b.get("parent")
        if parent and parent not in seen:
            raise ValueError(f"bone {name!r}: parent {parent!r} must be listed before it")
        seen.add(name)


def _add_bones(edit_bones: Any, bones: list[dict[str, Any]], origin: Vector) -> None:
    for b in bones:
        eb = edit_bones.new(b["name"])
        # Armature-local coordinates: the given points are world positions.
        eb.head = _vec(b["head"], "head") - origin
        eb.tail = _vec(b["tail"], "tail") - origin
        eb.roll = math.radians(float(b.get("roll", 0.0)))
        eb.use_deform = bool(b.get("deform", True))
        if b.get("parent"):
            eb.parent = edit_bones[b["parent"]]
            eb.use_connect = bool(b.get("connected", False)) and (
                (eb.parent.tail - eb.head).length < 1e-4
            )


def _new_armature(name: str, collection: str | None, origin: Vector) -> bpy.types.Object:
    data = bpy.data.armatures.new(name)
    data.display_type = "OCTAHEDRAL"
    obj = bpy.data.objects.new(name, data)
    obj.location = origin
    obj.show_in_front = True  # bones stay visible inside the mesh
    _target_collection(collection).objects.link(obj)
    return obj


def _bone_list(arm: bpy.types.Object) -> list[dict[str, Any]]:
    mw = arm.matrix_world
    return [
        {
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "head": vec(mw @ b.head_local),
            "tail": vec(mw @ b.tail_local),
            "length": num(b.length),
            "deform": b.use_deform,
        }
        for b in arm.data.bones
    ]


@mutation("create armature")
def create_armature(params: dict[str, Any]) -> dict[str, Any]:
    bones = params.get("bones") or []
    _validate_bones(bones)
    origin = Vector(params.get("location") or (0, 0, 0))
    arm = _new_armature(params.get("name") or "Armature", params.get("collection"), origin)
    with _edit_bones(arm) as edit_bones:
        _add_bones(edit_bones, bones, origin)
    _make_active(arm)
    return {"armature": arm.name, "bones": _bone_list(arm)}


# --- humanoid ------------------------------------------------------------------------------

# Default landmarks as fractions of height, for a character standing in A/T-pose facing -Y.
# Only the left (+X) side is listed; the right side is mirrored.
HUMANOID_DEFAULTS: dict[str, tuple[float, float, float]] = {
    "hips": (0.0, 0.0, 0.53),
    "chest": (0.0, 0.0, 0.70),
    "neck": (0.0, 0.0, 0.83),
    "head": (0.0, 0.0, 0.87),
    "head_top": (0.0, 0.0, 1.0),
    "shoulder": (0.10, 0.0, 0.81),
    "elbow": (0.25, 0.01, 0.70),
    "wrist": (0.37, 0.0, 0.60),
    "hand_tip": (0.44, 0.0, 0.55),
    "hip_joint": (0.06, 0.0, 0.50),
    "knee": (0.07, -0.01, 0.27),
    "ankle": (0.075, 0.01, 0.045),
    "ball": (0.075, -0.06, 0.01),
    "toe": (0.075, -0.11, 0.01),
}


def _landmarks(params: dict[str, Any]) -> dict[str, Vector]:
    height = float(params.get("height", 1.8))
    if height <= 0:
        raise ValueError("height must be > 0")
    given = params.get("landmarks") or {}
    unknown = set(given) - set(HUMANOID_DEFAULTS)
    if unknown:
        raise ValueError(
            f"unknown landmarks {sorted(unknown)}; known: {', '.join(HUMANOID_DEFAULTS)}"
        )
    points = {k: Vector(v) * height for k, v in HUMANOID_DEFAULTS.items()}
    for key, value in given.items():
        points[key] = _vec(value, f"landmark {key}")
    for side_key in ("shoulder", "elbow", "wrist", "hand_tip", "hip_joint", "knee", "ankle",
                     "ball", "toe"):  # fmt: skip
        if points[side_key].x <= 0:
            raise ValueError(f"landmark {side_key!r} is the character's left side: x must be > 0")
    return points


def _humanoid_bones(p: dict[str, Vector]) -> list[dict[str, Any]]:
    def mirror(v: Vector) -> Vector:
        return Vector((-v.x, v.y, v.z))

    spine = p["hips"].lerp(p["chest"], 0.5)
    bones = [
        {"name": "root", "head": [0, 0, 0], "tail": [0, 0.001 + p["hips"].z * 0.25, 0],
         "deform": False},
        {"name": "hips", "head": p["hips"], "tail": spine, "parent": "root"},
        {"name": "spine", "head": spine, "tail": p["chest"], "parent": "hips", "connected": True},
        {"name": "chest", "head": p["chest"], "tail": p["neck"], "parent": "spine",
         "connected": True},
        {"name": "neck", "head": p["neck"], "tail": p["head"], "parent": "chest",
         "connected": True},
        {"name": "head", "head": p["head"], "tail": p["head_top"], "parent": "neck",
         "connected": True},
    ]  # fmt: skip
    clavicle_start = p["chest"].lerp(p["neck"], 0.7)
    for suffix, f in ((".L", lambda v: v), (".R", mirror)):
        c_start = Vector((0.02 * (1 if suffix == ".L" else -1), clavicle_start.y, clavicle_start.z))
        bones += [
            {"name": f"shoulder{suffix}", "head": c_start, "tail": f(p["shoulder"]),
             "parent": "chest"},
            {"name": f"upper_arm{suffix}", "head": f(p["shoulder"]), "tail": f(p["elbow"]),
             "parent": f"shoulder{suffix}", "connected": True},
            {"name": f"forearm{suffix}", "head": f(p["elbow"]), "tail": f(p["wrist"]),
             "parent": f"upper_arm{suffix}", "connected": True},
            {"name": f"hand{suffix}", "head": f(p["wrist"]), "tail": f(p["hand_tip"]),
             "parent": f"forearm{suffix}", "connected": True},
            {"name": f"thigh{suffix}", "head": f(p["hip_joint"]), "tail": f(p["knee"]),
             "parent": "hips"},
            {"name": f"shin{suffix}", "head": f(p["knee"]), "tail": f(p["ankle"]),
             "parent": f"thigh{suffix}", "connected": True},
            {"name": f"foot{suffix}", "head": f(p["ankle"]), "tail": f(p["ball"]),
             "parent": f"shin{suffix}", "connected": True},
            {"name": f"toe{suffix}", "head": f(p["ball"]), "tail": f(p["toe"]),
             "parent": f"foot{suffix}", "connected": True},
        ]  # fmt: skip
    for b in bones:
        b["head"] = list(b["head"])
        b["tail"] = list(b["tail"])
    return bones


@mutation("create humanoid rig")
def create_humanoid_rig(params: dict[str, Any]) -> dict[str, Any]:
    points = _landmarks(params)
    bones = _humanoid_bones(points)
    extra = params.get("extra_bones") or []
    _validate_bones(bones + extra)
    arm = _new_armature(params.get("name") or "Rig", params.get("collection"), Vector())
    with _edit_bones(arm) as edit_bones:
        _add_bones(edit_bones, bones + extra, Vector())
        # Rolls chosen so +X rotation is the natural bend on both sides: spine/neck/head
        # bend forward, arms/hands fold forward, knees bend backward (thighs swing back;
        # negative X lifts a leg forward). Y twists along the bone, Z is sideways.
        for eb in edit_bones:
            if eb.name.startswith(("thigh", "shin")):
                eb.align_roll(Vector((0, 1, 0)))
            elif eb.name.startswith(("foot", "toe")):  # these point forward, not down
                eb.align_roll(Vector((0, 0, -1)))  # +X points the toes down
            elif eb.name in {b["name"] for b in bones}:
                eb.align_roll(Vector((0, -1, 0)))
    _make_active(arm)
    return {
        "armature": arm.name,
        "bone_count": len(arm.data.bones),
        "bones": _bone_list(arm),
        "landmarks": {k: vec(v) for k, v in points.items()},
    }


# --- binding and weights -------------------------------------------------------------------


def _deform_segments(arm: bpy.types.Object) -> list[tuple[str, Vector, Vector]]:
    mw = arm.matrix_world
    return [(b.name, mw @ b.head_local, mw @ b.tail_local) for b in arm.data.bones if b.use_deform]


def _segment_distance(p: Vector, a: Vector, b: Vector) -> float:
    closest, t = intersect_point_line(p, a, b)
    if t < 0:
        closest = a
    elif t > 1:
        closest = b
    return (p - closest).length


def _side_ok(bone: str, x: float) -> bool:
    """Keep left bones off the right half and vice versa (legs/arms close together)."""
    if bone.endswith(".L"):
        return x > -MIDLINE
    if bone.endswith(".R"):
        return x < MIDLINE
    return True


def _nearest_weights(
    mesh_obj: bpy.types.Object, arm: bpy.types.Object, only: set[int] | None = None
) -> int:
    """Weight each vertex to its nearest one or two deform bones (inverse-distance blend).
    Returns how many vertices were weighted."""
    segments = _deform_segments(arm)
    if not segments:
        raise ValueError(f"{arm.name!r} has no deform bones")
    groups = {
        name: mesh_obj.vertex_groups.get(name) or mesh_obj.vertex_groups.new(name=name)
        for name, _, _ in segments
    }
    mw = mesh_obj.matrix_world
    count = 0
    for v in mesh_obj.data.vertices:
        if only is not None and v.index not in only:
            continue
        p = mw @ v.co
        dists = sorted(
            (_segment_distance(p, a, b), name) for name, a, b in segments if _side_ok(name, p.x)
        )
        if not dists:
            continue
        best = dists[0][0]
        chosen = [(d, n) for d, n in dists[:2] if d <= best * 1.5 + 1e-6]
        inv = [(1.0 / max(d, 1e-4) ** 4, n) for d, n in chosen]
        total = sum(w for w, _ in inv)
        for w, n in inv:
            groups[n].add([v.index], w / total, "REPLACE")
        count += 1
    return count


def _unweighted(mesh_obj: bpy.types.Object, arm: bpy.types.Object) -> list[int]:
    deform = {b.name for b in arm.data.bones if b.use_deform}
    index_to_name = {g.index: g.name for g in mesh_obj.vertex_groups}
    return [
        v.index
        for v in mesh_obj.data.vertices
        if not any(index_to_name.get(g.group) in deform and g.weight > 1e-4 for g in v.groups)
    ]


def _attach(mesh_obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    world = mesh_obj.matrix_world.copy()
    mesh_obj.parent = arm
    mesh_obj.matrix_parent_inverse = arm.matrix_world.inverted()
    mesh_obj.matrix_world = world
    mod = next((m for m in mesh_obj.modifiers if m.type == "ARMATURE"), None)
    if mod is None:
        mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
        # Deform first, then smooth/mirror/etc.: SUBSURF after the Armature keeps a
        # subdivision cage rig light and correct.
        mesh_obj.modifiers.move(len(mesh_obj.modifiers) - 1, 0)
    mod.object = arm
    mod.use_vertex_groups = True


def limit_and_normalize(mesh_obj: bpy.types.Object, arm: bpy.types.Object, limit: int) -> int:
    """Keep each vertex's `limit` strongest bone weights and make them sum to 1 (what game
    engines expect). Returns how many vertices had influences dropped."""
    bones = {b.name for b in arm.data.bones}
    groups = {g.index: g for g in mesh_obj.vertex_groups if g.name in bones}
    trimmed = 0
    for v in mesh_obj.data.vertices:
        ws = sorted(
            ((g.weight, g.group) for g in v.groups if g.group in groups and g.weight > 0),
            reverse=True,
        )
        if not ws:
            continue
        keep, drop = ws[:limit], ws[limit:]
        trimmed += bool(drop)
        for _, gi in drop:
            groups[gi].remove([v.index])
        total = sum(w for w, _ in keep)
        for w, gi in keep:
            groups[gi].add([v.index], w / total, "REPLACE")
    return trimmed


@mutation("bind to armature")
def bind_to_armature(params: dict[str, Any]) -> dict[str, Any]:
    arm = _armature(params["armature"])
    names = params["meshes"] if isinstance(params["meshes"], list) else [params["meshes"]]
    meshes = [get_object(n) for n in names]
    bad = [m.name for m in meshes if m.type != "MESH"]
    if bad:
        raise ValueError(f"not meshes: {bad}")
    method = params.get("method", "automatic")
    if method not in {"automatic", "nearest"}:
        raise ValueError("method must be 'automatic' or 'nearest'")
    for pose_bone in arm.pose.bones:  # bind in rest pose
        pose_bone.location = (0, 0, 0)
        pose_bone.rotation_quaternion = (1, 0, 0, 0)
        pose_bone.rotation_euler = (0, 0, 0)
        pose_bone.scale = (1, 1, 1)

    results = []
    for mesh_obj in meshes:
        if mesh_obj.data.users > 1:
            raise ValueError(f"{mesh_obj.name!r} shares its mesh; make it single-user first")
        for group in [g for g in mesh_obj.vertex_groups if g.name in arm.data.bones]:
            mesh_obj.vertex_groups.remove(group)  # rebinding replaces old bone weights
        note = None
        if method == "automatic":
            view_layer = bpy.context.view_layer
            for o in view_layer.objects:
                o.select_set(False)
            mesh_obj.select_set(True)
            arm.select_set(True)
            view_layer.objects.active = arm
            override = {
                **window_override(),
                "active_object": arm,
                "object": arm,
                "selected_objects": [mesh_obj, arm],
                "selected_editable_objects": [mesh_obj, arm],
            }
            with bpy.context.temp_override(**override):
                bpy.ops.object.parent_set(type="ARMATURE_AUTO")
            missing = _unweighted(mesh_obj, arm)
            if missing:
                # Heat weighting fails on some shapes (loose parts, bad normals); fill gaps.
                _nearest_weights(mesh_obj, arm, only=set(missing))
                note = (
                    f"automatic weights missed {len(missing)} vertices; those got nearest-"
                    "bone weights"
                )
        else:
            _nearest_weights(mesh_obj, arm)
        _attach(mesh_obj, arm)
        limit = int(params.get("max_influences", 4))
        trimmed = limit_and_normalize(mesh_obj, arm, limit) if limit > 0 else 0
        info = _weight_summary(mesh_obj, arm)
        if trimmed:
            info["trimmed_to_max_influences"] = trimmed
        if note:
            info["note"] = note
        results.append(info)
    return {"armature": arm.name, "meshes": results}


def _weight_summary(mesh_obj: bpy.types.Object, arm: bpy.types.Object) -> dict[str, Any]:
    per_bone: dict[str, int] = {}
    index_to_name = {g.index: g.name for g in mesh_obj.vertex_groups}
    for v in mesh_obj.data.vertices:
        for g in v.groups:
            name = index_to_name.get(g.group)
            if name in arm.data.bones and g.weight > 1e-4:
                per_bone[name] = per_bone.get(name, 0) + 1
    unweighted = _unweighted(mesh_obj, arm)
    return {
        "mesh": mesh_obj.name,
        "vertices": len(mesh_obj.data.vertices),
        "unweighted_vertices": len(unweighted),
        "unweighted_sample": unweighted[:20],
        "vertices_per_bone": dict(sorted(per_bone.items())),
        "bones_without_vertices": sorted(
            b.name for b in arm.data.bones if b.use_deform and b.name not in per_bone
        ),
    }


@mutation("set vertex weights")
def set_vertex_weights(params: dict[str, Any]) -> dict[str, Any]:
    mesh_obj = get_object(params["mesh"])
    if mesh_obj.type != "MESH":
        raise ValueError(f"{mesh_obj.name!r} is not a mesh")
    group_name = params["group"]
    weight = float(params.get("weight", 1.0))
    mode = params.get("mode", "REPLACE").upper()
    if mode not in {"REPLACE", "ADD", "SUBTRACT"} or not 0 <= weight <= 1:
        raise ValueError("mode must be REPLACE/ADD/SUBTRACT and weight between 0 and 1")
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh_obj.data)
        _refresh(bm)
        verts = select(bm, mesh_obj, params["select"], params.get("type", "verts"))
        indices = sorted(
            {v.index for e in verts for v in (e.verts if hasattr(e, "verts") else [e])}
        )
    finally:
        bm.free()
    group = mesh_obj.vertex_groups.get(group_name) or mesh_obj.vertex_groups.new(name=group_name)
    group.add(indices, weight, mode)
    if params.get("normalize", True):
        _normalize(mesh_obj, set(indices))
    return {"mesh": mesh_obj.name, "group": group.name, "vertices": len(indices)}


def _normalize(mesh_obj: bpy.types.Object, indices: set[int]) -> None:
    arm_mod = next((m for m in mesh_obj.modifiers if m.type == "ARMATURE" and m.object), None)
    bones = set(arm_mod.object.data.bones.keys()) if arm_mod else None
    names = {g.index: g.name for g in mesh_obj.vertex_groups}
    for v in mesh_obj.data.vertices:
        if v.index not in indices:
            continue
        entries = [g for g in v.groups if bones is None or names[g.group] in bones]
        total = sum(g.weight for g in entries)
        if total > 1e-6:
            for g in entries:
                g.weight = g.weight / total


# --- posing --------------------------------------------------------------------------------


def _mirror_name(name: str) -> str | None:
    for a, b in ((".L", ".R"), (".R", ".L"), ("_L", "_R"), ("_R", "_L")):
        if name.endswith(a):
            return name[: -len(a)] + b
    return None


@mutation("pose bone")
def pose_bone(params: dict[str, Any]) -> dict[str, Any]:
    result = _pose_one(params, params["bone"], flip=False)
    if params.get("mirror"):
        other = _mirror_name(params["bone"])
        if other is None:
            raise ValueError(f"{params['bone']!r} has no .L/.R side to mirror")
        result["mirrored"] = _pose_one(params, other, flip=True)
    return result


def _pose_one(params: dict[str, Any], bone_name: str, flip: bool) -> dict[str, Any]:
    arm = _armature(params["armature"])
    bone = arm.pose.bones.get(bone_name)
    if bone is None:
        raise ValueError(f"{arm.name!r} has no bone {bone_name!r}; bones: "
                         f"{[b.name for b in arm.pose.bones][:40]}")  # fmt: skip
    bone.rotation_mode = "XYZ"
    if params.get("rotation") is not None:
        x, y, z = (math.radians(a) for a in params["rotation"])
        # Mirroring across the character's centre keeps X (the bend) and flips Y and Z.
        bone.rotation_euler = Euler((x, -y, -z) if flip else (x, y, z), "XYZ")
    if params.get("location") is not None:
        loc = _vec(params["location"], "location")
        bone.location = Vector((-loc.x, loc.y, loc.z)) if flip else loc
    if params.get("scale") is not None:
        s = params["scale"]
        bone.scale = (s, s, s) if isinstance(s, int | float) else _vec(s, "scale")
    frame = params.get("frame")
    if frame is not None:
        for path in ("rotation_euler", "location", "scale"):
            bone.keyframe_insert(path, frame=float(frame))
    bpy.context.view_layer.update()
    return {
        "armature": arm.name,
        "bone": bone.name,
        "rotation_deg": [num(math.degrees(a)) for a in bone.rotation_euler],
        "location": vec(bone.location),
        "tail_world": vec(arm.matrix_world @ bone.tail),
        "keyframed": frame is not None,
    }


@mutation("reset pose")
def reset_pose(params: dict[str, Any]) -> dict[str, Any]:
    arm = _armature(params["armature"])
    for bone in arm.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)
    return {"armature": arm.name, "bones_reset": len(arm.pose.bones)}


def get_armature_info(params: dict[str, Any]) -> dict[str, Any]:
    arm = _armature(params["armature"])
    bound = [
        o for o in bpy.data.objects
        if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
    ]  # fmt: skip
    posed = [
        b.name
        for b in arm.pose.bones
        if b.location.length > 1e-5
        or any(abs(a) > 1e-5 for a in b.rotation_euler)
        or abs(b.rotation_quaternion.angle) > 1e-5
    ]
    return {
        "armature": arm.name,
        "bones": _bone_list(arm),
        "posed_bones": posed,
        "bound_meshes": [_weight_summary(m, arm) for m in bound],
    }
