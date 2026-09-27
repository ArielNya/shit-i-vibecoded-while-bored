"""Viewport screenshots and quick renders, returned as base64 PNG."""

from __future__ import annotations

import base64
import math
import os
import tempfile
import time
from contextlib import ExitStack, contextmanager
from typing import Any

import bpy
from mathutils import Color, Euler, Matrix, Quaternion, Vector

from .util import get_object, world_bounds

MAX_SIZE = 2048
DEFAULT_SIZE = 768
PREVIEW_CAMERA = "_mcp_preview_camera"
MATHUTILS_TYPES = (Color, Euler, Matrix, Quaternion, Vector)

# Rotations (degrees, XYZ Euler) matching Blender's numpad views. Used for both the
# viewport and preview cameras, whose local +Z points back towards the viewer.
VIEW_ROTATIONS = {
    "front": (90, 0, 0),
    "back": (90, 0, 180),
    "right": (90, 0, 90),
    "left": (90, 0, -90),
    "top": (0, 0, 0),
    "bottom": (180, 0, 0),
    "iso": (60, 0, 45),
}
VIEWS = {*VIEW_ROTATIONS, "camera", "current"}
SHADING = {"SOLID", "WIREFRAME", "MATERIAL", "RENDERED"}
ENGINES = {
    "workbench": ("BLENDER_WORKBENCH",),
    "eevee": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),  # renamed back in Blender 5
    "cycles": ("CYCLES",),
}


@contextmanager
def _restoring(struct: Any, **values: Any):
    """Set attributes on an RNA struct, restoring the previous values on exit."""
    saved = {key: getattr(struct, key) for key in values}
    # mathutils values read from RNA are live views; copy them so restoring works.
    saved = {k: v.copy() if isinstance(v, MATHUTILS_TYPES) else v for k, v in saved.items()}
    try:
        for key, value in values.items():
            setattr(struct, key, value)
        yield
    finally:
        for key, value in saved.items():
            try:
                setattr(struct, key, value)
            except (ReferenceError, AttributeError, TypeError):
                pass


def _view_rotation(view: str) -> Euler:
    return Euler([math.radians(a) for a in VIEW_ROTATIONS[view]])


def _check_size(size: int) -> int:
    if not 16 <= size <= MAX_SIZE:
        raise ValueError(f"size must be between 16 and {MAX_SIZE}")
    return size


def _resolution(scene: bpy.types.Scene, size: int, aspect: float | None = None) -> tuple[int, int]:
    """Width/height with `size` as the long edge, keeping the given (or scene) aspect."""
    if aspect is None:
        aspect = scene.render.resolution_x / max(scene.render.resolution_y, 1)
    if aspect >= 1:
        return size, max(16, round(size / aspect))
    return max(16, round(size * aspect)), size


def _targets(scene: bpy.types.Scene, name: str | None) -> list[bpy.types.Object]:
    if name:
        obj = get_object(name)
        return [obj, *obj.children_recursive]
    return [obj for obj in scene.objects if obj.visible_get() and not obj.hide_render]


def _framing(objects: list[bpy.types.Object]) -> tuple[Vector, float]:
    bounds = world_bounds(objects)
    if bounds is None:
        return Vector((0, 0, 0)), 1.0
    lo, hi = bounds
    return (lo + hi) / 2, max((hi - lo).length / 2, 0.01)


def _png_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


@contextmanager
def _temp_png():
    fd, path = tempfile.mkstemp(prefix="blender_mcp_", suffix=".png")
    os.close(fd)
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@contextmanager
def _preview_camera(scene: bpy.types.Scene, view: str, target: str | None, aspect: float):
    """A temporary camera looking at the target from `view`, removed afterwards."""
    center, radius = _framing(_targets(scene, target))
    data = bpy.data.cameras.new(PREVIEW_CAMERA)
    cam = bpy.data.objects.new(PREVIEW_CAMERA, data)
    scene.collection.objects.link(cam)
    try:
        # sensor_fit AUTO: data.angle spans the longer image edge.
        narrow = 2 * math.atan(math.tan(data.angle / 2) * min(aspect, 1 / aspect))
        distance = radius / math.sin(narrow / 2) * 1.05
        rotation = _view_rotation(view)
        cam.rotation_euler = rotation
        cam.location = center + rotation.to_matrix() @ Vector((0, 0, distance))
        data.clip_start = max(0.001, (distance - radius) * 0.1)
        data.clip_end = distance + radius * 4
        with _restoring(scene, camera=cam):
            yield cam
    finally:
        bpy.data.objects.remove(cam)
        bpy.data.cameras.remove(data)


def _set_engine(scene: bpy.types.Scene, engine: str) -> str:
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {sorted(ENGINES)}")
    for identifier in ENGINES[engine]:
        try:
            scene.render.engine = identifier
            return identifier
        except TypeError:
            continue
    raise ValueError(f"render engine {engine!r} is not available in this Blender")


