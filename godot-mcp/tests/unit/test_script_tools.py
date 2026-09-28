"""Python-side logic of the script tools, against a fake editor + fake LSP."""

import json

import pytest
from mcp import Client

from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.server import create_server
from godot_mcp.tools.script import _find_word, _flatten

from .fakes import FakeGodot, FakeLSP

pytestmark = pytest.mark.anyio

ERR = {
    "severity": 1,
    "message": 'Identifier "oops" not declared in the current scope.',
    "range": {"start": {"line": 3, "character": 1}, "end": {"line": 3, "character": 5}},
}


def test_find_word_matches_whole_identifiers():
    assert _find_word("\tp.hurt()", "hurt") == 3
    assert _find_word("var hurting := hurt", "hurt") == 15
    assert _find_word("nothing here", "hurt") == -1


def test_flatten_marks_nesting():
    symbols = [
        {
            "name": "Hero",
            "kind": 5,
            "children": [
                {"name": "hp", "kind": 13},
                {"name": "Inner", "kind": 5, "children": [{"name": "x", "kind": 13}]},
            ],
        }
    ]
    flat = [(s["name"], parent) for s, parent in _flatten(symbols)]
    assert flat == [("Hero", ""), ("hp", ""), ("Inner", ""), ("x", "Inner")]


async def test_write_script_returns_fresh_diagnostics():
    files = {}

    def write(p):
        files[p["path"]] = p["content"]
        return {"path": p["path"], "created": True, "lines": 4}

    async with FakeLSP(diagnostics={"/a.gd": [ERR]}) as lsp:
        info = {"project_path": "/proj/", "lsp": {"host": "127.0.0.1", "port": lsp.port}}
        handlers = {
            "write_script": write,
            "read_text_files": lambda p: {"files": {k: files.get(k) for k in p["paths"]}},
        }
        async with FakeGodot(handlers, info=info) as fake:
            bridge = GodotBridge(BridgeConfig(port=fake.port, timeout=5))
            async with Client(create_server(bridge)) as client:
                res = await client.call_tool(
                    "write_script", {"path": "res://a.gd", "content": "extends Node\n"}
                )
                data = json.loads(res.content[0].text)
                assert data["errors"] == [
                    '4:2 Identifier "oops" not declared in the current scope.'
                ]
                assert data["created"] is True
            await bridge.close()


async def test_write_script_without_language_server_still_writes():
    info = {"project_path": "/proj/", "lsp": {"host": "127.0.0.1", "port": 1}}
    handlers = {
        "write_script": lambda p: {"path": p["path"], "created": False, "lines": 1},
        "read_text_files": lambda p: {"files": {k: "x" for k in p["paths"]}},
    }
    async with FakeGodot(handlers, info=info) as fake:
        bridge = GodotBridge(BridgeConfig(port=fake.port, timeout=5))
        async with Client(create_server(bridge)) as client:
            res = await client.call_tool("write_script", {"path": "res://a.gd", "content": "x"})
            assert not res.is_error
            assert "diagnostics_unavailable" in json.loads(res.content[0].text)
        await bridge.close()
