"""Keyframe animation: set/list/clear keyframes, frame range, current frame."""

from __future__ import annotations

import math
from typing import Any

import bpy

from .undo import mutation
from .util import get_object, num

TRANSFORMS = {"location", "rotation", "scale"}
INTERPOLATIONS = {"CONSTANT", "LINEAR", "BEZIER"}
MAX_KEYS_REPORTED = 200


def _fcurves(obj: bpy.types.Object) -> list[Any]:
    """F-curves of an object's action, for both classic and layered (4.4+) actions."""
    anim = obj.animation_data
    action = anim.action if anim else None
    if action is None:
        return []
    layers = getattr(action, "layers", None)
    if layers:  # layered actions: curves live in per-slot channelbags
        slot = getattr(anim, "action_slot", None)
        curves = []
        for layer in layers:
            for strip in layer.strips:
                bag = strip.channelbag(slot) if slot is not None else None
                if bag is not None:
                    curves.extend(bag.fcurves)
        return curves
    return list(action.fcurves)


def _data_path(prop: str) -> str:
    return "rotation_euler" if prop == "rotation" else prop


@mutation("set keyframe")
def set_keyframe(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    prop = params.get("property", "location")
    frame = float(params.get("frame", bpy.context.scene.frame_current))
    interpolation = params.get("interpolation")
    if interpolation is not None and interpolation.upper() not in INTERPOLATIONS:
        raise ValueError(f"interpolation must be one of {sorted(INTERPOLATIONS)}")

    if prop in TRANSFORMS:
        path = _data_path(prop)
        if "value" in params and params["value"] is not None:
            value = params["value"]
            if isinstance(value, int | float):
                value = [value] * 3
            if len(value) != 3:
                raise ValueError(f"{prop} value must be 3 numbers")
            if prop == "rotation":
                value = [math.radians(v) for v in value]
            setattr(obj, path, value)
    else:
        # Another animatable property of the object itself, e.g. "hide_render".
        path = prop
        if "." in path or "[" in path or not hasattr(obj, path):
            raise ValueError(
                f"{obj.name!r} has no object property {prop!r}; use location, rotation, "
                "scale or a top-level object property such as hide_render"
            )
        if "value" in params and params["value"] is not None:
            try:
                setattr(obj, path, params["value"])
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"can't set {prop!r}: {exc}") from None

    if not obj.keyframe_insert(path, frame=frame):
        raise ValueError(f"{prop!r} can't be keyframed")
    if interpolation:
        for curve in _fcurves(obj):
            if curve.data_path == path:
                for point in curve.keyframe_points:
                    if abs(point.co.x - frame) < 1e-3:
                        point.interpolation = interpolation.upper()
    return {"object": obj.name, "property": prop, "frame": frame, **_summary(obj)}


def _summary(obj: bpy.types.Object) -> dict[str, Any]:
    curves = _fcurves(obj)
    frames = sorted({num(p.co.x) for c in curves for p in c.keyframe_points})
    return {"keyframed_frames": frames[:MAX_KEYS_REPORTED], "curves": len(curves)}


def list_keyframes(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    channels = []
    for curve in _fcurves(obj):
        # Objects key "rotation_euler"; pose bones key 'pose.bones["x"].rotation_euler'.
        is_rotation = curve.data_path.endswith("rotation_euler")
        keys = [
            [
                num(p.co.x),
                num(math.degrees(p.co.y)) if is_rotation else num(p.co.y),
                p.interpolation,
            ]
            for p in list(curve.keyframe_points)[:MAX_KEYS_REPORTED]
        ]
        channels.append(
            {
                "property": "rotation" if curve.data_path == "rotation_euler" else curve.data_path,
                "index": curve.array_index,
                "keys": keys,  # [frame, value (rotation in degrees), interpolation]
            }
        )
    return {"object": obj.name, "channels": channels}


@mutation("clear animation")
def clear_animation(params: dict[str, Any]) -> dict[str, Any]:
    obj = get_object(params["object"])
    had = obj.animation_data is not None and obj.animation_data.action is not None
    obj.animation_data_clear()
    return {"object": obj.name, "cleared": had}


@mutation("set frame range")
def set_frame_range(params: dict[str, Any]) -> dict[str, Any]:
    scene = bpy.context.scene
    start = int(params.get("start", scene.frame_start))
    end = int(params.get("end", scene.frame_end))
    if end < start:
        raise ValueError("end must be >= start")
    scene.frame_start, scene.frame_end = start, end
    if "fps" in params and params["fps"] is not None:
        fps = int(params["fps"])
        if not 1 <= fps <= 240:
            raise ValueError("fps must be between 1 and 240")
        scene.render.fps = fps
        scene.render.fps_base = 1.0
    if "current" in params and params["current"] is not None:
        scene.frame_set(int(params["current"]))
    return {
        "start": scene.frame_start,
        "end": scene.frame_end,
        "current": scene.frame_current,
        "fps": scene.render.fps,
    }
