# godot-mcp

MCP server that lets AI agents inspect, edit, run and debug a live **Godot 4.7+**
project — from any major MCP harness (Claude Code, Claude Desktop, Codex CLI,
Gemini CLI, Cursor, VS Code / Copilot, Windsurf, Zed, opencode, Cline, JetBrains AI,
dsh, …).

**Status: planning.** Nothing is implemented yet — see [`PLAN.md`](PLAN.md) for the
architecture, tool surface, harness-compatibility strategy and milestones.

In short: a Python MCP server (stdio or Streamable HTTP) talks over localhost to a
GDScript editor plugin, which in turn reaches the running game through Godot's own
debugger channel, so the agent can build scenes, write scripts, press Play, read the
errors, look at screenshots and fix things in a loop.
