"""Mesh-level editing with bmesh, driven by stateless selection specs.

Instead of relying on Blender's edit-mode selection, every tool takes a `select`
spec describing which elements to act on, e.g.

    {"normal": [0, 0, 1], "max_angle": 10}          faces pointing up
    {"position": {"axis": "z", "min": 0.9}}          elements above z = 0.9
    {"indices": [0, 4, 5]}                           explicit indices
    {"all": true}

Criteria combine with AND. Tools return the indices of what they created, which
stay valid until the next topology change, so steps can be chained.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import bmesh
import bpy
from bmesh.types import BMEdge, BMFace, BMVert
from mathutils import Euler, Matrix, Vector

from .undo import mutation
from .util import get_object, vec

KINDS = {"faces", "edges", "verts"}
SPEC_KEYS = {
    "all", "indices", "normal", "max_angle", "position", "material", "boundary",
    "sharp_angle", "space",
}  # fmt: skip
AXES = {"x": 0, "y": 1, "z": 2}
MAX_REPORTED = 500
MAX_CUTS = 100
MAX_CREATE = 200_000
MAX_RESULT_FACES = 2_000_000  # refuse edits that would hang Blender


# --- bmesh access --------------------------------------------------------------------------


def _mesh_object(name: str) -> bpy.types.Object:
    obj = get_object(name)
    if obj.type != "MESH":
        raise ValueError(f"{obj.name!r} is a {obj.type}, not a MESH")
    return obj


@contextmanager
def _edit(obj: bpy.types.Object) -> Iterator[bmesh.types.BMesh]:
    """A bmesh of obj's mesh, written back if the block completes without error."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        _refresh(bm)
        yield bm
        bm.normal_update()
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def _refresh(bm: bmesh.types.BMesh) -> None:
    for seq in (bm.verts, bm.edges, bm.faces):
        seq.ensure_lookup_table()
        seq.index_update()


def _elements(bm: bmesh.types.BMesh, kind: str):
    return {"faces": bm.faces, "edges": bm.edges, "verts": bm.verts}[kind]


# --- selection specs -----------------------------------------------------------------------


def _center(elem) -> Vector:
    if isinstance(elem, BMFace):
        return elem.calc_center_median()
    if isinstance(elem, BMEdge):
        return (elem.verts[0].co + elem.verts[1].co) / 2
    return elem.co.copy()


def _normal(elem) -> Vector | None:
    if isinstance(elem, BMEdge):
        normals = [f.normal for f in elem.link_faces]
        if not normals:
            return None
        return sum(normals, Vector()).normalized()
    return elem.normal.copy()


def _is_boundary(elem) -> bool:
    if isinstance(elem, BMFace):
        return any(e.is_boundary for e in elem.edges)
    return elem.is_boundary


def _position_filters(value: Any) -> list[dict[str, Any]]:
    filters = value if isinstance(value, list) else [value]
    for f in filters:
        if not isinstance(f, dict) or f.get("axis") not in AXES:
            raise ValueError("position needs {'axis': 'x'|'y'|'z', 'min': .., 'max': ..}")
        if f.get("min") is None and f.get("max") is None:
            raise ValueError("position needs at least one of min / max")
    return filters


