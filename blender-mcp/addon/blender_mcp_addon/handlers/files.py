"""Save/open .blend files and import/export models, restricted by paths.resolve()."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import bpy

from . import paths
from .undo import mutation, window_override
from .util import get_object


def _ops_context() -> Any:
    return bpy.context.temp_override(**window_override())


def save_blend(params: dict[str, Any]) -> dict[str, Any]:
    path = params.get("path")
    if path is None:
        if not bpy.data.filepath:
            raise ValueError("the file has never been saved; give a path")
        target = Path(bpy.data.filepath)
    else:
        target = paths.resolve(
            path, paths.BLEND_SUFFIXES, overwrite=bool(params.get("overwrite", False))
        )
        paths.prepare_write(target)
    with _ops_context():
        bpy.ops.wm.save_as_mainfile(filepath=str(target), copy=bool(params.get("copy", False)))
    return {"saved": str(target), "is_dirty": bpy.data.is_dirty}


def open_blend(params: dict[str, Any]) -> dict[str, Any]:
    target = paths.resolve(params["path"], paths.BLEND_SUFFIXES, must_exist=True)
    if bpy.data.is_dirty and not params.get("discard_unsaved", False):
        raise ValueError(
            "the current file has unsaved changes; save_blend first, or pass "
            "discard_unsaved=true to lose them"
        )
    with _ops_context():
        # use_scripts=False: never auto-run Python embedded in a file the agent opens.
        bpy.ops.wm.open_mainfile(filepath=str(target), load_ui=False, use_scripts=False)
    return {
        "opened": str(target),
        "objects": len(bpy.context.scene.objects),
        "scene": bpy.context.scene.name,
    }


IMPORTERS = {
    ".obj": lambda p: bpy.ops.wm.obj_import(filepath=p),
    ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".stl": lambda p: bpy.ops.wm.stl_import(filepath=p),
    ".ply": lambda p: bpy.ops.wm.ply_import(filepath=p),
    ".usd": lambda p: bpy.ops.wm.usd_import(filepath=p),
    ".usda": lambda p: bpy.ops.wm.usd_import(filepath=p),
    ".usdc": lambda p: bpy.ops.wm.usd_import(filepath=p),
    ".usdz": lambda p: bpy.ops.wm.usd_import(filepath=p),
}


@mutation("import")
def import_file(params: dict[str, Any]) -> dict[str, Any]:
    target = paths.resolve(params["path"], set(IMPORTERS), must_exist=True)
    before = set(bpy.data.objects)
    with _ops_context():
        IMPORTERS[target.suffix.lower()](str(target))
    new = sorted(o.name for o in set(bpy.data.objects) - before)
    return {"imported": str(target), "objects": new, "count": len(new)}


def _exporter(suffix: str, path: str, apply_modifiers: bool) -> None:
    if suffix in {".glb", ".gltf"}:
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format="GLB" if suffix == ".glb" else "GLTF_SEPARATE",
            use_selection=True,
            export_apply=apply_modifiers,
        )
    elif suffix == ".fbx":
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, use_mesh_modifiers=apply_modifiers
        )
    elif suffix == ".obj":
        bpy.ops.wm.obj_export(
            filepath=path, export_selected_objects=True, apply_modifiers=apply_modifiers
        )
    elif suffix == ".stl":
        bpy.ops.wm.stl_export(
            filepath=path, export_selected_objects=True, apply_modifiers=apply_modifiers
        )
    elif suffix == ".ply":
        bpy.ops.wm.ply_export(
            filepath=path, export_selected_objects=True, apply_modifiers=apply_modifiers
        )
    else:  # usd family
        bpy.ops.wm.usd_export(filepath=path, selected_objects_only=True)


@contextmanager
def _selection(objects: list[bpy.types.Object]):
    """Temporarily select exactly `objects`, restoring the user's selection after."""
    view_layer = bpy.context.view_layer
    previous = [o for o in view_layer.objects if o.select_get()]
    active = view_layer.objects.active
    try:
        for o in previous:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
        if objects:
            view_layer.objects.active = objects[0]
        yield
    finally:
        for o in view_layer.objects:
            o.select_set(False)
        for o in previous:
            try:
                o.select_set(True)
            except (ReferenceError, RuntimeError):
                pass
        view_layer.objects.active = active


def export_file(params: dict[str, Any]) -> dict[str, Any]:
    suffixes = paths.MODEL_SUFFIXES
    target = paths.resolve(params["path"], suffixes, overwrite=bool(params.get("overwrite")))
    names = params.get("objects")
    if names:
        objects = [get_object(n) for n in names]
        if params.get("include_children", True):
            objects += [c for o in list(objects) for c in o.children_recursive]
    else:
        objects = [o for o in bpy.context.view_layer.objects if o.visible_get()]
    if not objects:
        raise ValueError("nothing to export")
    paths.prepare_write(target)
    with _selection(objects), _ops_context():
        _exporter(target.suffix.lower(), str(target), bool(params.get("apply_modifiers", True)))
    written = [p for p in target.parent.glob(f"{target.stem}*") if p.is_file()]
    return {
        "exported": str(target),
        "objects": sorted({o.name for o in objects}),
        "bytes": target.stat().st_size if target.exists() else 0,
        "files": sorted(p.name for p in written),
    }
