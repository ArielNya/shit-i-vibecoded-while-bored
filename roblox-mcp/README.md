# roblox-mcp

A companion to **Roblox Studio's built-in MCP server**. Studio's server works on the
live session: instances, scripts, `execute_luau`, play-testing, input, screenshots,
asset search and insert. This server covers what it can't do: the game project on
disk (Rojo), type-checking and linting, tests, uploading local assets, publishing,
and offline Engine API docs. It needs no Studio, so it also runs on Linux and in CI.

Status: **M0** (skeleton: `get_project_info`, stdio + HTTP). See [`PLAN.md`](PLAN.md)
for the roadmap.

Targets Roblox Studio **0.740** (Sept 2026).

## Setup

Configure **both** servers in your MCP client.

**1. Studio's built-in server.** In Studio: Assistant → **…** → Manage MCP Servers →
turn on *Enable Studio as MCP server*. Use quick connect, or add it by hand:

| OS | Command |
| --- | --- |
| Windows | `cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat` |
| macOS | `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP` |

**2. This server** (needs [uv](https://docs.astral.sh/uv/)), pointed at your game
project folder:

```
uvx --from /path/to/roblox-mcp roblox-mcp --project /path/to/your-game
```

Claude Code, both at once:

```sh
claude mcp add Roblox_Studio -- /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
claude mcp add roblox -- uvx --from /path/to/roblox-mcp roblox-mcp --project /path/to/your-game
```

JSON clients (Claude Desktop, Cursor, Gemini CLI, …):

```json
{
  "mcpServers": {
    "Roblox_Studio": { "command": "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP" },
    "roblox": {
      "command": "uvx",
      "args": ["--from", "/path/to/roblox-mcp", "roblox-mcp", "--project", "/path/to/your-game"]
    }
  }
}
```

Verified: roblox-mcp over stdio and HTTP with the MCP SDK client (M0). Not yet
tried in any harness with Studio connected; that's the M2 smoke test.

## Options

Every option is a flag and an environment variable.

| Flag | Variable | Default |
| --- | --- | --- |
| `--project` | `ROBLOX_MCP_PROJECT` | current directory |
| `--http` | | stdio |
| `--http-host` | `ROBLOX_MCP_HTTP_HOST` | `127.0.0.1` |
| `--http-port` | `ROBLOX_MCP_HTTP_PORT` | `7090` |
| `--http-token` | `ROBLOX_MCP_HTTP_TOKEN` | required with `--http` |
| `--no-http-auth` | | loopback only |

Open Cloud (later milestones) reads `ROBLOX_API_KEY`, `ROBLOX_UNIVERSE_ID` and
`ROBLOX_PLACE_ID`. The key is never logged or returned by a tool.

## Tools

| Tool | What it does |
| --- | --- |
| `get_project_info` | Rojo or Studio-only project, Rojo tree, toolchain versions (rojo, luau-lsp, selene, stylua, lune, rokit), Open Cloud settings, where Studio's MCP server is installed |

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python scripts/check_harness_schemas.py
```
