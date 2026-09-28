"""M1: editor screenshots. Needs an editor with a window: runs it under Xvfb with Mesa's
software OpenGL (skipped when xvfb-run is missing)."""

import pytest

pytestmark = pytest.mark.anyio

EDITOR_OPTIONS = {"display": True}


async def test_auto_picks_2d_for_a_2d_scene(call_image):
    meta = await call_image("get_editor_screenshot")
    assert meta["view"] == "2d"
    assert meta["scene"] == "res://scenes/main.tscn"
    assert max(meta["width"], meta["height"]) <= 768


async def test_3d_and_editor_views(call_image):
    three_d = await call_image("get_editor_screenshot", view="3d", size=256)
    assert three_d["view"] == "3d" and max(three_d["width"], three_d["height"]) <= 256
    window = await call_image("get_editor_screenshot", view="editor", size=1024)
    assert window["view"] == "editor"
    assert window["width"] == 1024  # the 1600x900 window, scaled down to fit


async def test_screenshot_is_not_blank(bridge):
    import base64
    import zlib

    reply = await bridge.call("get_editor_screenshot", {"view": "editor", "size": 200})
    png = base64.b64decode(reply["image_base64"])
    # Crude but dependency-free: a real editor frame compresses far worse than a flat one.
    assert len(png) > 2000 and len(zlib.compress(png)) > 1000
