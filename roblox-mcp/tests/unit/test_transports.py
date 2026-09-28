"""The server as a client runs it: a separate process over stdio and over HTTP."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

pytestmark = pytest.mark.anyio

SAMPLE = str(Path(__file__).parent.parent / "fixtures" / "sample_game")
ARGS = [sys.executable, "-m", "roblox_mcp.server", "--project", SAMPLE]


async def test_stdio_with_an_empty_environment():
    """Harnesses may spawn servers with a scrubbed env: flags alone must be enough."""
    params = StdioServerParameters(command=ARGS[0], args=ARGS[1:], env={"PATH": "/usr/bin:/bin"})
    async with Client(params) as c:
        info = json.loads((await c.call_tool("get_project_info", {})).content[0].text)
        assert info["mode"] == "rojo" and info["name"] == "sample_game"


@pytest.fixture
def http_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [*ARGS, "--http", "--http-port", str(port), "--http-token", "t"],
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
    yield f"http://127.0.0.1:{port}/mcp"
    proc.terminate()
    proc.wait(10)


async def test_http_with_and_without_the_token(http_url):
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer t"}, timeout=30) as http:
        async with Client(streamable_http_client(http_url, http_client=http)) as c:
            info = json.loads((await c.call_tool("get_project_info", {})).content[0].text)
            assert info["name"] == "sample_game"
    async with httpx2.AsyncClient(timeout=30) as http:
        assert (await http.post(http_url, json={})).status_code == 401
