"""Python-side argument mapping of the run toolset, against a fake editor."""

import base64
import json

import pytest
from mcp import Client

from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.server import create_server

from .fakes import FakeGodot

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\ngame"


@pytest.fixture
async def session():
    handlers = {
        "wait_for": lambda p: {"met": True, "got": p},
        "send_input": lambda p: {"sent": len(p["events"])},
        "get_game_screenshot": lambda p: {
            "image_base64": base64.b64encode(PNG).decode(),
            "mime_type": "image/png",
            "width": p["size"],
            "height": 10,
        },
    }
    async with FakeGodot(handlers) as fake:
        bridge = GodotBridge(BridgeConfig(port=fake.port, timeout=5))
        async with Client(create_server(bridge)) as client:
            yield client, fake
        await bridge.close()


async def call(client, tool, **args):
    res = await client.call_tool(tool, args)
    assert not res.is_error, res.content
    return json.loads(res.content[0].text)


@pytest.mark.parametrize(
    ("args", "sent"),
    [
        ({"until": "frames", "frames": 30}, {"frames": 30, "timeout": 10}),
        ({"until": "seconds", "seconds": 2.5}, {"seconds": 2.5, "timeout": 10}),
        ({"until": "node_exists", "node": "Boss"}, {"node_exists": "Boss", "timeout": 10}),
        ({"until": "node_gone", "node": "Coin", "timeout": 3}, {"node_gone": "Coin", "timeout": 3}),
        (
            {"until": "property", "node": "Player", "property": "position:x", "op": ">",
             "value": "300", "timeout": 5},
            {"property": {"node": "Player", "property": "position:x", "op": ">", "value": 300},
             "timeout": 5},
        ),
        (
            {"until": "property", "node": "Player", "property": "position",
             "value": "Vector2(1, 2)"},
            {"property": {"node": "Player", "property": "position", "op": "==",
                          "value": "Vector2(1, 2)"}, "timeout": 10},
        ),
        (
            {"until": "signal", "node": "Door", "signal": "opened"},
            {"signal": {"node": "Door", "signal": "opened"}, "timeout": 10},
        ),
    ],
)  # fmt: skip
async def test_wait_for_builds_one_condition(session, args, sent):
    client, fake = session
    assert (await call(client, "wait_for", **args))["met"] is True
    assert fake.calls[-1] == ("wait_for", sent)


async def test_send_input_and_screenshot(session):
    client, fake = session
    await call(client, "send_input", events=[{"action": "jump"}], frames=12)
    assert fake.calls[-1] == (
        "send_input",
        {"events": [{"action": "jump"}], "mode": "tap", "frames": 12},
    )
    res = await client.call_tool("get_game_screenshot", {"size": 200})
    image, meta = res.content
    assert base64.b64decode(image.data) == PNG
    assert json.loads(meta.text) == {"width": 200, "height": 10}
