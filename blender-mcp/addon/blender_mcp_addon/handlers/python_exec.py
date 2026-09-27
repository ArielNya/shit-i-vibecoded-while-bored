"""The escape hatch: run agent-written Python inside Blender.

Off unless the user enables "Allow arbitrary Python" in the add-on preferences, and
refused without a token, because anyone who can reach the port (other accounts on a
shared machine included) would otherwise get code execution as this user.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import traceback
from typing import Any

import bmesh
import bpy
import mathutils

from . import settings
from .undo import mutation

MAX_CODE = 100_000
MAX_OUTPUT = 20_000
FILENAME = "<execute_python>"

_session: dict[str, Any] = {}


def _namespace(keep: bool) -> dict[str, Any]:
    base = {
        "__name__": "__mcp__",
        "bpy": bpy,
        "bmesh": bmesh,
        "mathutils": mathutils,
        "Vector": mathutils.Vector,
        "Matrix": mathutils.Matrix,
        "Euler": mathutils.Euler,
        "Quaternion": mathutils.Quaternion,
        "math": math,
        "C": bpy.context,
        "D": bpy.data,
    }
    if not keep:
        return base
    _session.update({k: v for k, v in base.items() if k not in _session})
    return _session


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n... [{len(text) - MAX_OUTPUT} more characters cut]"


def _jsonable(value: Any, depth: int = 0) -> Any:
    """Best-effort JSON form of `result`: containers recurse, Blender IDs become their
    names, vectors/matrices become lists, anything else its repr."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if depth > 8:
        return _clip(repr(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in list(value.items())[:1000]}
    if isinstance(value, bpy.types.ID):
        return value.name
    # Sequences, incl. mathutils types (which iterate via __getitem__, not __iter__).
    if hasattr(value, "__len__") and not isinstance(value, bytes | bytearray):
        try:
            return [_jsonable(v, depth + 1) for v in list(value)[:10_000]]
        except TypeError:
            pass
    return _clip(repr(value))


def _user_traceback(exc: BaseException) -> str:
    """Traceback limited to frames from the submitted code."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == FILENAME]
    lines = [f"  line {f.lineno}, in {f.name}" for f in frames]
    return "\n".join(["Traceback (submitted code):", *lines, f"{type(exc).__name__}: {exc}"])


class PythonError(Exception):
    pass


def _check_enabled() -> None:
    if not settings.allow_python:
        raise PermissionError(
            "execute_python is disabled. The user can enable it in Blender: Preferences > "
            "Add-ons > Blender MCP > 'Allow arbitrary Python' (a token is required too). "
            "Prefer the dedicated tools where they exist."
        )
    if not settings.token_set:
        raise PermissionError(
            "execute_python needs a token: set one in the add-on preferences and give the "
            "server the same value in BLENDER_MCP_TOKEN."
        )


def execute_python(params: dict[str, Any]) -> dict[str, Any]:
    _check_enabled()  # before the undo wrapper: a refused call changes nothing
    return _run(params)


@mutation("execute python")
def _run(params: dict[str, Any]) -> dict[str, Any]:
    code = params["code"]
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string")
    if len(code) > MAX_CODE:
        raise ValueError(f"code is longer than {MAX_CODE} characters")
    if params.get("reset_session"):
        _session.clear()
    namespace = _namespace(bool(params.get("keep_session", False)))
    namespace["result"] = None

    try:
        compiled = compile(code, FILENAME, "exec")
    except SyntaxError as exc:
        raise PythonError(f"SyntaxError: {exc.msg} (line {exc.lineno}): {exc.text!r}") from None

    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compiled, namespace)  # noqa: S102 - this is the feature, gated above
    except BaseException as exc:  # incl. SystemExit/KeyboardInterrupt from exit() etc.
        output = stdout.getvalue()
        detail = f"\n--- stdout before the error ---\n{_clip(output)}" if output else ""
        raise PythonError(_user_traceback(exc) + detail) from None

    result = _jsonable(namespace.get("result"))
    if len(json.dumps(result)) > MAX_OUTPUT * 5:
        result = _clip(repr(namespace.get("result")))
    return {
        "result": result,
        "stdout": _clip(stdout.getvalue()),
        "stderr": _clip(stderr.getvalue()),
    }
