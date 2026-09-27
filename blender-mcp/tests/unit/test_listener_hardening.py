"""Hostile or broken input must get an error reply, never a dead connection thread."""

import socket

from blender_mcp_addon import listener as listener_mod

from blender_mcp import protocol


def connect(fb) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", fb.listener.port), timeout=5)
    return sock


def assert_closed(sock):
    # Unread bytes left in the server's buffer turn its close into a TCP reset.
    try:
        assert protocol.read_message(sock) is None
    except ConnectionResetError:
        pass


def handshake(sock, token=None):
    params = {"protocol_version": protocol.PROTOCOL_VERSION, "token": token}
    sock.sendall(protocol.encode(protocol.request(1, "handshake", params)))
    return protocol.read_message(sock)


def handlers(calls):
    def ping(params):
        calls.append("ping")
        return {"pong": True}

    return {"ping": ping, "huge": lambda params: "x" * (protocol.MAX_MESSAGE_BYTES + 1)}


def test_http_request_from_browser_is_rejected(fake_blender):
    calls = []
    fb = fake_blender(handlers(calls))
    with connect(fb) as sock:
        sock.sendall(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}")
        reply = protocol.read_message(sock)
        assert reply["error"]["code"] == protocol.PARSE_ERROR
        assert_closed(sock)
    assert calls == []


def test_non_ascii_token(fake_blender):
    fb = fake_blender(handlers([]), token="pässwörd")
    with connect(fb) as sock:
        assert handshake(sock, "wrong")["error"]["code"] == protocol.UNAUTHORIZED
    with connect(fb) as sock:
        assert "result" in handshake(sock, "pässwörd")


def test_large_message_before_handshake_is_refused(fake_blender):
    fb = fake_blender(handlers([]))
    with connect(fb) as sock:
        sock.sendall(protocol.HEADER.pack(protocol.MAX_UNAUTHENTICATED_BYTES + 1))
        reply = protocol.read_message(sock)
    assert reply["error"]["code"] == protocol.PARSE_ERROR


def test_deeply_nested_json_after_handshake(fake_blender):
    fb = fake_blender(handlers([]))
    with connect(fb) as sock:
        handshake(sock)
        body = b"[" * 200_000 + b"]" * 200_000
        sock.sendall(protocol.HEADER.pack(len(body)) + body)
        reply = protocol.read_message(sock)
    assert reply["error"]["code"] == protocol.PARSE_ERROR


def test_oversized_result_returns_error_and_keeps_connection(fake_blender):
    calls = []
    fb = fake_blender(handlers(calls))
    with connect(fb) as sock:
        sock.settimeout(30)
        handshake(sock)
        sock.sendall(protocol.encode(protocol.request(2, "huge")))
        reply = protocol.read_message(sock)
        assert reply["id"] == 2 and "too large" in reply["error"]["message"]
        sock.sendall(protocol.encode(protocol.request(3, "ping")))
        assert protocol.read_message(sock)["result"] == {"pong": True}


def test_client_limit(fake_blender):
    fb = fake_blender(handlers([]))
    socks = [connect(fb) for _ in range(listener_mod.MAX_CLIENTS)]
    try:
        for sock in socks:
            assert "result" in handshake(sock)
        with connect(fb) as extra:
            assert_closed(extra)  # accepted then closed
    finally:
        for sock in socks:
            sock.close()
