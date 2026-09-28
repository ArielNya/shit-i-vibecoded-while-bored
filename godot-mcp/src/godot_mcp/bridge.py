"""Async client that talks to the godot-mcp editor plugin over TCP."""

from __future__ import annotations

import asyncio
import itertools
import os
from dataclasses import dataclass
from typing import Any

from . import protocol


class GodotConnectionError(Exception):
    """The Godot editor isn't reachable, or the connection dropped."""


class GodotCommandError(Exception):
    """The editor received the command but it failed."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass
class BridgeConfig:
    host: str = protocol.DEFAULT_HOST
    port: int = protocol.DEFAULT_PORT
    token: str | None = None
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> BridgeConfig:
        return cls(
            host=os.environ.get("GODOT_MCP_HOST", protocol.DEFAULT_HOST),
            port=int(os.environ.get("GODOT_MCP_PORT", protocol.DEFAULT_PORT)),
            token=os.environ.get("GODOT_MCP_TOKEN") or None,
            timeout=float(os.environ.get("GODOT_MCP_TIMEOUT", 30.0)),
        )


class GodotBridge:
    """One persistent connection to the editor; requests are serialized.

    Connects lazily on the first call and reconnects on the next call after a drop.
    `server_info` holds the handshake reply (Godot version, project path, LSP port, ...).
    """

    def __init__(self, config: BridgeConfig | None = None):
        self.config = config or BridgeConfig()
        self.server_info: dict[str, Any] | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)

    @property
    def address(self) -> str:
        return f"{self.config.host}:{self.config.port}"

    async def call(
        self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        async with self._lock:
            await self._ensure_connected()
            limit = timeout or self.config.timeout
            try:
                return await asyncio.wait_for(self._roundtrip(method, params), limit)
            except TimeoutError:
                # The reply may still arrive later; drop the connection so it can't be
                # mistaken for the answer to the next request.
                await self.close()
                raise GodotConnectionError(
                    f"Godot did not answer '{method}' within {limit}s "
                    "(the editor may be busy, e.g. importing assets)."
                ) from None
            except (OSError, asyncio.IncompleteReadError, protocol.ProtocolError) as exc:
                await self.close()
                raise GodotConnectionError(f"Lost connection to Godot: {exc}") from exc

    async def ensure_info(self) -> dict[str, Any]:
        """Connect if needed and return the handshake info."""
        async with self._lock:
            await self._ensure_connected()
            assert self.server_info is not None
            return self.server_info

    async def close(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        self.server_info = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _ensure_connected(self) -> None:
        if self._writer is not None and self._reader is not None and not self._reader.at_eof():
            return
        await self.close()
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.port), 5.0
            )
        except (OSError, TimeoutError) as exc:
            raise GodotConnectionError(
                f"Could not connect to the Godot editor at {self.address}. Is the project open "
                "in Godot 4.7+ with the 'Godot MCP' plugin enabled (Project > Project Settings "
                "> Plugins)? The MCP dock in the editor shows the port it listens on."
            ) from exc
        try:
            info = await asyncio.wait_for(
                self._roundtrip(
                    protocol.HANDSHAKE_METHOD,
                    {"protocol_version": protocol.PROTOCOL_VERSION, "token": self._token()},
                ),
                5.0,
            )
        except GodotConnectionError:
            await self.close()
            raise
        except GodotCommandError as exc:
            await self.close()
            if exc.code == protocol.UNAUTHORIZED:
                source = "GODOT_MCP_TOKEN" if self.config.token else str(protocol.token_file_path())
                raise GodotCommandError(
                    exc.code,
                    f"{exc} — the token from {source} doesn't match the plugin's. If the "
                    "plugin uses a custom token (Editor Settings > godot_mcp/token), set the "
                    "same value in GODOT_MCP_TOKEN.",
                ) from None
            raise
        except (OSError, TimeoutError, asyncio.IncompleteReadError, protocol.ProtocolError) as exc:
            await self.close()
            raise GodotConnectionError(f"Handshake with Godot failed: {exc}") from exc
        self.server_info = info

    def _token(self) -> str | None:
        """Explicit token, else the shared token file — read on every connect, since the
        editor (which creates the file) may start after this server."""
        if self.config.token:
            return self.config.token
        try:
            return protocol.read_token_file()
        except (protocol.TokenFileError, OSError) as exc:
            raise GodotConnectionError(f"Can't use the token file: {exc}") from exc

    async def _roundtrip(self, method: str, params: dict[str, Any] | None) -> Any:
        assert self._reader is not None and self._writer is not None
        msg_id = next(self._ids)
        self._writer.write(protocol.encode(protocol.request(msg_id, method, params)))
        await self._writer.drain()

        header = await self._reader.readexactly(protocol.HEADER.size)
        body = await self._reader.readexactly(protocol.parse_header(header))
        reply = protocol.decode_body(body)
        if reply.get("id") != msg_id:
            raise protocol.ProtocolError(f"reply id {reply.get('id')!r} != request id {msg_id}")
        if "error" in reply:
            err = reply["error"]
            raise GodotCommandError(err.get("code", 0), err.get("message", ""), err.get("data"))
        return reply.get("result")