def select(bm: bmesh.types.BMesh, obj: bpy.types.Object, spec: Any, kind: str) -> list:
    if kind not in KINDS:
        raise ValueError(f"element type must be one of {sorted(KINDS)}")
    if not isinstance(spec, dict) or not spec:
        raise ValueError(
            "select must be a non-empty object, e.g. {'all': true}, {'indices': [..]}, "
            "{'normal': [0,0,1]}, {'position': {'axis': 'z', 'min': 0.5}}"
        )
    unknown = set(spec) - SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown select keys {sorted(unknown)}; valid: {sorted(SPEC_KEYS)}")
    space = spec.get("space", "local")
    if space not in {"local", "world"}:
        raise ValueError("space must be 'local' or 'world'")
    world = space == "world"
    matrix = obj.matrix_world
    normal_matrix = matrix.to_3x3().inverted_safe().transposed()

    elems = list(_elements(bm, kind))
    if "indices" in spec:
        indices = spec["indices"]
        bad = [i for i in indices if not isinstance(i, int) or not 0 <= i < len(elems)]
        if bad:
            raise ValueError(f"{kind} indices out of range 0..{len(elems) - 1}: {bad[:10]}")
        wanted = set(indices)
        elems = [e for e in elems if e.index in wanted]

    if "normal" in spec:
        target = Vector(spec["normal"])
        if target.length == 0:
            raise ValueError("normal must not be zero")
        target.normalize()
        limit = math.radians(float(spec.get("max_angle", 30)))
        kept = []
        for e in elems:
            n = _normal(e)
            if n is None or n.length == 0:
                continue
            if world:
                n = (normal_matrix @ n).normalized()
            if n.angle(target, math.pi) <= limit:
                kept.append(e)
        elems = kept

    if "position" in spec:
        for f in _position_filters(spec["position"]):
            axis, lo, hi = AXES[f["axis"]], f.get("min"), f.get("max")
            kept = []
            for e in elems:
                c = _center(e)
                value = (matrix @ c)[axis] if world else c[axis]
                if (lo is None or value >= lo - 1e-6) and (hi is None or value <= hi + 1e-6):
                    kept.append(e)
            elems = kept

    if "material" in spec:
        if kind != "faces":
            raise ValueError("material filtering works on faces")
        mat = spec["material"]
        if isinstance(mat, str):
            names = [m.name if m else None for m in obj.data.materials]
            if mat not in names:
                raise ValueError(f"{obj.name!r} has no material slot {mat!r}; slots: {names}")
            mat = names.index(mat)
        elems = [e for e in elems if e.material_index == mat]

    if "boundary" in spec:
        want = bool(spec["boundary"])
        elems = [e for e in elems if _is_boundary(e) == want]

    if "sharp_angle" in spec:
        if kind != "edges":
            raise ValueError("sharp_angle filtering works on edges")
        limit = math.radians(float(spec["sharp_angle"]))
        elems = [e for e in elems if len(e.link_faces) == 2 and e.calc_face_angle(0) >= limit]

    if not elems:
        raise ValueError(f"the selection matched no {kind}")
    return elems


def _report(elems: list, key: str = "indices") -> dict:
    elems = [e for e in elems if e.is_valid]
    out: dict[str, Any] = {key: [e.index for e in elems[:MAX_REPORTED]], "count": len(elems)}
    if len(elems) > MAX_REPORTED:
        out["truncated"] = True
    return out


def _stats(obj: bpy.types.Object) -> dict[str, int]:
    mesh = obj.data
    return {"vertices": len(mesh.vertices), "edges": len(mesh.edges), "faces": len(mesh.polygons)}


def select_elements(params: dict[str, Any]) -> dict[str, Any]:
    """Preview a selection spec: which indices match (and where, for small results)."""
    obj = _mesh_object(params["name"])
    kind = params.get("type", "faces")
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        _refresh(bm)
        elems = select(bm, obj, params["select"], kind)
        out = {"type": kind, **_report(elems)}
        if len(elems) <= 50:
            out["centers"] = [vec(_center(e)) for e in elems]
            if kind == "faces":
                out["normals"] = [vec(e.normal) for e in elems]
        return out
    finally:
        bm.free()


# --- operations ----------------------------------------------------------------------------


def _index_after(bm: bmesh.types.BMesh, elems: list) -> list:
    _refresh(bm)
    return [e for e in elems if e.is_valid]


