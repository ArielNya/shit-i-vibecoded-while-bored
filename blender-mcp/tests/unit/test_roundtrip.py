"""Server -> bridge -> socket -> listener -> main-thread queue, with stub handlers."""

import base64
import json
import socket
import threading

import pytest
from mcp import Client

from blender_mcp import protocol
from blender_mcp.bridge import (
    BlenderBridge,
    BlenderCommandError,
    BlenderConnectionError,
    BridgeConfig,
)
from blender_mcp.server import create_server

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\nfake"
SCENE = {"scene": "Scene", "object_count": 3, "objects_by_type": {"MESH": 1, "CAMERA": 1}}


def boom(params):
    raise RuntimeError("kaboom")


def stub_handlers(calls=None):
    def ping(params):
        if calls is not None:
            calls.append(threading.current_thread().name)
        return {"pong": True}

    def screenshot(params):
        return {
            "image_base64": base64.b64encode(PNG).decode(),
            "mime_type": "image/png",
            "width": params["size"],
            "height": params["size"],
        }

    return {
        "ping": ping,
        "get_scene_info": lambda params: SCENE,
        "boom": boom,
        "get_viewport_screenshot": screenshot,
    }


def bridge_for(fb, **kwargs):
    return BlenderBridge(BridgeConfig(port=fb.listener.port, timeout=5, **kwargs))


async def test_handshake_and_call_runs_on_main_thread(fake_blender):
    calls = []
    fb = fake_blender(stub_handlers(calls))
    bridge = bridge_for(fb)
    assert await bridge.call("ping") == {"pong": True}
    assert bridge.server_info == {
        "protocol_version": protocol.PROTOCOL_VERSION,
        "blender_version": "fake",
    }
    assert calls == ["fake-main"]
    await bridge.close()


async def test_handler_exception_becomes_command_error(fake_blender):
    bridge = bridge_for(fake_blender(stub_handlers()))
    with pytest.raises(BlenderCommandError) as info:
        await bridge.call("boom")
    assert info.value.code == protocol.HANDLER_ERROR
    assert "kaboom" in str(info.value)
    # Connection is still usable afterwards.
    assert await bridge.call("ping") == {"pong": True}
    await bridge.close()


async def test_unknown_method(fake_blender):
    bridge = bridge_for(fake_blender(stub_handlers()))
    with pytest.raises(BlenderCommandError) as info:
        await bridge.call("nope")
    assert info.value.code == protocol.METHOD_NOT_FOUND
    await bridge.close()


async def test_token_required(fake_blender):
    fb = fake_blender(stub_handlers(), token="secret")
    with pytest.raises(BlenderCommandError) as info:
        await bridge_for(fb, token="wrong").call("ping")
    assert info.value.code == protocol.UNAUTHORIZED

    good = bridge_for(fb, token="secret")
    assert await good.call("ping") == {"pong": True}
    await good.close()


async def test_requests_before_handshake_are_rejected(fake_blender):
    fb = fake_blender(stub_handlers())
    with socket.create_connection(("127.0.0.1", fb.listener.port), timeout=5) as sock:
        sock.sendall(protocol.encode(protocol.request(1, "ping")))
        reply = protocol.read_message(sock)
    assert reply["error"]["code"] == protocol.UNAUTHORIZED


async def test_version_mismatch(fake_blender):
    fb = fake_blender(stub_handlers())
    with socket.create_connection(("127.0.0.1", fb.listener.port), timeout=5) as sock:
        sock.sendall(protocol.encode(protocol.request(1, "handshake", {"protocol_version": 999})))
        reply = protocol.read_message(sock)
    assert reply["error"]["code"] == protocol.VERSION_MISMATCH


async def test_reconnects_after_blender_restart(fake_blender):
    fb = fake_blender(stub_handlers())
    port = fb.listener.port
    bridge = bridge_for(fb)
    assert await bridge.call("ping") == {"pong": True}

    fb.listener.stop()
    fb.listener.port = port
    fb.listener.start()

    # The old socket is dead; the next call should notice and reconnect (possibly after
    # one failed call if the drop hasn't been observed yet).
    try:
        result = await bridge.call("ping")
    except BlenderConnectionError:
        result = await bridge.call("ping")
    assert result == {"pong": True}
    await bridge.close()


async def test_connection_refused_message():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    bridge = BlenderBridge(BridgeConfig(port=free_port))
    with pytest.raises(BlenderConnectionError, match="Is Blender running"):
        await bridge.call("ping")


async def test_mcp_tools_end_to_end(fake_blender):
    fb = fake_blender(stub_handlers())
    bridge = bridge_for(fb)
    server = create_server(bridge)
    async with Client(server) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        assert {"ping", "get_scene_info"} <= tools

        result = await client.call_tool("get_scene_info", {})
        assert not result.is_error
        assert json.loads(result.content[0].text) == SCENE

        result = await client.call_tool("ping", {})
        assert not result.is_error
        assert json.loads(result.content[0].text)["blender_version"] == "fake"
    await bridge.close()


async def test_mcp_tool_reports_blender_down():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    server = create_server(BlenderBridge(BridgeConfig(port=free_port)))
    async with Client(server) as client:
        result = await client.call_tool("get_scene_info", {})
    assert result.is_error
    assert "Is Blender running" in result.content[0].text


async def test_image_tool_returns_image_and_metadata(fake_blender):
    bridge = bridge_for(fake_blender(stub_handlers()))
    async with Client(create_server(bridge)) as client:
        result = await client.call_tool("get_viewport_screenshot", {"size": 64})
    assert not result.is_error, result.content
    image, meta = result.content
    assert image.type == "image" and image.mime_type == "image/png"
    assert base64.b64decode(image.data) == PNG
    assert json.loads(meta.text) == {"width": 64, "height": 64}
    await bridge.close()


async def test_invalid_arguments_rejected_before_reaching_blender(fake_blender):
    bridge = bridge_for(fake_blender(stub_handlers()))
    async with Client(create_server(bridge)) as client:
        result = await client.call_tool("get_viewport_screenshot", {"size": 99999})
    assert result.is_error
    await bridge.close()
