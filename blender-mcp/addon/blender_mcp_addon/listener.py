"""Socket listener that hands requests to Blender's main thread.

No bpy imports here: the listener only does socket I/O on background threads and
submits handler calls through a MainThreadQueue, which Blender drains from a
bpy.app.timers callback (or a plain loop in --background mode).
"""

from __future__ import annotations

import hmac
import queue
import socket
import threading
import traceback
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from . import protocol

Handler = Callable[[dict[str, Any]], Any]


class MainThreadQueue:
    """Work submitted from any thread, executed when drain() is called on the main thread."""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[Callable[[], Any], Future]] = queue.Queue()

    def submit(self, fn: Callable[[], Any]) -> Future:
        future: Future = Future()
        self._queue.put((fn, future))
        return future

    def drain(self, max_items: int = 50) -> None:
        for _ in range(max_items):
            try:
                fn, future = self._queue.get_nowait()
            except queue.Empty:
                return
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn())
            except Exception as exc:
                future.set_exception(exc)


class Listener:
    def __init__(
        self,
        handlers: dict[str, Handler],
        main_thread: MainThreadQueue,
        host: str = protocol.DEFAULT_HOST,
        port: int = protocol.DEFAULT_PORT,
        token: str | None = None,
        server_info: dict[str, Any] | None = None,
    ) -> None:
        self.handlers = handlers
        self.main_thread = main_thread
        self.host = host
        self.port = port
        self.token = token or None
        self.server_info = server_info or {}
        self._sock: socket.socket | None = None
        self._clients: set[socket.socket] = set()
        self._clients_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def start(self) -> None:
        if self.running:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen()
        sock.settimeout(0.5)
        self.port = sock.getsockname()[1]  # resolves port 0 to the real port
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(target=self._accept_loop, name="blender-mcp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        with self._clients_lock:
            for conn in self._clients:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.close()
            self._clients.clear()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                return
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            conn.settimeout(None)
            with self._clients_lock:
                self._clients.add(conn)
            threading.Thread(
                target=self._serve_client, args=(conn,), name="blender-mcp-client", daemon=True
            ).start()

    def _serve_client(self, conn: socket.socket) -> None:
        state = {"authenticated": False}
        try:
            while not self._stop.is_set():
                try:
                    message = protocol.read_message(conn)
                except protocol.ProtocolError as exc:
                    reply = protocol.error(None, protocol.PARSE_ERROR, str(exc))
                    conn.sendall(protocol.encode(reply))
                    return
                if message is None:
                    return
                conn.sendall(protocol.encode(self._dispatch(message, state)))
        except OSError:
            pass
        finally:
            with self._clients_lock:
                self._clients.discard(conn)
            conn.close()

    def _dispatch(self, message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return protocol.error(msg_id, protocol.INVALID_REQUEST, "invalid request")

        if method == protocol.HANDSHAKE_METHOD:
            return self._handshake(msg_id, params, state)
        if not state["authenticated"]:
            return protocol.error(msg_id, protocol.UNAUTHORIZED, "handshake required")

        handler = self.handlers.get(method)
        if handler is None:
            return protocol.error(msg_id, protocol.METHOD_NOT_FOUND, f"unknown method '{method}'")
        try:
            value = self.main_thread.submit(lambda: handler(params)).result()
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
            return protocol.error(msg_id, protocol.HANDLER_ERROR, text, _traceback_tail(exc))
        return protocol.result(msg_id, value)

    def _handshake(self, msg_id: Any, params: dict[str, Any], state: dict[str, Any]) -> dict:
        client_version = params.get("protocol_version")
        if client_version != protocol.PROTOCOL_VERSION:
            return protocol.error(
                msg_id,
                protocol.VERSION_MISMATCH,
                f"protocol version mismatch: add-on speaks {protocol.PROTOCOL_VERSION}, "
                f"server speaks {client_version}. Update whichever is older.",
            )
        if self.token and not hmac.compare_digest(str(params.get("token") or ""), self.token):
            return protocol.error(msg_id, protocol.UNAUTHORIZED, "invalid token")
        state["authenticated"] = True
        return protocol.result(
            msg_id, {"protocol_version": protocol.PROTOCOL_VERSION, **self.server_info}
        )


def _traceback_tail(exc: BaseException, lines: int = 6) -> str:
    formatted = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return "".join(formatted[-lines:]).rstrip()
