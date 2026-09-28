"""Async client that talks to the Blender add-on over TCP."""

from __future__ import annotations

import asyncio
import itertools
import os
from dataclasses import dataclass
from typing import Any

from . import protocol


class BlenderConnectionError(Exception):
    """Blender isn't reachable, or the connection dropped."""


class BlenderCommandError(Exception):
    """Blender received the command but it failed."""

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
            host=os.environ.get("BLENDER_MCP_HOST", protocol.DEFAULT_HOST),
            port=int(os.environ.get("BLENDER_MCP_PORT", protocol.DEFAULT_PORT)),
            token=os.environ.get("BLENDER_MCP_TOKEN") or None,
            timeout=float(os.environ.get("BLENDER_MCP_TIMEOUT", 30.0)),
        )


class BlenderBridge:
    """One persistent connection to Blender; requests are serialized.

    Connects lazily on the first call and reconnects on the next call after a drop.
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
            try:
                return await asyncio.wait_for(
                    self._roundtrip(method, params), timeout or self.config.timeout
                )
            except TimeoutError:
                # The reply may still arrive later; drop the connection so it can't be
                # mistaken for the answer to the next request.
                await self.close()
                raise BlenderConnectionError(
                    f"Blender did not answer '{method}' within {timeout or self.config.timeout}s "
                    "(it may be busy with a long operation)."
                ) from None
            except (OSError, asyncio.IncompleteReadError, protocol.ProtocolError) as exc:
                await self.close()
                raise BlenderConnectionError(f"Lost connection to Blender: {exc}") from exc

    async def switch_port(self, port: int) -> None:
        """Talk to the Blender on another port from the next call on."""
        async with self._lock:
            await self.close()
            self.config.port = port

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
            raise BlenderConnectionError(
                f"Could not connect to Blender at {self.address}. Is Blender running with the "
                "blender-mcp add-on started (3D Viewport sidebar > MCP > Start)?"
            ) from exc
        try:
            token = self._token()
            info = await asyncio.wait_for(
                self._roundtrip(
                    protocol.HANDSHAKE_METHOD,
                    {"protocol_version": protocol.PROTOCOL_VERSION, "token": token},
                ),
                5.0,
            )
        except BlenderConnectionError:
            await self.close()
            raise
        except BlenderCommandError as exc:
            await self.close()
            if exc.code == protocol.UNAUTHORIZED:
                source = (
                    "BLENDER_MCP_TOKEN" if self.config.token else str(protocol.token_file_path())
                )
                raise BlenderCommandError(
                    exc.code,
                    f"{exc} — the token from {source} doesn't match the add-on's. If the "
                    "add-on has a custom token in its preferences, set the same value in "
                    "BLENDER_MCP_TOKEN.",
                ) from None
            raise
        except (OSError, TimeoutError, asyncio.IncompleteReadError, protocol.ProtocolError) as exc:
            await self.close()
            raise BlenderConnectionError(f"Handshake with Blender failed: {exc}") from exc
        self.server_info = info

    def _token(self) -> str | None:
        """Explicit token, else the shared token file — read on every connect, since
        Blender (which creates the file) may start after this server."""
        if self.config.token:
            return self.config.token
        try:
            return protocol.read_token_file()
        except (protocol.TokenFileError, OSError) as exc:
            raise BlenderConnectionError(f"Can't use the token file: {exc}") from exc

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
            raise BlenderCommandError(err.get("code", 0), err.get("message", ""), err.get("data"))
        return reply.get("result")
