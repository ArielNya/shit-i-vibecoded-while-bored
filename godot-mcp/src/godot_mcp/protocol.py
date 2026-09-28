"""Wire protocol shared by the MCP server and the Godot editor plugin.

JSON-RPC 2.0 messages, each prefixed with a 4-byte big-endian length.

This module is stdlib-only on purpose: the plugin has a GDScript twin
(addon/addons/godot_mcp/protocol.gd). Keep the constants in sync;
tests/unit/test_protocol_parity.py checks them.
"""

from __future__ import annotations

import json
import os
import stat
import struct
import sys
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9080

HEADER = struct.Struct(">I")
MAX_MESSAGE_BYTES = 32 * 1024 * 1024
# Until a client has completed the handshake it only gets to send small messages.
MAX_UNAUTHENTICATED_BYTES = 64 * 1024

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


def encode(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"message too large ({len(body)} bytes)")
    return HEADER.pack(len(body)) + body


def decode_body(body: bytes) -> dict[str, Any]:
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    return message


def parse_header(header: bytes, max_bytes: int = MAX_MESSAGE_BYTES) -> int:
    (length,) = HEADER.unpack(header)
    if length > max_bytes:
        raise ProtocolError(f"message too large ({length} bytes)")
    return length


def request(msg_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}


# --- shared token file ---------------------------------------------------------------------
#
# The plugin generates a random token and stores it in a file only this user can read;
# the server reads the same file. Other accounts on the machine can reach the
# localhost port but not the file, so they can't connect. GODOT_MCP_TOKEN (server) or
# the plugin's token setting override it.

TOKEN_FILE_ENV = "GODOT_MCP_TOKEN_FILE"


class TokenFileError(Exception):
    """The token file exists but can't be trusted or read."""


def token_file_path() -> Path:
    override = os.environ.get(TOKEN_FILE_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "godot-mcp" / "token"


def _check_private(path: Path) -> None:
    if os.name != "posix":
        return  # per-user profile folders on Windows
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise TokenFileError(
            f"{path} is accessible by other users (mode {stat.filemode(mode)}); "
            f"fix with: chmod 600 {path}"
        )


def read_token_file(path: Path | None = None) -> str | None:
    """The token from the file, or None if there is no file."""
    path = path or token_file_path()
    if not path.is_file():
        return None
    _check_private(path)
    token = path.read_text(encoding="utf-8").strip()
    return token or None
