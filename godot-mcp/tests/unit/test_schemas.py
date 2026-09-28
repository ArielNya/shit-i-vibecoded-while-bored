"""Every tool must be usable from every major MCP client, so schemas stay in the
lowest common denominator (see PLAN.md §6.2): no $ref/$defs, no anyOf/oneOf/allOf,
explicit types everywhere, short names and descriptions."""

import re

import pytest

from godot_mcp import tools
from godot_mcp.server import _toolsets, create_server

pytestmark = pytest.mark.anyio

NAME = re.compile(r"^[a-z0-9_]{1,48}$")
FORBIDDEN = {"$ref", "$defs", "definitions", "anyOf", "oneOf", "allOf", "patternProperties"}


def _walk(schema, path="$"):
    if isinstance(schema, dict):
        bad = FORBIDDEN & schema.keys()
        assert not bad, f"{path} uses {bad}"
        if "properties" in schema:
            for key, sub in schema["properties"].items():
                assert "type" in sub or "enum" in sub, f"{path}.{key} has no type"
                _walk(sub, f"{path}.{key}")
        if "items" in schema:
            assert "type" in schema["items"], f"{path}[] has no type"
            _walk(schema["items"], f"{path}[]")


async def test_tool_schemas_are_portable():
    listed = await create_server().list_tools()
    assert len(listed) == len({t.name for t in listed})
    for tool in listed:
        assert NAME.match(tool.name), tool.name
        assert tool.description and len(tool.description) <= 500, tool.name
        assert tool.input_schema["type"] == "object"
        _walk(tool.input_schema, tool.name)


async def test_toolsets_select_groups():
    only = await create_server(toolsets=["docs"]).list_tools()
    assert {t.name for t in only} == {"get_class_docs", "search_docs"}
    assert _toolsets(None) == list(tools.TOOLSETS)
    assert _toolsets(" scene , docs ") == ["scene", "docs"]
    with pytest.raises(SystemExit, match="unknown toolset"):
        _toolsets("scene,nope")
