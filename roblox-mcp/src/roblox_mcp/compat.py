"""Keeping tool definitions acceptable to every major MCP client.

`make_portable` rewrites the SDK-generated schemas once at startup; `problems` checks a
listed tool against each client's known rules (used by tests and
scripts/check_harness_schemas.py).
"""

from __future__ import annotations

import re
from typing import Any

# Gemini's function declarations accept an OpenAPI 3.0 subset; relayed verbatim, any
# other keyword fails the whole request with a 400. The strictest, so everyone's fine.
GEMINI_KEYS = {
    "type", "description", "properties", "required", "items", "enum", "format", "nullable",
    "minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength", "pattern",
    "default",
}  # fmt: skip
NAME = re.compile(r"^[a-zA-Z0-9_-]+$")
SERVER_NAME = "roblox"


def _clean(schema: Any) -> Any:
    if isinstance(schema, dict):
        out = {}
        for key, value in schema.items():
            if key == "title" or (key == "additionalProperties" and value is True):
                continue  # noise, and JSON Schema's default anyway
            out[key] = (
                _clean(value)
                if key != "properties"
                else {name: _clean(prop) for name, prop in value.items()}
            )
        return out
    if isinstance(schema, list):
        return [_clean(v) for v in schema]
    return schema


def make_portable(tool_manager: Any) -> None:
    """Strip keywords strict clients reject from every tool's input schema, and drop
    output schemas: ours only say "an object", and some clients (Gemini) reject output
    schemas. Results are still the same JSON, as text content."""
    for tool in tool_manager.list_tools():
        tool.parameters = _clean(tool.parameters)
        tool.fn_metadata.output_schema = None


def _walk(schema: dict, path: str, out: list[str]) -> None:
    for key in schema:
        if key not in GEMINI_KEYS:
            out.append(f"gemini: {path} uses '{key}'")
    props = schema.get("properties")
    if isinstance(props, dict):
        for name, prop in props.items():
            if "type" not in prop:
                out.append(f"all: {path}.{name} has no type")
            _walk(prop, f"{path}.{name}", out)
    if isinstance(schema.get("items"), dict):
        _walk(schema["items"], f"{path}[]", out)


def problems(tool: Any, server_name: str = SERVER_NAME) -> list[str]:
    """Rule violations for one listed tool (mcp.types.Tool), prefixed with the client
    whose rule it breaks."""
    out: list[str] = []
    name = tool.name
    if not NAME.match(name):
        out.append(f"all: name '{name}' has characters outside [a-zA-Z0-9_-]")
    if len(f"mcp__{server_name}__{name}") > 64:
        out.append(f"claude/openai: 'mcp__{server_name}__{name}' is over 64 characters")
    if len(server_name + name) > 60:
        out.append(f"cursor: server + tool name '{server_name}{name}' is over 60 characters")
    if not tool.description:
        out.append("all: no description")
    elif len(tool.description) > 1024:
        out.append(f"openai: description is {len(tool.description)} characters (max 1024)")
    schema = tool.input_schema
    if schema.get("type") != "object":
        out.append("all: input schema is not an object")
    _walk(schema, name, out)
    if tool.output_schema:
        out.append("gemini: has an output schema (gemini-cli rejects some)")
    return out
