"""Wire protocol shared by the MCP server and the Blender add-on.

JSON-RPC 2.0 messages, each prefixed with a 4-byte big-endian length.

This module is stdlib-only on purpose: the add-on ships a vendored copy
(addon/blender_mcp_addon/protocol.py). Edit this file, then run
scripts/build_addon.py (or scripts/sync_protocol.py) to update the copy.
"""

from __future__ import annotations

import json
import socket
import struct
from typing import Any

PROTOCOL_VERSION = 1
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876

HEADER = struct.Struct(">I")
MAX_MESSAGE_BYTES = 64 * 1024 * 1024

# JSON-RPC error codes. -326xx are standard, -320xx are ours.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
HANDLER_ERROR = -32000
UNAUTHORIZED = -32001
VERSION_MISMATCH = -32002

HANDSHAKE_METHOD = "handshake"


class ProtocolError(Exception):
    """The byte stream or a message in it is malformed."""


def _json_default(obj: Any) -> Any:
    # mathutils.Vector/Euler/Color and similar are iterable; everything else becomes a string.
    try:
        return list(obj)
    except TypeError:
        return str(obj)


def encode(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, default=_json_default, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"message too large ({len(body)} bytes)")
    return HEADER.pack(len(body)) + body


def decode_body(body: bytes) -> dict[str, Any]:
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    return message


def parse_header(header: bytes) -> int:
    (length,) = HEADER.unpack(header)
    if length > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"message too large ({length} bytes)")
    return length


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    chunks = []
    remaining = n
    while remaining:
        chunk = sock.recv(min(remaining, 1024 * 1024))
        if not chunk:
            if remaining == n:
                return None
            raise ProtocolError("connection closed mid-message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_message(sock: socket.socket) -> dict[str, Any] | None:
    """Blocking read of one message. Returns None on clean EOF."""
    header = _recv_exact(sock, HEADER.size)
    if header is None:
        return None
    body = _recv_exact(sock, parse_header(header))
    if body is None:
        raise ProtocolError("connection closed mid-message")
    return decode_body(body)


def request(msg_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}


def result(msg_id: Any, value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": value}


def error(msg_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": err}