@mutation("extrude")
def extrude(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    distance = float(params.get("distance", 1.0))
    individual = params.get("mode", "region") == "individual"
    with _edit(obj) as bm:
        faces = select(bm, obj, params["select"], "faces")
        if individual:
            new_faces = bmesh.ops.extrude_discrete_faces(bm, faces=faces)["faces"]
            for face in new_faces:
                bmesh.ops.translate(bm, vec=face.normal * distance, verts=list(face.verts))
        else:
            direction = params.get("direction")
            if direction is not None:
                offset = Vector(direction).normalized() * distance
            else:
                avg = sum((f.normal for f in faces), Vector())
                if avg.length == 0:
                    raise ValueError("selected faces' normals cancel out; give a direction")
                offset = avg.normalized() * distance
            geom = bmesh.ops.extrude_face_region(bm, geom=faces)["geom"]
            # The original faces stay behind as internal faces; Blender's extrude removes them.
            bmesh.ops.delete(bm, geom=faces, context="FACES_ONLY")
            new_verts = [g for g in geom if isinstance(g, BMVert)]
            moved = set(new_verts)
            # Report the cap (faces made only of new verts), not the new side walls.
            new_faces = [g for g in geom if isinstance(g, BMFace) and set(g.verts) <= moved]
            bmesh.ops.translate(bm, vec=offset, verts=new_verts)
        new_faces = _index_after(bm, new_faces)
        result = _report(new_faces, key="new_faces")
    return {"name": obj.name, **result, **_stats(obj)}


@mutation("inset")
def inset(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    thickness = float(params.get("thickness", 0.1))
    depth = float(params.get("depth", 0.0))
    with _edit(obj) as bm:
        faces = select(bm, obj, params["select"], "faces")
        if params.get("individual"):
            bmesh.ops.inset_individual(
                bm, faces=faces, thickness=thickness, depth=depth, use_even_offset=True
            )
        else:
            bmesh.ops.inset_region(
                bm, faces=faces, thickness=thickness, depth=depth, use_even_offset=True
            )
        inner = _index_after(bm, faces)  # the original faces become the inner ones
        result = _report(inner, key="inner_faces")
    return {"name": obj.name, **result, **_stats(obj)}


def _edges_for(bm, obj, spec, kind) -> list[BMEdge]:
    """Edges from a spec that may target faces or edges."""
    elems = select(bm, obj, spec, kind)
    if kind == "edges":
        return elems
    if kind == "faces":
        return list({e for f in elems for e in f.edges})
    return list({e for v in elems for e in v.link_edges})


@mutation("bevel")
def bevel(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    segments = int(params.get("segments", 1))
    if not 1 <= segments <= MAX_CUTS:
        raise ValueError(f"segments must be between 1 and {MAX_CUTS}")
    with _edit(obj) as bm:
        edges = _edges_for(bm, obj, params["select"], params.get("type", "edges"))
        verts = list({v for e in edges for v in e.verts})
        result = bmesh.ops.bevel(
            bm,
            geom=edges + verts,
            offset=float(params.get("width", 0.1)),
            offset_type="OFFSET",
            segments=segments,
            profile=float(params.get("profile", 0.5)),
            affect="EDGES",
            clamp_overlap=True,
        )
        new_faces = _index_after(bm, result["faces"])
        report = _report(new_faces, key="new_faces")
    return {"name": obj.name, **report, **_stats(obj)}


@mutation("subdivide")
def subdivide(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    cuts = int(params.get("cuts", 1))
    if not 1 <= cuts <= MAX_CUTS:
        raise ValueError(f"cuts must be between 1 and {MAX_CUTS}")
    with _edit(obj) as bm:
        edges = _edges_for(
            bm, obj, params.get("select") or {"all": True}, params.get("type", "faces")
        )
        touched = {f for e in edges for f in e.link_faces}
        estimate = len(bm.faces) + len(touched) * ((cuts + 1) ** 2 - 1)
        if estimate > MAX_RESULT_FACES:
            raise ValueError(
                f"that would make ~{estimate:,} faces (limit {MAX_RESULT_FACES:,}); "
                "use fewer cuts or a smaller selection"
            )
        bmesh.ops.subdivide_edges(
            bm, edges=edges, cuts=cuts, use_grid_fill=True,
            smooth=float(params.get("smooth", 0.0)),
        )  # fmt: skip
    return {"name": obj.name, **_stats(obj)}


def _edge_ring(start: BMEdge) -> list[BMEdge]:
    """Edges across a strip of quads, like Blender's loop cut uses."""
    ring = [start]
    seen = {start}
    for face in list(start.link_faces):
        edge = start
        while face is not None and len(face.verts) == 4:
            loop = next(lp for lp in face.loops if lp.edge == edge)
            opposite = loop.link_loop_next.link_loop_next.edge
            if opposite in seen:
                break
            seen.add(opposite)
            ring.append(opposite)
            others = [f for f in opposite.link_faces if f != face]
            face, edge = (others[0] if others else None), opposite
    return ring


@mutation("loop cut")
def loop_cut(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    cuts = int(params.get("cuts", 1))
    if not 1 <= cuts <= MAX_CUTS:
        raise ValueError(f"cuts must be between 1 and {MAX_CUTS}")
    with _edit(obj) as bm:
        start = select(bm, obj, params["select"], "edges")[0]
        ring = _edge_ring(start)
        if len(ring) < 2:
            raise ValueError("that edge isn't part of a strip of quads; nothing to cut")
        bmesh.ops.subdivide_edges(bm, edges=ring, cuts=cuts, use_grid_fill=True)
    return {"name": obj.name, "ring_edges": len(ring), **_stats(obj)}


@mutation("bisect")
def bisect(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    point = Vector(params.get("point", (0, 0, 0)))
    normal = Vector(params.get("normal", (0, 0, 1)))
    if normal.length == 0:
        raise ValueError("normal must not be zero")
    if params.get("space", "local") == "world":
        inverse = obj.matrix_world.inverted_safe()
        point = inverse @ point
        normal = (obj.matrix_world.to_3x3().transposed() @ normal).normalized()
    keep = params.get("keep", "both")
    if keep not in {"both", "above", "below"}:
        raise ValueError("keep must be 'both', 'above' or 'below'")
    with _edit(obj) as bm:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        result = bmesh.ops.bisect_plane(
            bm, geom=geom, plane_co=point, plane_no=normal, dist=1e-5,
            clear_inner=keep == "above", clear_outer=keep == "below",
        )  # fmt: skip
        cut_edges = [g for g in result["geom_cut"] if isinstance(g, BMEdge)]
        filled = 0
        if params.get("fill") and keep != "both" and cut_edges:
            filled = len(bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)["faces"])
    return {"name": obj.name, "cut_edges": len(cut_edges), "filled_faces": filled, **_stats(obj)}


DELETE_CONTEXTS = {
    "verts": "VERTS", "edges": "EDGES", "faces": "FACES", "only_faces": "FACES_ONLY",
}  # fmt: skip


@mutation("delete elements")
def delete_elements(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    kind = params.get("type", "faces")
    if kind not in DELETE_CONTEXTS:
        raise ValueError(f"type must be one of {sorted(DELETE_CONTEXTS)}")
    with _edit(obj) as bm:
        elems = select(bm, obj, params["select"], "faces" if kind == "only_faces" else kind)
        count = len(elems)
        bmesh.ops.delete(bm, geom=elems, context=DELETE_CONTEXTS[kind])
    return {"name": obj.name, "deleted": count, **_stats(obj)}


@mutation("merge by distance")
def merge_by_distance(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    with _edit(obj) as bm:
        before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=float(params.get("distance", 1e-4)))
        removed = before - len(bm.verts)
    return {"name": obj.name, "removed_vertices": removed, **_stats(obj)}


@mutation("recalculate normals")
def recalc_normals(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    with _edit(obj) as bm:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        if params.get("inside"):
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    return {"name": obj.name, **_stats(obj)}


@mutation("shade")
def shade(params: dict[str, Any]) -> dict[str, Any]:
    obj = _mesh_object(params["name"])
    mesh = obj.data
    if params.get("smooth", True):
        mesh.shade_smooth()
        angle = params.get("auto_smooth_angle")
        if angle is not None:
            # Keep edges sharper than this angle hard (Blender 4.1+ "smooth by angle").
            mesh.set_sharp_from_angle(angle=math.radians(float(angle)))
    else:
        mesh.shade_flat()
    return {"name": obj.name, "smooth": bool(params.get("smooth", True))}


def _pivot(verts: list[BMVert], pivot: Any) -> Vector:
    if pivot in (None, "median"):
        return sum((v.co for v in verts), Vector()) / len(verts)
    if pivot == "bounds_center":
        lo = Vector(tuple(min(v.co[i] for v in verts) for i in range(3)))
        hi = Vector(tuple(max(v.co[i] for v in verts) for i in range(3)))
        return (lo + hi) / 2
    if pivot == "origin":
        return Vector()
    if isinstance(pivot, list | tuple) and len(pivot) == 3:
        return Vector(pivot)
    raise ValueError("pivot must be 'median', 'bounds_center', 'origin' or [x, y, z]")


@mutation("transform elements")
def transform_elements(params: dict[str, Any]) -> dict[str, Any]:
    """Move/rotate/scale selected vertices (e.g. taper a shape, raise a face)."""
    obj = _mesh_object(params["name"])
    with _edit(obj) as bm:
        elems = select(bm, obj, params["select"], params.get("type", "faces"))
        verts = list({v for e in elems for v in (e.verts if not isinstance(e, BMVert) else [e])})
        center = _pivot(verts, params.get("pivot"))
        matrix = Matrix.Identity(4)
        if "scale" in params:
            s = params["scale"]
            s = (s, s, s) if isinstance(s, int | float) else s
            matrix = Matrix.Diagonal((*s, 1)) @ matrix
        if "rotation" in params:
            rot = Euler([math.radians(a) for a in params["rotation"]]).to_matrix().to_4x4()
            matrix = rot @ matrix
        about = Matrix.Translation(center) @ matrix @ Matrix.Translation(-center)
        if "translate" in params:
            about = Matrix.Translation(Vector(params["translate"])) @ about
        bmesh.ops.transform(bm, matrix=about, verts=verts)
        # Absolute fitting (what reference-based modelling needs): make the selection's
        # bounding box this size and/or put its centre here; null keeps an axis as is.
        if params.get("size") is not None or params.get("center") is not None:
            lo, hi = _bounds(verts)
            box_center = (lo + hi) / 2
            factors = [1.0, 1.0, 1.0]
            for axis, want in enumerate(params.get("size") or [None] * 3):
                extent = hi[axis] - lo[axis]
                if want is not None:
                    if extent < 1e-6:
                        raise ValueError(f"selection is flat along {'xyz'[axis]}; can't size it")
                    factors[axis] = float(want) / extent
            shift = Vector((0.0, 0.0, 0.0))
            for axis, want in enumerate(params.get("center") or [None] * 3):
                if want is not None:
                    shift[axis] = float(want) - box_center[axis]
            fit = (
                Matrix.Translation(box_center + shift)
                @ Matrix.Diagonal((*factors, 1))
                @ Matrix.Translation(-box_center)
            )
            bmesh.ops.transform(bm, matrix=fit, verts=verts)
        lo, hi = _bounds(verts)
    return {
        "name": obj.name,
        "moved_vertices": len(verts),
        "pivot": vec(center),
        "bounds": {"min": vec(lo), "max": vec(hi), "size": vec(hi - lo)},
    }


def _bounds(verts: list[BMVert]) -> tuple[Vector, Vector]:
    lo = Vector(tuple(min(v.co[i] for v in verts) for i in range(3)))
    hi = Vector(tuple(max(v.co[i] for v in verts) for i in range(3)))
    return lo, hi


@mutation("create mesh")
def create_mesh_from_data(params: dict[str, Any]) -> dict[str, Any]:
    from .editing import _make_active, _target_collection, _vec3
    from .objects import _summary

    verts = params["vertices"]
    faces = params.get("faces") or []
    edges = params.get("edges") or []
    if not verts or len(verts) > MAX_CREATE:
        raise ValueError(f"vertices must have between 1 and {MAX_CREATE} entries")
    if any(not isinstance(v, list | tuple) or len(v) != 3 for v in verts):
        raise ValueError("each vertex must be [x, y, z]")
    n = len(verts)
    for group, size in ((faces, 3), (edges, 2)):
        for item in group:
            if len(item) < size or any(not isinstance(i, int) or not 0 <= i < n for i in item):
                raise ValueError(f"bad index list {item!r} (vertex indices are 0..{n - 1})")
            if len(set(item)) != len(item):
                raise ValueError(f"index list {item!r} repeats a vertex")
    name = params.get("name") or "Mesh"
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(
        [tuple(v) for v in verts], [tuple(e) for e in edges], [tuple(f) for f in faces]
    )
    invalid = mesh.validate(clean_customdata=False)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = _vec3(params.get("location", 0), "location")
    _target_collection(params.get("collection")).objects.link(obj)
    _make_active(obj)
    return {**_summary(obj), **_stats(obj), "repaired": bool(invalid)}
