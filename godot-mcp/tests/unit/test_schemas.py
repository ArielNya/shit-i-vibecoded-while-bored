"""Every tool must be usable from every major MCP client, so schemas stay in the
lowest common denominator (see PLAN.md §6.2): no $ref/$defs, no anyOf/oneOf/allOf,
explicit types everywhere, short names and descriptions."""

import pytest

from godot_mcp import compat, tools
from godot_mcp.server import create_server, selected_tools

pytestmark = pytest.mark.anyio


async def test_every_tool_is_portable_to_every_client():
    """PLAN §6.2: Claude, OpenAI/Codex, Gemini (OpenAPI subset), Cursor (60-char names),
    VS Code. The same check runs in CI via scripts/check_harness_schemas.py."""
    listed = await create_server().list_tools()
    assert len(listed) == len({t.name for t in listed})
    assert {t.name: compat.problems(t) for t in listed if compat.problems(t)} == {}


def test_problems_are_detected():
    from mcp.types import Tool

    bad = Tool(
        name="x" * 70,
        description="d",
        input_schema={
            "type": "object",
            "properties": {"a": {"anyOf": [{"type": "string"}]}, "b": {"type": "object",
                           "additionalProperties": True}},
        },
        output_schema={"type": "object"},
    )  # fmt: skip
    found = "\n".join(compat.problems(bad))
    for expected in ["over 64", "over 60", "'anyOf'", "a has no type", "'additionalProperties'",
                     "output schema"]:  # fmt: skip
        assert expected in found


async def names(toolsets):
    sets, keep = selected_tools(toolsets)
    return {t.name for t in await create_server(toolsets=sets, keep=keep).list_tools()}


async def test_toolsets_and_presets():
    assert await names("docs") == {"get_class_docs", "search_docs"}
    everything = await names(None)
    assert len(everything) == 52 and await names("all") == everything
    minimal, core = await names("minimal"), await names("core")
    assert minimal == set(tools.MINIMAL) and core == set(tools.CORE)
    assert minimal < core < everything and len(core) <= 32
    # presets and toolsets combine
    assert await names("minimal,docs") == minimal | {"search_docs"}
    assert selected_tools(" scene , docs ") == (["scene", "docs"], None)
    with pytest.raises(SystemExit, match="unknown"):
        selected_tools("scene,nope")