def _render(
    scene: bpy.types.Scene,
    engine: str,
    view: str,
    size: int,
    samples: int | None,
    target: str | None,
) -> dict[str, Any]:
    if view == "camera" and scene.camera is None:
        raise ValueError("The scene has no camera; use a view like 'iso' or 'front' instead")
    render = scene.render
    width, height = _resolution(scene, size)
    started = time.monotonic()
    with ExitStack() as stack:
        path = stack.enter_context(_temp_png())
        stack.enter_context(
            _restoring(
                render,
                engine=render.engine,
                resolution_x=width,
                resolution_y=height,
                resolution_percentage=100,
                filepath=path,
                use_file_extension=True,
            )
        )
        stack.enter_context(_restoring(render.image_settings, file_format="PNG", color_mode="RGBA"))
        engine_id = _set_engine(scene, engine)
        if engine_id == "CYCLES":
            stack.enter_context(_restoring(scene.cycles, samples=samples or 16))
        elif engine_id.startswith("BLENDER_EEVEE"):
            stack.enter_context(_restoring(scene.eevee, taa_render_samples=samples or 16))
        else:
            # Show material colors instead of flat grey.
            stack.enter_context(_restoring(scene.display.shading, color_type="MATERIAL"))
        if view != "camera":
            stack.enter_context(_preview_camera(scene, view, target, width / height))
        bpy.ops.render.render(write_still=True)
        image = _png_base64(path)
    return {
        "image_base64": image,
        "mime_type": "image/png",
        "width": width,
        "height": height,
        "engine": engine_id,
        "view": view,
        "seconds": round(time.monotonic() - started, 2),
    }


def _resolve_view(scene: bpy.types.Scene, view: str | None, default_current: bool) -> str:
    if view is None:
        view = "current" if default_current else ("camera" if scene.camera else "iso")
    if view not in VIEWS:
        raise ValueError(f"view must be one of {sorted(VIEWS)}")
    return view


def render_preview(params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    view = _resolve_view(scene, params.get("view"), default_current=False)
    if view == "current":
        view = "camera" if scene.camera else "iso"
    return _render(
        scene,
        engine=params.get("engine", "workbench"),
        view=view,
        size=_check_size(params.get("size", DEFAULT_SIZE)),
        samples=params.get("samples"),
        target=params.get("object"),
    )


def _find_view3d():
    best = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region and (
                best is None or area.width * area.height > best[1].width * best[1].height
            ):
                best = (window, area, region)
    return best


def get_viewport_screenshot(params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    size = _check_size(params.get("size", DEFAULT_SIZE))
    view = _resolve_view(scene, params.get("view"), default_current=True)
    shading = params.get("shading")
    if shading is not None and shading.upper() not in SHADING:
        raise ValueError(f"shading must be one of {sorted(SHADING)}")
    target = params.get("object")

    found = None if bpy.app.background else _find_view3d()
    if found is None:
        # No UI (e.g. blender --background): render the same framing with Workbench instead.
        fallback_view = "iso" if view == "current" else view
        result = _render(scene, "workbench", fallback_view, size, None, target)
        result["note"] = "No 3D viewport available (headless Blender); rendered with Workbench."
        return result

    window, area, region = found
    space = area.spaces.active
    rv3d = space.region_3d
    if view == "camera" and scene.camera is None:
        raise ValueError("The scene has no camera; use a view like 'iso' or 'front' instead")
    width, height = _resolution(scene, size, aspect=area.width / max(area.height, 1))
    shading_used = (shading or space.shading.type).upper()
    started = time.monotonic()

    with ExitStack() as stack:
        path = stack.enter_context(_temp_png())
        stack.enter_context(
            _restoring(
                rv3d,
                view_rotation=rv3d.view_rotation,
                view_location=rv3d.view_location,
                view_distance=rv3d.view_distance,
                view_perspective=rv3d.view_perspective,
            )
        )
        stack.enter_context(_restoring(space.shading, type=shading_used))
        stack.enter_context(
            _restoring(
                scene.render, resolution_x=width, resolution_y=height, resolution_percentage=100
            )
        )
        stack.enter_context(_restoring(scene.render.image_settings, file_format="PNG"))

        if view == "camera":
            rv3d.view_perspective = "CAMERA"
        elif view != "current":
            rv3d.view_rotation = _view_rotation(view).to_quaternion()
            rv3d.view_perspective = "PERSP" if view == "iso" else "ORTHO"
        if target or view not in {"current", "camera"}:
            center, radius = _framing(_targets(scene, target))
            fov = 2 * math.atan(36 / space.lens)  # viewport uses a 72mm sensor
            narrow = 2 * math.atan(math.tan(fov / 2) * min(width, height) / max(width, height))
            rv3d.view_location = center
            rv3d.view_distance = radius / math.sin(narrow / 2) * 1.1
        rv3d.update()

        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.render.opengl(write_still=False, view_context=True)
        bpy.data.images["Render Result"].save_render(path, scene=scene)
        image = _png_base64(path)

    return {
        "image_base64": image,
        "mime_type": "image/png",
        "width": width,
        "height": height,
        "view": view,
        "shading": shading_used,
        "seconds": round(time.monotonic() - started, 2),
    }
