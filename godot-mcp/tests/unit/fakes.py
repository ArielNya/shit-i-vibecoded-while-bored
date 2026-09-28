"""In-process stand-ins for the Godot editor plugin and its GDScript language server."""

from __future__ import annotations

import asyncio
import json

from godot_mcp import protocol


class FakeGodot:
    """Speaks the plugin's framed JSON-RPC: handshake (with token) + stub handlers.

    A handler returns a result, or raises FakeError to reply with a JSON-RPC error.
    """

    def __init__(self, handlers, token=None, info=None, protocol_version=protocol.PROTOCOL_VERSION):
        self.handlers = handlers
        self.token = token
        self.info = info or {"godot_version": "4.7.2-stable (fake)", "project_path": "/p/"}
        self.protocol_version = protocol_version
        self.port = 0
        self.calls: list[tuple[str, dict]] = []
        self._server: asyncio.base_events.Server | None = None
        self._writers: list[asyncio.StreamWriter] = []

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        # Like an editor quitting: drop live connections too, not just the listener.
        for writer in self._writers:
            writer.close()
        self._server.close()
        await self._server.wait_closed()

    async def _client(self, reader, writer):
        self._writers.append(writer)
        authed = False
        try:
            while True:
                header = await reader.readexactly(4)
                body = await reader.readexactly(protocol.parse_header(header))
                msg = protocol.decode_body(body)
                msg_id, method, params = msg["id"], msg["method"], msg.get("params") or {}
                if method == protocol.HANDSHAKE_METHOD:
                    if params.get("protocol_version") != self.protocol_version:
                        reply = protocol.error(
                            msg_id, protocol.VERSION_MISMATCH, "version mismatch"
                        )
                    elif self.token and params.get("token") != self.token:
                        reply = protocol.error(msg_id, protocol.UNAUTHORIZED, "invalid token")
                    else:
                        authed = True
                        reply = protocol.result(msg_id, self.info)
                elif not authed:
                    reply = protocol.error(msg_id, protocol.UNAUTHORIZED, "handshake required")
                elif method not in self.handlers:
                    reply = protocol.error(msg_id, protocol.METHOD_NOT_FOUND, "unknown method")
                else:
                    self.calls.append((method, params))
                    try:
                        value = self.handlers[method](params)
                        if asyncio.iscoroutine(value):
                            value = await value
                        reply = protocol.result(msg_id, value)
                    except FakeError as exc:
                        reply = protocol.error(msg_id, exc.code, str(exc), exc.data)
                writer.write(protocol.encode(reply))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()


class FakeError(Exception):
    def __init__(self, message, code=protocol.HANDLER_ERROR, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


class FakeLSP:
    """Answers initialize, nativeSymbol and didOpen (publishing canned diagnostics)."""

    def __init__(self, diagnostics=None, symbols=None):
        self.diagnostics = diagnostics or {}  # uri suffix -> list
        self.symbols = symbols or {}  # (class, symbol) -> result
        self.received: list[dict] = []
        self.port = 0

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()

    @staticmethod
    def _frame(message):
        body = json.dumps(message).encode()
        return b"Content-Length: %d\r\n\r\n" % len(body) + body

    async def _client(self, reader, writer):
        try:
            while True:
                length = None
                while True:
                    raw = await reader.readline()
                    if not raw:
                        return  # client went away
                    line = raw.strip()
                    if not line:
                        break
                    name, _, value = line.decode().partition(":")
                    if name.lower() == "content-length":
                        length = int(value)
                msg = json.loads(await reader.readexactly(length))
                self.received.append(msg)
                method = msg.get("method")
                if method == "initialize":
                    # Godot sends a notification and a server->client request first.
                    writer.write(self._frame({"jsonrpc": "2.0", "method": "window/logMessage"}))
                    writer.write(self._frame({"jsonrpc": "2.0", "id": 99, "method": "x/ask"}))
                    writer.write(self._frame({"jsonrpc": "2.0", "id": msg["id"], "result": {}}))
                elif method == "textDocument/nativeSymbol":
                    p = msg["params"]
                    result = self.symbols.get((p["native_class"], p["symbol_name"]))
                    writer.write(self._frame({"jsonrpc": "2.0", "id": msg["id"], "result": result}))
                elif method == "textDocument/didOpen":
                    uri = msg["params"]["textDocument"]["uri"]
                    diags = next((d for k, d in self.diagnostics.items() if uri.endswith(k)), [])
                    publish = {"uri": uri, "diagnostics": diags}
                    writer.write(
                        self._frame(
                            {
                                "jsonrpc": "2.0",
                                "method": "textDocument/publishDiagnostics",
                                "params": publish,
                            }
                        )
                    )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
