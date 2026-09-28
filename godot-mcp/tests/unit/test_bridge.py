"""MCP server -> bridge -> fake editor, without Godot."""

import base64
import json

import pytest
from mcp import Client

from godot_mcp import protocol
from godot_mcp.bridge import BridgeConfig, GodotBridge, GodotCommandError, GodotConnectionError
from godot_mcp.server import create_server

from .fakes import FakeError, FakeGodot

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\nfake"


def handlers():
    def screenshot(params):
        return {
            "image_base64": base64.b64encode(PNG).decode(),
            "mime_type": "image/png",
            "view": params["view"],
            "width": 10,
            "height": 5,
        }

    def fail(params):
        raise FakeError("No node 'X' in the scene.", data="res://a.gd:3: boom")

    return {
        "ping": lambda p: {"pong": True, "editor_ready": True},
        "get_scene_tree": fail,
        "get_editor_screenshot": screenshot,
        "set_project_setting": lambda p: p,
    }


def bridge_for(fake, **kwargs):
    return GodotBridge(BridgeConfig(port=fake.port, timeout=5, **kwargs))


async def test_handshake_then_calls():
    async with FakeGodot(handlers()) as fake:
        bridge = bridge_for(fake)
        assert await bridge.call("ping") == {"pong": True, "editor_ready": True}
        assert bridge.server_info["godot_version"].startswith("4.7")
        await bridge.close()


async def test_token_from_env_and_file(private_token_file):
    async with FakeGodot(handlers(), token="s3cret") as fake:
        with pytest.raises(GodotCommandError, match="doesn't match"):
            await bridge_for(fake, token="wrong").call("ping")
        assert (await bridge_for(fake, token="s3cret").call("ping"))["pong"]
        # No explicit token: the shared token file (as created by the plugin) is used.
        protocol.ensure_token_file(private_token_file)
        fake.token = protocol.read_token_file(private_token_file)
        bridge = bridge_for(fake)
        assert (await bridge.call("ping"))["pong"]
        await bridge.close()


async def test_version_mismatch_is_reported():
    async with FakeGodot(handlers(), protocol_version=99) as fake:
        with pytest.raises(GodotCommandError, match="version mismatch"):
            await bridge_for(fake).call("ping")


async def test_no_editor_gives_actionable_error():
    bridge = GodotBridge(BridgeConfig(port=1, timeout=1))
    with pytest.raises(GodotConnectionError, match="Godot MCP' plugin enabled"):
        await bridge.call("ping")


async def test_tools_map_errors_and_images():
    async with FakeGodot(handlers()) as fake:
        bridge = bridge_for(fake)
        async with Client(create_server(bridge)) as client:
            ping = await client.call_tool("ping", {})
            data = json.loads(ping.content[0].text)
            assert data["connected"] and data["address"] == f"127.0.0.1:{fake.port}"

            failed = await client.call_tool("get_scene_tree", {})
            assert failed.is_error
            assert "No node 'X'" in failed.content[0].text
            assert "res://a.gd:3: boom" in failed.content[0].text  # engine log detail

            shot = await client.call_tool("get_editor_screenshot", {"view": "3d"})
            image, meta = shot.content
            assert image.type == "image" and base64.b64decode(image.data) == PNG
            assert json.loads(meta.text) == {"view": "3d", "width": 10, "height": 5}

            await client.call_tool("set_project_setting", {"name": "a/b", "value": "[1, 2]"})
            assert fake.calls[-1] == (
                "set_project_setting",
                {"name": "a/b", "value": [1, 2], "value_text": "[1, 2]"},
            )
            # "null" resets: the value is left out, only the raw text is sent.
            await client.call_tool("set_project_setting", {"name": "a/b", "value": "null"})
            assert fake.calls[-1][1] == {"name": "a/b", "value_text": "null"}
        await bridge.close()


async def test_editor_restart_reconnects():
    """After the editor restarts, the next call notices the closed connection and
    reconnects (with a fresh handshake) instead of failing."""
    async with FakeGodot(handlers()) as fake:
        bridge = bridge_for(fake)
        await bridge.call("ping")
    async with FakeGodot(handlers(), info={"godot_version": "4.7.3"}) as fake2:
        bridge.config.port = fake2.port
        assert (await bridge.call("ping"))["pong"]
        assert bridge.server_info["godot_version"] == "4.7.3"
        await bridge.close()
