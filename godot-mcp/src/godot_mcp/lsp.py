"""Minimal client for the GDScript language server built into the Godot editor.

Used for diagnostics (parse/type errors and warnings, exactly what the script editor
shows) and native class documentation (`textDocument/nativeSymbol`). The editor serves
it on 127.0.0.1:6005 by default; the plugin reports the actual host/port at handshake.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, unquote, urlparse


class LSPError(Exception):
    """The language server is unreachable or answered with an error."""


def path_to_uri(path: str) -> str:
    """Absolute file path (as Godot reports it, forward slashes) -> file:// URI."""
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p  # Windows drive paths: C:/x -> /C:/x
    return "file://" + quote(p, safe="/:")


def uri_to_path(uri: str) -> str:
    p = unquote(urlparse(uri).path)
    if len(p) > 2 and p[0] == "/" and p[2] == ":":
        p = p[1:]
    return p


class GDScriptLSP:
    """One connection to the language server; created lazily, reconnects after a drop."""

    def __init__(self, host: str, port: int, project_path: str):
        self.host = host
        self.port = port
        self.project_path = project_path.rstrip("/")
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._diag_waiters: dict[str, asyncio.Future] = {}
        self._open_versions: dict[str, int] = {}
        self._connect_lock = asyncio.Lock()
        self._diag_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    # --- public API ----------------------------------------------------------------------

    def res_to_uri(self, res_path: str) -> str:
        rel = res_path.removeprefix("res://")
        return path_to_uri(str(PurePosixPath(self.project_path) / rel))

    def uri_to_res(self, uri: str) -> str:
        path = uri_to_path(uri)
        root = uri_to_path(path_to_uri(self.project_path))
        if path.startswith(root + "/"):
            return "res://" + path[len(root) + 1 :]
        return path

    async def diagnostics(self, res_path: str, text: str, timeout: float = 10.0) -> list[dict]:
        """Send the file's text to the server and return the diagnostics it publishes."""
        await self._ensure_connected()
        uri = self.res_to_uri(res_path)
        async with self._diag_lock:
            waiter: asyncio.Future = asyncio.get_running_loop().create_future()
            self._diag_waiters[uri] = waiter
            try:
                if uri in self._open_versions:
                    # Re-open rather than didChange: the server re-analyses on open, and a
                    # fresh open can't be confused with an older publish.
                    await self._notify("textDocument/didClose", {"textDocument": {"uri": uri}})
                version = self._open_versions.get(uri, 0) + 1
                self._open_versions[uri] = version
                await self._notify(
                    "textDocument/didOpen",
                    {
                        "textDocument": {
                            "uri": uri,
                            "languageId": "gdscript",
                            "version": version,
                            "text": text,
                        }
                    },
                )
                return await asyncio.wait_for(waiter, timeout)
            except TimeoutError:
                raise LSPError(
                    f"The GDScript language server sent no diagnostics for {res_path} "
                    f"within {timeout}s."
                ) from None
            finally:
                self._diag_waiters.pop(uri, None)

    async def native_symbol(self, class_name: str, symbol: str = "") -> dict | None:
        """Docs for a native class (symbol="") or one of its members; None if unknown."""
        await self._ensure_connected()
        result = await self._request(
            "textDocument/nativeSymbol",
            {"native_class": class_name, "symbol_name": symbol or class_name},
            timeout=10.0,
        )
        return result or None

    async def close(self) -> None:
        task, self._reader_task = self._reader_task, None
        writer, self._writer, self._reader = self._writer, None, None
        self._open_versions.clear()
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if writer is not None:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
        for fut in [*self._pending.values(), *self._diag_waiters.values()]:
            if not fut.done():
                fut.set_exception(LSPError("connection to the GDScript language server closed"))
        self._pending.clear()

    # --- plumbing ------------------------------------------------------------------------

    async def _ensure_connected(self) -> None:
        async with self._connect_lock:
            if self.connected and self._reader_task is not None and not self._reader_task.done():
                return
            await self.close()
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), 5.0
                )
            except (OSError, TimeoutError) as exc:
                raise LSPError(
                    f"Could not reach Godot's GDScript language server at {self.host}:"
                    f"{self.port}. It runs inside the editor (Editor Settings > Network > "
                    "Language Server); set GODOT_MCP_LSP_PORT if you changed its port."
                ) from exc
            self._reader_task = asyncio.create_task(self._read_loop())
            root = path_to_uri(self.project_path)
            await self._request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": root,
                    "rootPath": self.project_path,
                    "capabilities": {},
                    "clientInfo": {"name": "godot-mcp"},
                },
                timeout=10.0,
            )
            await self._notify("initialized", {})

    async def _send(self, message: dict[str, Any]) -> None:
        if self._writer is None:
            raise LSPError("not connected to the GDScript language server")
        body = json.dumps(message).encode("utf-8")
        self._writer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        try:
            await self._writer.drain()
        except OSError as exc:
            await self.close()
            raise LSPError(f"lost connection to the GDScript language server: {exc}") from exc

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict[str, Any], timeout: float) -> Any:
        msg_id = next(self._ids)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        try:
            await self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            raise LSPError(f"The GDScript language server did not answer {method}.") from None
        finally:
            self._pending.pop(msg_id, None)

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                length = None
                while True:
                    line = await self._reader.readline()
                    if not line:
                        return
                    line = line.strip()
                    if not line:
                        break
                    name, _, value = line.decode("ascii", "replace").partition(":")
                    if name.lower() == "content-length":
                        length = int(value.strip())
                if length is None:
                    continue
                body = await self._reader.readexactly(length)
                try:
                    message = json.loads(body)
                except json.JSONDecodeError:
                    continue
                await self._dispatch(message)
        except (asyncio.IncompleteReadError, OSError):
            return
        finally:
            for fut in [*self._pending.values(), *self._diag_waiters.values()]:
                if not fut.done():
                    fut.set_exception(
                        LSPError("the GDScript language server closed the connection")
                    )

    async def _dispatch(self, message: dict[str, Any]) -> None:
        if "id" in message and ("result" in message or "error" in message):
            fut = self._pending.get(message["id"])
            if fut is not None and not fut.done():
                if "error" in message:
                    err = message["error"] or {}
                    fut.set_exception(LSPError(err.get("message", "language server error")))
                else:
                    fut.set_result(message.get("result"))
            return
        method = message.get("method")
        if "id" in message:  # a request from the server; we support none, answer politely
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": None})
            return
        if method == "textDocument/publishDiagnostics":
            params = message.get("params") or {}
            fut = self._diag_waiters.get(params.get("uri", ""))
            if fut is not None and not fut.done():
                fut.set_result(params.get("diagnostics") or [])
