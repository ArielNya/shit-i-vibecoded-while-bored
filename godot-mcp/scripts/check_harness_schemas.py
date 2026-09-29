"""Check every tool definition against the rules of the major MCP clients.

    uv run python scripts/check_harness_schemas.py [--server-name godot]

Exits non-zero on any problem (run it before pushing). The server name matters because clients
prefix tool names with it (Claude: mcp__<server>__<tool>, Cursor: 60-char limit)."""

import argparse
import asyncio
import json
import sys

from godot_mcp import compat
from godot_mcp.server import create_server


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", default=compat.SERVER_NAME)
    args = parser.parse_args()
    tools = await create_server().list_tools()
    found = {t.name: compat.problems(t, args.server_name) for t in tools}
    bad = {name: p for name, p in found.items() if p}
    size = sum(len(json.dumps(t.input_schema)) + len(t.description or "") for t in tools)
    print(
        f"{len(tools)} tools, ~{size // 4} tokens of definitions, server name '{args.server_name}'"
    )
    for name, items in bad.items():
        for item in items:
            print(f"  {name}: {item}")
    print("OK: portable to Claude, OpenAI/Codex, Gemini, Cursor, VS Code" if not bad else
          f"{len(bad)} tool(s) with problems")  # fmt: skip
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
