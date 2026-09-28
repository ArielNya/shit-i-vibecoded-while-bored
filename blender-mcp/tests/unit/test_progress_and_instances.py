"""M7 server features against fake Blenders: progress heartbeats, several instances."""

import socket
import time

import pytest
from mcp import Client

from blender_mcp.bridge import BlenderBridge, BridgeConfig
from blender_mcp.server import create_server
from blender_mcp.tools import _common

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\nfake"


def slow_screenshot(params):
    import base64

    time.sleep(0.6)  # "Blender is busy"
    return {"image_base64": base64.b64encode(PNG).decode(), "width": 1, "height": 1}


async def test_long_calls_report_progress(fake_blender, monkeypatch):
    monkeypatch.setattr(_common, "PROGRESS_INTERVAL", 0.1)
    fb = fake_blender({"get_viewport_screenshot": slow_screenshot})
    bridge = BlenderBridge(BridgeConfig(port=fb.listener.port, timeout=5))
    updates = []

    async def on_progress(progress, total, message):
        updates.append((progress, message))

    async with Client(create_server(bridge)) as client:
        result = await client.call_tool(
            "get_viewport_screenshot", {"size": 64}, progress_callback=on_progress
        )
    assert not result.is_error
    assert len(updates) >= 3
    assert updates == sorted(updates)  # elapsed time only goes up
    assert "get_viewport_screenshot" in updates[0][1]
    await bridge.close()


def _free_consecutive_ports(n=3):
    for _ in range(50):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            base = probe.getsockname()[1]
        if base + n >= 65535:
            continue
        socks = []
        try:
            for p in range(base, base + n):
                s = socket.socket()
                s.bind(("127.0.0.1", p))
                socks.append(s)
            return base
        except OSError:
            continue
        finally:
            for s in socks:
                s.close()
    pytest.skip("no free consecutive ports")


def blender_named(name):
    return {"ping": lambda params: {"pong": True, "file": name, "scene": "Scene", "objects": 1}}


async def test_list_and_switch_instances(fake_blender):
    base = _free_consecutive_ports(3)
    fake_blender(blender_named("/work/a.blend"), port=base)
    fake_blender(blender_named("/work/b.blend"), port=base + 1, token="someone-elses")
    # base + 2: nothing listening
    bridge = BlenderBridge(BridgeConfig(port=base, timeout=5))
    async with Client(create_server(bridge)) as client:
        found = await client.call_tool("list_blender_instances", {"first_port": base, "count": 3})
        data = found.structured_content
        by_port = {i["port"]: i for i in data["instances"]}
        assert set(by_port) == {base, base + 1}
        assert by_port[base]["file"] == "/work/a.blend" and by_port[base]["active"] is True
        assert "invalid token" in by_port[base + 1]["error"]

        refused = await client.call_tool("use_blender", {"port": base + 1})
        assert refused.is_error and "refused" in refused.content[0].text
        missing = await client.call_tool("use_blender", {"port": base + 2})
        assert missing.is_error and "No Blender" in missing.content[0].text
    await bridge.close()


async def test_switching_changes_where_calls_go(fake_blender):
    base = _free_consecutive_ports(2)
    fake_blender(blender_named("/work/a.blend"), port=base)
    fake_blender(blender_named("/work/b.blend"), port=base + 1)
    bridge = BlenderBridge(BridgeConfig(port=base, timeout=5))
    async with Client(create_server(bridge)) as client:
        first = (await client.call_tool("ping", {})).structured_content
        assert first["file"] == "/work/a.blend"
        switched = await client.call_tool("use_blender", {"port": base + 1})
        assert not switched.is_error
        second = (await client.call_tool("ping", {})).structured_content
        assert second["file"] == "/work/b.blend"
    await bridge.close()
