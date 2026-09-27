"""Where file tools may read and write (PLAN §5).

Allowed: the configured workspace folder, plus the folder of the currently open
.blend file — except when that folder is the user's home or a filesystem root,
which would expose far too much. Paths are resolved with symlinks followed before
checking, and each tool restricts the file extensions it accepts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import bpy

DEFAULT_WORKSPACE = Path.home() / "BlenderMCP"

MODEL_SUFFIXES = {
    ".obj",
    ".fbx",
    ".glb",
    ".gltf",
    ".stl",
    ".ply",
    ".usd",
    ".usda",
    ".usdc",
    ".usdz",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".exr", ".hdr", ".tif", ".tiff", ".webp", ".bmp"}
BLEND_SUFFIXES = {".blend"}

_workspace: Path = DEFAULT_WORKSPACE


def configure(workspace: str | os.PathLike | None) -> None:
    global _workspace
    _workspace = Path(workspace).expanduser() if workspace else DEFAULT_WORKSPACE


def workspace() -> Path:
    return _workspace


def _real(path: Path) -> Path:
    return Path(os.path.realpath(path))


def _too_broad(folder: Path) -> bool:
    return folder == _real(Path.home()) or folder.parent == folder


def allowed_roots() -> list[Path]:
    roots = [_real(_workspace)]
    if bpy.data.filepath:
        blend_dir = _real(Path(bpy.data.filepath).parent)
        if not _too_broad(blend_dir) and blend_dir not in roots:
            roots.append(blend_dir)
    return roots


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def is_allowed(path: str | os.PathLike) -> bool:
    """Whether a path (after resolving symlinks) is inside an allowed folder."""
    real = _real(Path(path))
    return any(_inside(real, root) for root in allowed_roots())


def resolve(
    path: str,
    suffixes: set[str],
    *,
    must_exist: bool = False,
    overwrite: bool = True,
) -> Path:
    """Validate a user-supplied path and return its real absolute form.

    Relative paths are taken relative to the workspace folder.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    if "\0" in path:
        raise ValueError("path contains a NUL byte")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = _workspace / candidate
    real = _real(candidate)
    roots = allowed_roots()
    if not any(_inside(real, root) for root in roots):
        raise PermissionError(
            f"{path!r} is outside the folders this add-on may use: "
            f"{', '.join(str(r) for r in roots)}. Use a path inside one of them "
            "(relative paths go in the workspace folder)."
        )
    if real.suffix.lower() not in suffixes:
        raise ValueError(f"file type {real.suffix or '(none)'!r} not allowed here; use one of "
                         f"{', '.join(sorted(suffixes))}")  # fmt: skip
    if must_exist and not real.is_file():
        raise FileNotFoundError(f"no such file: {real}")
    if not overwrite and real.exists():
        raise FileExistsError(f"{real} already exists; pass overwrite=true to replace it")
    return real


def prepare_write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def list_files(params: dict[str, Any]) -> dict[str, Any]:
    """Files in an allowed folder (default: the workspace), for picking import sources."""
    sub = params.get("folder") or ""
    base = _real(_workspace / sub) if not Path(sub).is_absolute() else _real(Path(sub))
    roots = allowed_roots()
    if not any(_inside(base, root) for root in roots):
        raise PermissionError(f"{sub!r} is outside the allowed folders")
    known = MODEL_SUFFIXES | IMAGE_SUFFIXES | BLEND_SUFFIXES
    files, folders = [], []
    if base.is_dir():
        for entry in sorted(base.iterdir())[:500]:
            if entry.is_dir():
                folders.append(entry.name)
            elif entry.suffix.lower() in known:
                files.append({"name": entry.name, "bytes": entry.lstat().st_size})
    return {
        "folder": str(base),
        "exists": base.is_dir(),
        "allowed_roots": [str(r) for r in roots],
        "folders": folders,
        "files": files,
    }
