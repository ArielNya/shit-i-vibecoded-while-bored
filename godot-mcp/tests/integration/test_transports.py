"""M4: the server as clients actually run it (a separate process), over stdio and
Streamable HTTP, with every MCP protocol version clients still speak."""

import json
import os
import socket
import subprocess
import sys
import time

import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from godot_mcp import protocol

pytestmark = pytest.mark.anyio

# Handshake-era versions (initialize + session). 2026-07-28 (stateless) is what the SDK
# client below negotiates.
LEGACY_VERSIONS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_args(editor, token_file):
    return [
        sys.executable, "-m", "godot_mcp.server",
        "--godot-port", str(editor["port"]),
        "--token-file", str(token_file),
        "--lsp-port", str(editor["lsp_port"]),
    ]  # fmt: skip


@pytest.fixture(scope="module")
def http_server(editor, token_file):
    port = _free_port()
    proc = subprocess.Popen(
        [*server_args(editor, token_file), "--http", "--http-port", str(port)],
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("HTTP server did not start: " + proc.stderr.read())
    yield {"url": f"http://127.0.0.1:{port}/mcp", "token": protocol.read_token_file(token_file)}
    proc.terminate()
    proc.wait(10)


def _headers(token, session=None, version=None):
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if session:
        h["Mcp-Session-Id"] = session
    if version:
        h["Mcp-Protocol-Version"] = version
    return h


def _json_from(response) -> dict:
    """A JSON-RPC reply from a JSON or SSE response body."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data:") and line[5:].strip():
                return json.loads(line[5:])
        raise AssertionError(f"no data in SSE response: {response.text!r}")
    return response.json()


async def test_http_modern_client_with_token(http_server):
    headers = {"Authorization": f"Bearer {http_server['token']}"}
    async with httpx2.AsyncClient(headers=headers, timeout=60) as http:
        async with Client(streamable_http_client(http_server["url"], http_client=http)) as c:
            listed = await c.list_tools()
            assert len(listed.tools) == 64
            result = await c.call_tool("get_project_info", {})
            assert not result.is_error
            assert json.loads(result.content[0].text)["name"] == "MCP Demo"


async def test_http_requires_the_token(http_server):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    async with httpx2.AsyncClient(timeout=10) as http:
        for token in (None, "wrong"):
            r = await http.post(http_server["url"], json=body, headers=_headers(token))
            assert r.status_code == 401


@pytest.mark.parametrize("version", LEGACY_VERSIONS)
async def test_http_legacy_protocol_versions(http_server, version):
    token = http_server["token"]
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": f"legacy-{version}", "version": "0"},
        },
    }
    async with httpx2.AsyncClient(timeout=60) as http:
        r = await http.post(http_server["url"], json=init, headers=_headers(token))
        assert r.status_code == 200, r.text
        reply = _json_from(r)
        assert reply["result"]["protocolVersion"] == version
        session = r.headers.get("mcp-session-id")
        h = _headers(token, session, version)
        note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        assert (await http.post(http_server["url"], json=note, headers=h)).status_code in (200, 202)
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_scene_tree", "arguments": {}},
        }
        reply = _json_from(await http.post(http_server["url"], json=call, headers=h))
        tree = json.loads(reply["result"]["content"][0]["text"])
        assert tree["scene"] == "res://scenes/main.tscn"


async def test_stdio_modern_client(editor, token_file):
    args = server_args(editor, token_file)
    params = StdioServerParameters(command=args[0], args=args[1:], env=dict(os.environ))
    async with Client(params) as c:
        result = await c.call_tool("ping", {})
        assert json.loads(result.content[0].text)["pong"] is True


@pytest.mark.parametrize("version", LEGACY_VERSIONS)
def test_stdio_legacy_protocol_versions(editor, token_file, version):
    proc = subprocess.Popen(
        server_args(editor, token_file),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    def rpc(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        if "id" not in msg:
            return None
        while True:
            line = json.loads(proc.stdout.readline())
            if line.get("id") == msg["id"]:
                return line

    try:
        init = rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": version,
                    "capabilities": {},
                    "clientInfo": {"name": "legacy", "version": "0"},
                },
            }
        )
        assert init["result"]["protocolVersion"] == version
        rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert len(listed["result"]["tools"]) == 64
        called = rpc(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_project_info", "arguments": {}},
            }
        )
        assert json.loads(called["result"]["content"][0]["text"])["name"] == "MCP Demo"
    finally:
        proc.stdin.close()
        proc.wait(10)


async def test_stdio_with_a_scrubbed_environment(editor, token_file):
    """Some harnesses (dsh, sandboxed IDEs) start servers with almost no environment:
    no HOME, no XDG dirs. Flags alone must be enough."""
    args = server_args(editor, token_file)
    params = StdioServerParameters(command=args[0], args=args[1:], env={"PATH": "/usr/bin:/bin"})
    async with Client(params) as c:
        info = json.loads((await c.call_tool("get_project_info", {})).content[0].text)
        assert info["name"] == "MCP Demo"
        diags = json.loads(
            (await c.call_tool("get_diagnostics", {"path": "res://scripts/player.gd"}))
            .content[0]
            .text
        )
        assert diags["error_count"] == 0  # the language server is reachable too


async def test_http_rejects_dns_rebinding(http_server):
    """Even with the token: a page on another origin (or a rebound hostname) is refused."""
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "x", "version": "0"}},
    }  # fmt: skip
    h = _headers(http_server["token"])
    async with httpx2.AsyncClient(timeout=10) as http:
        forged_host = await http.post(
            http_server["url"], json=init, headers={**h, "Host": "evil.example"}
        )
        assert forged_host.status_code == 421
        foreign_origin = await http.post(
            http_server["url"], json=init, headers={**h, "Origin": "http://evil.example"}
        )
        assert foreign_origin.status_code == 403
