"""execute_python stays off in a Blender started without authentication (--no-auth),
even with --allow-python. The fully disabled case is in test_blender.py."""

import pytest

pytestmark = pytest.mark.anyio

BLENDER_OPTIONS = {"allow_python": True, "no_auth": True}


async def test_refused_without_token(call, call_error):
    text = await call_error("execute_python", code="result = 1")
    assert "needs authentication" in text
    assert (await call("ping"))["python_enabled"] is False
