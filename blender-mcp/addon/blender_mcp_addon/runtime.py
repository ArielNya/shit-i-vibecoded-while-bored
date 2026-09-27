"""Add-on runtime state: the one listener and the main-thread queue it feeds."""

from __future__ import annotations

import bpy

from . import bl_info, handlers, protocol
from .handlers import paths, settings
from .listener import Listener, MainThreadQueue

ADDON_VERSION = ".".join(str(part) for part in bl_info["version"])
DRAIN_INTERVAL = 0.02

main_thread = MainThreadQueue()
_listener: Listener | None = None
last_error = ""
token_source = ""  # "preference", "token file", "argument" or "none", for the panel


def start(
    host: str = protocol.DEFAULT_HOST,
    port: int = protocol.DEFAULT_PORT,
    token: str | None = None,
    workspace: str | None = None,
    allow_python: bool = False,
    auth: bool = True,
) -> Listener:
    """Start listening. With auth (the default) and no explicit token, the shared token
    file is used, created if needed, so only this OS user's processes can connect."""
    global _listener, last_error, token_source
    stop()
    if token:
        token_source = "given"
    elif auth:
        try:
            token = protocol.ensure_token_file()
        except (protocol.TokenFileError, OSError) as exc:
            last_error = f"Token file problem: {exc}"
            raise OSError(last_error) from exc
        token_source = "token file"
    else:
        token_source = "none"
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
