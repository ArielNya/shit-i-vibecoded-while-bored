"""Add-on runtime state: the one listener and the main-thread queue it feeds."""

from __future__ import annotations

import bpy

from . import handlers, protocol
from .handlers import paths, settings
from .listener import Listener, MainThreadQueue

ADDON_VERSION = "0.1.0"
DRAIN_INTERVAL = 0.02

main_thread = MainThreadQueue()
_listener: Listener | None = None
last_error = ""


def start(
    host: str = protocol.DEFAULT_HOST,
    port: int = protocol.DEFAULT_PORT,
    token: str | None = None,
    workspace: str | None = None,
    allow_python: bool = False,
) -> Listener:
    global _listener, last_error
    stop()
    paths.configure(workspace)
    settings.allow_python = allow_python
    settings.token_set = bool(token)
    listener = Listener(
        handlers.HANDLERS,
        main_thread,
        host=host,
        port=port,
        token=token,
        server_info={
            "blender_version": bpy.app.version_string,
            "addon_version": ADDON_VERSION,
            "background": bpy.app.background,
            "workspace": str(paths.workspace()),
            "python_enabled": allow_python and bool(token),
        },
    )
    try:
        listener.start()
    except OSError as exc:
        last_error = f"Could not listen on {host}:{port}: {exc}"
        raise
    last_error = ""
    _listener = listener
    return listener


def stop() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def is_running() -> bool:
    return _listener is not None and _listener.running


def status() -> str:
    if not is_running():
        return "Stopped"
    assert _listener is not None
    clients = _listener.client_count
    plural = "" if clients == 1 else "s"
    return f"Listening on {_listener.host}:{_listener.port} ({clients} client{plural})"


def drain_timer() -> float:
    """bpy.app.timers callback: run queued requests on the main thread."""
    main_thread.drain()
    return DRAIN_INTERVAL
