"""execute_python stays off when enabled without a token (a Blender started with
--allow-python but no --token). The fully disabled case is in test_blender.py."""

import pytest

pytestmark = pytest.mark.anyio

BLENDER_OPTIONS = {"allow_python": True}


async def test_refused_without_token(call, call_error):
    text = await call_error("execute_python", code="result = 1")
    assert "needs a token" in text
    assert (await call("ping"))["python_enabled"] is False
