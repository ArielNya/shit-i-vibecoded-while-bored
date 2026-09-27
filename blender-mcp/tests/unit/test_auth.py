"""Token file (the default auth) and the handshake deadline."""

import os
import socket
import stat
import time

import pytest

from blender_mcp import protocol
from blender_mcp.bridge import BlenderBridge, BlenderCommandError, BridgeConfig

posix_only = pytest.mark.skipif(os.name != "posix", reason="file modes are POSIX")


def test_token_file_created_private_and_reused(private_token_file):
    assert protocol.read_token_file() is None
    token = protocol.ensure_token_file()
    assert len(token) >= 40
    assert protocol.token_file_path() == private_token_file
    assert protocol.ensure_token_file() == token  # second Blender reuses it
    assert protocol.read_token_file() == token
    if os.name == "posix":
        assert stat.S_IMODE(private_token_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(private_token_file.parent.stat().st_mode) == 0o700


@posix_only
def test_token_file_readable_by_others_is_refused(private_token_file):
    protocol.ensure_token_file()
    private_token_file.chmod(0o644)
    with pytest.raises(protocol.TokenFileError, match="chmod 600"):
        protocol.read_token_file()


def test_default_path_is_per_user(monkeypatch):
    monkeypatch.delenv(protocol.TOKEN_FILE_ENV)
    path = protocol.token_file_path()
    assert path.name == "token" and path.parent.name == "blender-mcp"


@pytest.mark.anyio
async def test_bridge_reads_token_file_at_connect_time(fake_blender):
    # The server starts first (no file yet); Blender creates the file later.
    bridge = BlenderBridge(BridgeConfig(port=1, timeout=5))
    token = protocol.ensure_token_file()
    fb = fake_blender({"ping": lambda p: {"pong": True}}, token=token)
    bridge.config.port = fb.listener.port
    assert await bridge.call("ping") == {"pong": True}
    await bridge.close()


@pytest.mark.anyio
async def test_mismatched_token_explains_where_it_came_from(fake_blender, private_token_file):
    protocol.ensure_token_file()
    fb = fake_blender({"ping": lambda p: {"pong": True}}, token="the-addon-has-another")
    bridge = BlenderBridge(BridgeConfig(port=fb.listener.port, timeout=5))
    with pytest.raises(BlenderCommandError, match=str(private_token_file)):
        await bridge.call("ping")


@pytest.mark.anyio
async def test_unreadable_token_file_is_a_clear_error(fake_blender, private_token_file):
    if os.name != "posix":
        pytest.skip("file modes are POSIX")
    protocol.ensure_token_file()
    private_token_file.chmod(0o666)
    fb = fake_blender({"ping": lambda p: {"pong": True}}, token="x")
    bridge = BlenderBridge(BridgeConfig(port=fb.listener.port, timeout=5))
    with pytest.raises(Exception, match="accessible by other users"):
        await bridge.call("ping")


def test_idle_unauthenticated_connection_is_dropped(fake_blender):
    fb = fake_blender({}, handshake_timeout=0.3)
    with socket.create_connection(("127.0.0.1", fb.listener.port), timeout=5) as sock:
        started = time.monotonic()
        assert sock.recv(1) == b""  # server closed it
        assert time.monotonic() - started < 3
    assert fb.listener.client_count == 0


def test_authenticated_connection_has_no_deadline(fake_blender):
    fb = fake_blender({"ping": lambda p: {"pong": True}}, handshake_timeout=0.3)
    with socket.create_connection(("127.0.0.1", fb.listener.port), timeout=5) as sock:
        params = {"protocol_version": protocol.PROTOCOL_VERSION}
        sock.sendall(protocol.encode(protocol.request(1, "handshake", params)))
        assert "result" in protocol.read_message(sock)
        time.sleep(0.6)  # longer than the handshake deadline
        sock.sendall(protocol.encode(protocol.request(2, "ping")))
        assert protocol.read_message(sock)["result"] == {"pong": True}
