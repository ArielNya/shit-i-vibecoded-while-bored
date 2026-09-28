"""Save/open .blend files and import/export models, restricted by paths.resolve()."""

from __future__ import annotations

import json
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote

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
    result: dict[str, Any] = {
        "opened": str(target),
        "objects": len(bpy.context.scene.objects),
        "scene": bpy.context.scene.name,
    }
    # A .blend may legitimately use textures/libraries from elsewhere, so they stay, but
    # say which ones live outside the allowed folders.
    outside = sorted({p for b in _file_backed() if (p := _outside_file(b)) is not None})
    if outside:
        result["external_files"] = outside[:50]
    return result


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


MTL_MAP_PREFIXES = ("map_", "bump", "disp", "decal", "refl", "norm")


def _referenced_files(target: Path) -> list[Path]:
    """Files a text-based model says it will load (.gltf buffers/images, .obj → .mtl →
    textures). Data URIs and web URLs are ignored; they aren't local files."""
    refs: list[Path] = []
    base = target.parent
    suffix = target.suffix.lower()
    if suffix in {".gltf", ".glb"}:
        try:
            doc = json.loads(_gltf_json(target))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{target.name} is not valid glTF: {exc}") from None
        for section in ("buffers", "images"):
            for item in doc.get(section) or []:
                uri = item.get("uri") if isinstance(item, dict) else None
                if isinstance(uri, str) and not uri.startswith(("data:", "http:", "https:")):
                    refs.append(base / unquote(uri))
    elif suffix == ".obj":
        for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("mtllib "):
                for name in line.split()[1:]:
                    mtl = base / name
                    refs.append(mtl)
                    if mtl.is_file() and paths.is_allowed(mtl):
                        refs += _mtl_textures(mtl)
    return refs


def _gltf_json(target: Path) -> str:
    """The JSON part of a .gltf, or of a binary .glb (its first chunk)."""
    if target.suffix.lower() == ".gltf":
        return target.read_text(encoding="utf-8")
    with open(target, "rb") as f:
        header = f.read(20)
        if len(header) < 20 or header[:4] != b"glTF":
            raise ValueError(f"{target.name} is not a binary glTF file")
        length, chunk_type = struct.unpack("<I4s", header[12:20])
        if chunk_type != b"JSON" or length > 64 * 1024 * 1024:
            raise ValueError(f"{target.name}: unexpected first chunk")
        return f.read(length).decode("utf-8")


def _mtl_textures(mtl: Path) -> list[Path]:
    refs = []
    for line in mtl.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].lower().startswith(MTL_MAP_PREFIXES):
            refs.append(mtl.parent / parts[-1])  # options come first, the file name last
    return refs


def _file_backed() -> list[Any]:
    """Datablocks that load their content from a file path."""
    data = bpy.data
    return [
        *data.images, *data.sounds, *data.movieclips, *data.fonts, *data.cache_files,
        *data.libraries,
    ]  # fmt: skip


def _outside_file(block: Any) -> str | None:
    """The absolute path a datablock reads from, if that's outside the allowed folders."""
    filepath = getattr(block, "filepath", "")
    if not filepath or getattr(block, "packed_file", None) is not None:
        return None
    if getattr(block, "source", "FILE") == "GENERATED":
        return None
    library = getattr(block, "library", None)
    absolute = Path(bpy.path.abspath(filepath, library=library))
    return None if paths.is_allowed(absolute) else str(absolute)


def _remove(block: Any) -> None:
    for collection in (
        bpy.data.images, bpy.data.sounds, bpy.data.movieclips, bpy.data.fonts,
        bpy.data.cache_files, bpy.data.libraries,
    ):  # fmt: skip
        if block in collection.values():
            collection.remove(block)
            return


@mutation("import")
def import_file(params: dict[str, Any]) -> dict[str, Any]:
    target = paths.resolve(params["path"], set(IMPORTERS), must_exist=True)
    outside = [str(p) for p in _referenced_files(target) if not paths.is_allowed(p)]
    if outside:
        raise PermissionError(
            f"{target.name} references files outside the allowed folders: {outside[:10]}. "
            "Copy them into the workspace next to the model first."
        )
    before_objects = set(bpy.data.objects)
    before_files = set(_file_backed())
    with _ops_context():
        IMPORTERS[target.suffix.lower()](str(target))
    # Binary formats (fbx, usd, ...) can't be pre-scanned: drop anything they loaded
    # from outside the allowed folders.
    removed = []
    for block in set(_file_backed()) - before_files:
        path = _outside_file(block)
        if path is not None:
            removed.append(path)
            _remove(block)
    new = sorted(o.name for o in set(bpy.data.objects) - before_objects)
    result: dict[str, Any] = {"imported": str(target), "objects": new, "count": len(new)}
    if removed:
        result["removed_external_files"] = sorted(removed)
        result["note"] = "Files outside the allowed folders were not loaded."
    return result


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
