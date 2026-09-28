"""Undo integration: every mutating handler becomes one named undo step."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import bpy


def window_override() -> dict[str, Any]:
    """Context override with a window, which the undo and mode operators need."""
    window = bpy.context.window
    if window is None:
        windows = bpy.context.window_manager.windows
        window = windows[0] if windows else None
    return {"window": window} if window is not None else {}


def push(message: str) -> None:
    with bpy.context.temp_override(**window_override()):
        try:
            bpy.ops.ed.undo_push(message=message)
        except RuntimeError:
            pass  # undo unavailable (e.g. some headless setups); edits still happen


def ensure_object_mode() -> None:
    """Leave edit/sculpt/... mode so data-level edits aren't overwritten on mode exit."""
    if bpy.context.mode == "OBJECT" or bpy.context.view_layer.objects.active is None:
        return
    with bpy.context.temp_override(**window_override()):
        bpy.ops.object.mode_set(mode="OBJECT")


def mutation(label: str) -> Callable:
    """Decorator for handlers that change the scene."""

    def decorate(fn: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
        @functools.wraps(fn)
        def wrapper(params: dict[str, Any]) -> Any:
            ensure_object_mode()
            try:
                result = fn(params)
            except Exception:
                # Record whatever partial change happened so Ctrl+Z still reverts it.
                push(f"MCP: {label} (failed)")
                raise
            push(f"MCP: {label}")
            return result

        return wrapper

    return decorate


def step(params: dict[str, Any], redo: bool) -> dict[str, Any]:
    steps = params.get("steps", 1)
    if not 1 <= steps <= 50:
        raise ValueError("steps must be between 1 and 50")
    op = bpy.ops.ed.redo if redo else bpy.ops.ed.undo
    done = 0
    with bpy.context.temp_override(**window_override()):
        for _ in range(steps):
            if not op.poll() or op() != {"FINISHED"}:
                break
            done += 1
    objects = sorted(o.name for o in bpy.context.scene.objects)
    return {
        "steps_done": done,
        "note": None if done == steps else "reached the end of the undo history",
        "object_count": len(objects),
        "objects": objects[:50],
    }


def undo(params: dict[str, Any]) -> dict[str, Any]:
    return step(params, redo=False)


def redo(params: dict[str, Any]) -> dict[str, Any]:
    return step(params, redo=True)
