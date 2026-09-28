"""GDScript language server client against a fake server."""

import pytest
from mcp import Client

from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.lsp import GDScriptLSP, LSPError, path_to_uri, uri_to_path
from godot_mcp.server import create_server

from .fakes import FakeGodot, FakeLSP

pytestmark = pytest.mark.anyio

ERR = {
    "severity": 1,
    "message": 'Function "foo()" not found in base self.',
    "range": {"start": {"line": 4, "character": 1}, "end": {"line": 4, "character": 4}},
}
WARN = {
    "severity": 2,
    "message": "(UNUSED_VARIABLE): x",
    "range": {"start": {"line": 2, "character": 0}, "end": {"line": 2, "character": 1}},
}


def test_uris():
    assert path_to_uri("/tmp/my project/a.gd") == "file:///tmp/my%20project/a.gd"
    assert path_to_uri("C:/Games/x.gd") == "file:///C:/Games/x.gd"
    assert uri_to_path("file:///tmp/my%20project/a.gd") == "/tmp/my project/a.gd"
    assert uri_to_path("file:///C:/Games/x.gd") == "C:/Games/x.gd"
    lsp = GDScriptLSP("127.0.0.1", 1, "/tmp/my project/")
    assert lsp.res_to_uri("res://scripts/a.gd") == "file:///tmp/my%20project/scripts/a.gd"
    assert lsp.uri_to_res("file:///tmp/my%20project/scripts/a.gd") == "res://scripts/a.gd"


async def test_diagnostics_and_symbols():
    async with FakeLSP(
        diagnostics={"/bad.gd": [ERR]},
        symbols={("Node", "Node"): {"name": "Node", "documentation": "Base class."}},
    ) as server:
        lsp = GDScriptLSP("127.0.0.1", server.port, "/proj")
        assert await lsp.diagnostics("res://bad.gd", "extends Node") == [ERR]
        assert await lsp.diagnostics("res://ok.gd", "extends Node") == []
        # Second request for the same file: closed and re-opened, new version.
        await lsp.diagnostics("res://bad.gd", "extends Node")
        opens = [m for m in server.received if m.get("method") == "textDocument/didOpen"]
        assert [m["params"]["textDocument"]["version"] for m in opens] == [1, 1, 2]
        assert (await lsp.native_symbol("Node"))["documentation"] == "Base class."
        assert await lsp.native_symbol("Nope") is None
        # The server's request during initialize got an answer.
        assert any(m.get("id") == 99 and "result" in m for m in server.received)
        await lsp.close()


async def test_unreachable_server():
    lsp = GDScriptLSP("127.0.0.1", 1, "/proj")
    with pytest.raises(LSPError, match="GODOT_MCP_LSP_PORT"):
        await lsp.diagnostics("res://a.gd", "")


async def test_get_diagnostics_tool(monkeypatch):
    async with FakeLSP(diagnostics={"/scripts/bad.gd": [ERR, WARN]}) as server:
        files = {"res://scripts/bad.gd": "x", "res://scripts/ok.gd": "y"}
        godot_handlers = {
            "list_script_files": lambda p: {"files": list(files)},
            "read_text_files": lambda p: {"files": {k: files.get(k) for k in p["paths"]}},
        }
        info = {"project_path": "/proj/", "lsp": {"host": "127.0.0.1", "port": server.port}}
        async with FakeGodot(godot_handlers, info=info) as fake:
            bridge = GodotBridge(BridgeConfig(port=fake.port, timeout=5))
            async with Client(create_server(bridge)) as client:
                result = await client.call_tool("get_diagnostics", {})
                assert not result.is_error, result.content
                import json

                data = json.loads(result.content[0].text)
                assert data == {
                    "files_checked": 2,
                    "error_count": 1,
                    "warning_count": 1,
                    "files": [
                        {
                            "path": "res://scripts/bad.gd",
                            "errors": ['5:2 Function "foo()" not found in base self.'],
                            "warnings": ["3:1 (UNUSED_VARIABLE): x"],
                        }
                    ],
                }
                cs = await client.call_tool("get_diagnostics", {"path": "res://a.cs"})
                assert cs.is_error and "dotnet" in cs.content[0].text
            await bridge.close()
