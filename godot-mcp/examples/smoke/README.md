# Harness smoke tests

Run on 2026-09-28 against a headless Godot 4.7.2 editor with the demo project
(`tests/fixtures/demo_project`), godot-mcp 0.1.0 over stdio and over Streamable HTTP
(`--http`, bearer token). "Model run" means a real model drove the tools; "connects"
means the client's own MCP code connected and discovered the tools (no model: no API
key for that vendor in the test environment).

| Client | Version | stdio | HTTP | What was checked |
| --- | --- | --- | --- | --- |
| Claude Code | 2.1.283 | ✓ model run | ✓ model run | 52 tools listed; the model chained 6 tools (below) |
| Gemini CLI | 0.61.0 | ✓ connects | ✓ connects | `gemini mcp list` → Connected (needs a trusted folder) |
| opencode | 1.18.33 | ✓ connects | ✓ connects | `opencode mcp list` → connected |
| MCP Inspector CLI (TypeScript SDK) | latest | ✓ | ✓ | `tools/list` (52) and `tools/call` with arguments; 401 without a token |
| Codex CLI | 0.158.0 | config OK | config OK | `codex mcp list` accepts both entries; not connected (no key) |

Not run here (no way to drive them headless): Claude Desktop, Cursor, VS Code,
Windsurf, Zed, Cline, JetBrains AI, dsh. Their configs follow each client's documented
format. The schema rules they impose are checked by `scripts/check_harness_schemas.py`.

Also covered by the test suite (`tests/integration/test_transports.py`): the MCP
protocol versions 2024-11-05, 2025-03-26, 2025-06-18 and 2025-11-25 (raw JSON-RPC
handshakes) and 2026-07-28 (SDK client), over stdio and HTTP, plus a server started
with an empty environment.

## Claude Code, stdio

Prompt: *"Using only the godot MCP tools: (1) get the project info and report the
project name and main scene; (2) run get_diagnostics on res://scripts/broken.gd and
list the error messages; (3) run the project, wait 30 frames, and report the Player
node's live position; then stop the project."*

Tool calls: `get_project_info` → `get_diagnostics {"path": "res://scripts/broken.gd"}`
→ `run_project` → `wait_for {"until": "frames", "frames": 30}` →
`get_live_properties {"node": "Player", "filter": "position"}` → `stop_project`.

Answer (verbatim):

> Project: "MCP Demo", main scene res://scenes/main.tscn.
> broken.gd errors: line 4 col 19 String assigned to int variable "count" (two related errors), and line 5 col 2 undefined_helper() not found.
> Ran the project, waited 30 frames (~0.49s).
> Player's live position: Vector2(100, 7431.5796) — that Y is way off, likely falling/no floor collision.
> Stopped the project.

(Correct: the demo scene has no floor.)

## Claude Code, HTTP

Prompt: *"search the docs for how to move a CharacterBody2D, then read the full docs of
the method you'd use and quote its signature."* Tool calls: `search_docs` (twice) →
`get_class_docs {"class_name": "CharacterBody2D", "member": "move_and_slide"}`. Answer
quoted `func CharacterBody2D.move_and_slide() -> bool`.

Its first query, "move slide CharacterBody2D", found nothing because every word had to
be in the member's name. Fixed: words may also match the member's class, so that query
now ranks `CharacterBody2D.move_and_slide` first.
