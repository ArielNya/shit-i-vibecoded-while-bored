# roblox-mcp

A companion to **Roblox Studio's built-in MCP server**. Studio's server works on the
live session: instances, scripts, `execute_luau`, play-testing, input, screenshots,
asset search and insert. This server covers what it can't do: the game project on
disk (Rojo), type-checking and linting, tests, uploading local assets, publishing,
and offline Engine API docs. It needs no Studio, so it also runs on Linux and in CI.

Status: **M7** (the `--wrap-studio` single-server mode, Rojo projects and live sync, type checking and formatting, tests, asset
uploads, cloud Luau runs, data stores, publishing, offline Engine API docs, and the
`roblox-studio` agent skill with references and tested recipes). Open Cloud features are
tested against a fake server only so far, and nothing has been run inside Studio yet.
See [`PLAN.md`](PLAN.md) for the roadmap.

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

### One server instead of two (`--wrap-studio`)

roblox-mcp can start Studio's server itself and serve its tools next to its own, so the
client needs one entry. Calls pass through unchanged except where the two servers
conflict: `multi_edit` on a script Rojo syncs is refused (with the file to edit),
Edit-mode `execute_luau` is wrapped in an undo recording, a missing `studio_id` is filled
in when there's one Studio (or one matching `ROBLOX_PLACE_ID`), play-testing warns when
Rojo isn't serving (and waits for fresh file changes to sync), and `insert_asset` of an
upload still in moderation (from `assets.lock.json`) is flagged or refused if rejected.

```sh
claude mcp add roblox -- uvx --from /path/to/roblox-mcp roblox-mcp --project /path/to/your-game --wrap-studio
```

Studio's launcher is found where Studio installs it; `--studio-mcp "<command>"` overrides.
If it can't start, roblox-mcp logs why and serves its own tools. Tested against a stand-in
server with the documented tool names; not yet with Studio itself.

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
| `--allow-publish` | `ROBLOX_MCP_ALLOW_PUBLISH=1` | off: adds `publish_place`, `run_luau_cloud place="live"` |
| `--allow-datastore-writes` | `ROBLOX_MCP_ALLOW_DATASTORE_WRITES=1` | off: adds `datastore_set` |
| `--wrap-studio` | `ROBLOX_MCP_WRAP_STUDIO=1` | off: serve Studio's MCP tools through this server |
| `--studio-mcp` | `ROBLOX_MCP_STUDIO_MCP` | Studio's install location |

The code tools need the toolchain: in a game project, `rokit install` (it reads the
`rokit.toml` that `init_project` writes). Tools are looked up in `ROBLOX_MCP_BIN_DIR`, then
`PATH`. On Linux without rokit (CI, sandboxes),
`uv run python scripts/install_toolchain.py <dir>` downloads the pinned versions.

Open Cloud reads `ROBLOX_API_KEY`, `ROBLOX_UNIVERSE_ID`, `ROBLOX_PLACE_ID` and, for cloud
test runs, `ROBLOX_TEST_PLACE_ID` (a separate place: each run uploads a saved version to
it). The key is never logged or returned by a tool. Scopes for cloud tests:
`universe-places:write`, `universe.place.luau-execution-session:write` and `:read`.
Uploads need `asset:read` and `asset:write`, and an owner: `ROBLOX_CREATOR_USER_ID` or
`ROBLOX_CREATOR_GROUP_ID`. Data stores: `universe-datastores.control:list`,
`universe-datastores.objects:list`, `:read` (and `:update` for writes). Publishing:
`universe-places:write`.

## Tools

| Tool | What it does |
| --- | --- |
| `get_project_info` | Rojo or Studio-only project, Rojo tree, toolchain versions (rojo, luau-lsp, selene, stylua, lune, rokit), Open Cloud settings, where Studio's MCP server is installed |
| `init_project` | make the folder a Rojo project in Roblox's recommended structure, with `rokit.toml` pinning the toolchain; never overwrites |
| `build_place` | `rojo build` → `.rbxl` / `.rbxm` |
| `sync_status` | start, stop or check `rojo serve` so Studio's Rojo plugin gets file changes |
| `check_code` | luau-lsp type check + lints with Roblox's types (new type solver, requires resolved through the Rojo sourcemap); selene too if the project has a `selene.toml` |
| `format_code` | StyLua; returns the files it changed |
| `run_tests` | `*.spec.luau` specs locally under Lune (pure Luau), or in a real headless Roblox server through Open Cloud (`target="cloud"`, needs a separate test place) |
| `upload_asset` | upload a local model/image/audio/video/animation file with Open Cloud; returns the `rbxassetid://` and where to use it; unchanged files reuse their id (`assets.lock.json`) |
| `list_uploaded_assets` | the manifest: ids, moderation state (optionally refreshed), files changed since upload |
| `run_luau_cloud` | run Luau in a headless server on the latest version of the test place (`place="live"` needs `--allow-publish`) |
| `datastore_list` / `datastore_read` | list data stores and keys, read an entry (value, revision, etag) |
| `datastore_set` | **opt-in** (`--allow-datastore-writes`): write one entry, keeping its users and attributes; pass the etag you read |
| `publish_place` | **opt-in** (`--allow-publish`): upload a place file as a Saved or Published version; refuses Rojo builds that would drop the world |
| `get_api_docs` | Engine API reference for Studio 0.740, offline: `Part`, `Workspace:Raycast` (through inheritance), `Enum.Material`, `task.wait`, `wait` (with its deprecation note) |
| `search_api` | find classes and members by name or summary words |
| `read_guide` | the `roblox-studio` skill and its references, for clients that don't load skills |

## Agent skill

[`src/roblox_mcp/skills/roblox-studio/`](src/roblox_mcp/skills/roblox-studio/) teaches
an agent to use both servers together: orient (`studio_id`, Rojo or not), which tool
for what, undoable edits, client/server structure, remote validation, modern Luau,
deprecated APIs, text filtering, data saving; plus recipes (obby, round-based game,
inventory with saved data) that CI type-checks and tests. It works with Studio's server
alone too.

Claude Code: copy or link the folder into your skills directory.

```sh
ln -s /path/to/roblox-mcp/src/roblox_mcp/skills/roblox-studio ~/.claude/skills/roblox-studio
```

Other agents: point them at `SKILL.md`, or they can read the same text through
`read_guide`.

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python scripts/install_toolchain.py ~/.cache/roblox-mcp/bin  # for tests/integration
ROBLOX_MCP_BIN_DIR=~/.cache/roblox-mcp/bin uv run pytest -q
uv run python scripts/check_harness_schemas.py
```

Evals (the same tasks with and without the skill, graded on type errors, deprecated APIs,
specs and task-specific safety checks; needs `claude` on PATH, costs a few dollars):

```sh
ROBLOX_MCP_BIN_DIR=~/.cache/roblox-mcp/bin uv run python evals/run_evals.py --runs 2
```

Results land in `evals/results/`.

Updating the API reference (a sparse checkout of `content/en-us/reference/engine` from
[Roblox/creator-docs](https://github.com/Roblox/creator-docs) is enough):

```sh
uv run python scripts/build_api_index.py /path/to/creator-docs
```
