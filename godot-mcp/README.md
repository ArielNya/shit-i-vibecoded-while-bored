# godot-mcp

MCP server that lets AI agents inspect, edit, run and debug a live **Godot 4.7+**
project. It's meant to work with any MCP client (Claude Code, Claude Desktop, Codex CLI,
Gemini CLI, Cursor, VS Code / Copilot, Windsurf, Zed, opencode, dsh, …).

**Status: M0–M7 done.** The agent can explore the project, read and **edit** scenes
(nodes, properties, signals, groups, instancing, save-branch-as-scene), **write**
scripts and get the editor's errors and warnings back right away, navigate code
(definitions, references, symbols), look up the Godot 4.7 API, screenshot the editor,
and undo its own changes. It can also **run the game and play-test it**: read its
output and runtime errors (with file:line and backtrace), inspect and tweak the live
scene, send input, wait for conditions, and take screenshots of the game. And it can
build **content**: resources (.tres), imported art/audio/fonts, TileSets from sprite
sheets, and tile levels painted from ASCII grids. Finally it can **ship and test**:
validate the whole project, run GUT / GdUnit4 unit tests and export presets, with or
without the editor open. It comes with **curated Godot 4.7 guides** and step-by-step
**skills** (2D platformer, 3D third-person, menus), and an opt-in `execute_gdscript`
escape hatch. It runs over
stdio or Streamable HTTP, and has been checked against real clients (see below). See
[`PLAN.md`](PLAN.md) for the roadmap.

```
AI client ──stdio──▶ godot-mcp (Python) ──TCP 127.0.0.1:9080──▶ Godot editor + "Godot MCP" plugin
                          └──────────────── LSP :6005 ─────────▶ (GDScript language server)
```

## Tools

| Toolset | Tools |
| --- | --- |
| `project` | `ping`, `get_project_info`, `list_files`, `search_files`, `get_project_settings`, `set_project_setting`, `get_input_map`, `edit_input_map` |
| `scene` | `get_scene_tree`, `get_node_properties` |
| `edit` | `open_scene`, `new_scene`, `save_scene`, `close_scene`, `add_node`, `remove_node`, `rename_node`, `move_node`, `duplicate_node`, `set_node_properties`, `list_signals`, `connect_signal`, `disconnect_signal`, `set_groups`, `save_branch_as_scene`, `undo`, `redo` |
| `script` | `read_script`, `get_diagnostics`, `write_script`, `edit_script`, `create_script`, `attach_script`, `detach_script`, `find_symbol`, `get_definition`, `get_references` |
| `docs` | `get_class_docs`, `search_docs` |
| `view` | `get_editor_screenshot` |
| `run` | `run_project`, `stop_project`, `get_run_status`, `get_output`, `get_runtime_errors`, `get_game_screenshot`, `get_live_tree`, `get_live_properties`, `set_live_properties`, `send_input`, `wait_for`, `get_performance` |
| `assets` | `create_resource`, `get_resource`, `set_resource_properties`, `import_asset`, `reimport`, `create_tileset`, `get_tiles`, `set_tiles` |
| `build` | `validate_project`, `run_tests`, `list_export_presets`, `export_project` |
| `guides` | `read_guide` |
| `exec` | `execute_gdscript` (off unless you allow it in Godot) |

Plus MCP **resources** (`godot://docs/<topic>`, `godot://skills/<name>`,
`godot://project`) and **prompts** (`make_prototype`, `fix_errors_loop`, `playtest`),
available whatever toolsets you pick.

- **`get_diagnostics`** asks the editor's own GDScript analyzer (through the built-in
  language server) for errors and warnings in one file or the whole project. You get the
  same messages the script editor shows, e.g. `4:19 Cannot assign a value of type
  "String" as "int".`
- **`get_class_docs` / `search_docs`** answer from the running engine's `ClassDB` plus
  the class reference. The agent sees the exact API of *your* Godot version, and your
  own `class_name` scripts too. Godot 3 names get a pointer to the Godot 4 name
  (`KinematicBody2D` → use `CharacterBody2D`).
- **Every change is one editor undo step** named `MCP: <tool>`, so you can Ctrl+Z it in
  Godot. The agent's `undo`/`redo` only touch its own changes. Like Ctrl+Z, they only
  act on the current scene and the global history, and they stop instead of reverting
  anything you did in the editor since. Scene edits reach the disk on `save_scene`;
  settings and scripts are saved right away.
- **Scripts:** `write_script`, `edit_script` and `create_script` reload the file in the
  editor and return fresh errors and warnings. They refuse to overwrite a script that
  has unsaved changes in Godot's script editor (`force=true` overrides), and they can't
  write scenes, `project.godot` or this plugin's own files.
- **`set_project_setting` / `edit_input_map`** save `project.godot`.
- **Assets and tiles:** `import_asset` copies a file (image, audio, font, model) into
  the project and imports it. The server reads the file itself, only from its asset
  folders (default: its working directory; `--asset-dir` adds others), so an agent
  can't pull arbitrary files off your disk. `create_tileset` turns a sprite sheet into
  a TileSet (empty cells skipped, optional full-tile collision). `set_tiles` paints a
  TileMapLayer from rows of characters plus a legend, e.g. `["  ==  ", "######"]` with
  `{"#": [2, 0], "=": [1, 0]}`, and `get_tiles` shows a layer the same way.
- **Running the game:** `run_project` presses Play in the editor. The game talks back
  through Godot's own debugger connection to a small **`McpRuntime` autoload**, which
  the plugin adds to your project (it does nothing unless the game was started from
  the editor, and it's left out of exported games). Script errors don't pause the game
  the way a normal debug run would; they're logged, and `get_runtime_errors` returns
  them with file:line and a backtrace. When the editor has no display, the game runs
  headless: input, live properties and waits work, but screenshots need a window.
  A typical play-test is `send_input` (hold `move_right` for 60 frames), then
  `get_live_properties` or `wait_for` a condition.
- **Build and test** run a separate headless Godot, so they don't block the editor.
  They also work **with no editor open**: point the server at the project
  (`--project`, or start it inside the project folder) and at Godot (`--godot-bin`, or
  have `godot` on `PATH`). With an editor connected, it reuses the editor's project and
  binary, and asks the editor to rescan first, so files changed behind its back count.
  - `validate_project` compiles every script and loads every scene and resource. It
    reports errors with file:line, plus references to missing files (including the
    main scene and autoloads).
  - `run_tests` runs **GUT** or **GdUnit4** (whichever is installed in `addons/`; both
    if both). It returns pass/fail counts and each failure's message with file:line.
  - `export_project` exports a preset. `release`/`debug` builds need the export
    templates; `pack` (a `.pck`/`.zip` of the game data) doesn't. The output must be
    inside the server's export folders (default: its working directory; `--export-dir`
    adds others). An export folder inside the project gets a `.gdignore`.
  - Without an editor, `get_class_docs` and `search_docs` answer from a headless Godot
    too (signatures only; descriptions come from the editor).
- **Guides and skills:** `read_guide` (and the same texts as resources) has short
  Godot 4.7 guides: Godot 3 → 4 pitfalls, movement recipes, physics layers, UI layout,
  scenes and signals, testing, exporting, and the tools' value format. It also has three
  skills, step-by-step playbooks that use these tools: `godot-2d-platformer`,
  `godot-3d-third-person` and `godot-ui-menu`. The tests compile every GDScript block in
  them against Godot 4.7.2. The skills are also plain Agent Skills folders
  ([`skills/`](skills/)), so clients that load skills can use them directly, e.g. copy
  `skills/<name>` into `~/.claude/skills/` or your game's `.claude/skills/` for Claude
  Code.
- **`execute_gdscript`** runs a GDScript snippet in the editor or in the running game
  and returns its prints and return value, with errors pointing at the snippet's lines.
  It's for the rare thing no other tool covers, and it's **off by default**: tick
  *Allow execute_gdscript* in the MCP dock (Editor Settings `godot_mcp/allow_execute`).
  It also refuses to run while token auth is off. Changes made this way aren't
  undoable, and an endless loop freezes the editor.
- **Values** are plain JSON where possible. Engine types are written as GDScript
  literals (`"Vector2(100, 200)"`, `"Color(1, 0, 0, 1)"`). Resources are
  `{"_type": "Resource", "class": "...", "path": "res://..."}`.

## Requirements

- Godot **4.7** or newer (standard or .NET build)
- [uv](https://docs.astral.sh/uv/) (it fetches Python 3.11+ automatically)

## Setup

### 1. Add the plugin to your Godot project

One command copies the plugin into your project (`addons/godot_mcp/`) and enables it.
Run it again after updating the server, so the plugin matches:

```bash
uvx --from "git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=godot-mcp" \
  godot-mcp install-addon /path/to/your/project
```

Or by hand: copy [`addon/addons/godot_mcp`](addon/addons/godot_mcp) to
`res://addons/godot_mcp/` and enable it in *Project → Project Settings → Plugins*.

Open the project in Godot (or *Project → Reload Current Project* if it was open). An
**MCP** dock appears that shows `● Listening on 127.0.0.1:9080`. No token setup is
needed: the plugin writes a private token file and the server reads it (see
[Security](#security)).

### 2. The server command

Every client runs the same command:

```bash
uvx --from "git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=godot-mcp" godot-mcp
```

- **From a clone** (for development): `uv run --directory /path/to/godot-mcp godot-mcp`.
- **Don't** use `uvx godot-mcp` on its own. The PyPI name hasn't been claimed by this
  project.
- **GUI apps:** desktop apps often don't inherit your shell's PATH. If the client can't
  find `uvx`, use its full path (`which uvx`, or `where uvx` on Windows).

Below, `SERVER_SPEC` stands for
`git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=godot-mcp`.
Ready-to-copy files with it filled in are in [`examples/`](examples/).

### 3. Register it with your client

The server speaks plain MCP over **stdio** (every client) or **Streamable HTTP**
(`--http`, see below). Its tool schemas keep to what every major client accepts;
`scripts/check_harness_schemas.py` checks that. What has actually been run (details
in [`examples/smoke/`](examples/smoke/)):

| Client | Status |
| --- | --- |
| Claude Code | **verified**: a model used the tools end to end, over stdio and HTTP |
| Gemini CLI, opencode | **connects** over stdio and HTTP and discovers the tools (no model run) |
| MCP Inspector (TypeScript SDK, which most IDE clients use) | **verified** tool listing and calls, stdio and HTTP |
| Codex CLI | config accepted by `codex mcp list`; not connected |
| Claude Desktop, Cursor, VS Code, Windsurf, Zed, Cline, JetBrains AI, dsh | untested; configs follow each client's docs |

Ready-to-copy files are in [`examples/`](examples/).

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add godot -s user -- uvx --from "SERVER_SPEC" godot-mcp
claude mcp list          # godot … ✓ Connected
```

Or check [`examples/claude-code.mcp.json`](examples/claude-code.mcp.json) into your game
repo as `.mcp.json`.
</details>

<details>
<summary><b>Claude Desktop</b>, <b>Cursor</b>, <b>Windsurf</b>, <b>Cline</b>, <b>JetBrains AI</b>, <b>Gemini CLI</b></summary>

All of these read the same `mcpServers` shape
([`examples/claude_desktop_config.json`](examples/claude_desktop_config.json)):

```json
{ "mcpServers": { "godot": { "command": "uvx", "args": ["--from", "SERVER_SPEC", "godot-mcp"] } } }
```

Where it goes: Claude Desktop *Settings → Developer → Edit Config*; Cursor
`.cursor/mcp.json` (or `~/.cursor/mcp.json`); Windsurf
`~/.codeium/windsurf/mcp_config.json`; Cline *MCP Servers → Configure*; JetBrains AI
*Settings → Tools → AI Assistant → MCP → As JSON*; Gemini CLI `~/.gemini/settings.json`
or `.gemini/settings.json` (Gemini only starts MCP servers in *trusted* folders).
Restart the app afterwards. GUI apps may need the full path to `uvx`.

With many servers Cursor slows down (godot-mcp has 66 tools): add
`"env": {"GODOT_MCP_TOOLSETS": "core"}` (37 tools) or `"minimal"` (13).
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add godot -- uvx --from "SERVER_SPEC" godot-mcp
```

or [`examples/codex.config.toml`](examples/codex.config.toml) in `~/.codex/config.toml`
(sets a longer `tool_timeout_sec` for game runs).
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

[`examples/vscode.mcp.json`](examples/vscode.mcp.json) as `.vscode/mcp.json`: a stdio
entry, plus an HTTP entry that prompts for the token.
</details>

<details>
<summary><b>opencode</b>, <b>Zed</b>, <b>dsh</b></summary>

[`examples/opencode.json`](examples/opencode.json) (`opencode.json`),
[`examples/zed.settings.json`](examples/zed.settings.json) (Zed `settings.json`,
`context_servers`), [`examples/dsh.cordis.patch.yml`](examples/dsh.cordis.patch.yml)
(dsh starts servers with an empty environment, so give the full `uvx` path; the server
needs nothing else).
</details>

<details>
<summary><b>Streamable HTTP</b> (one server shared by several clients, remote dev containers)</summary>

```bash
uvx --from "SERVER_SPEC" godot-mcp --http            # http://127.0.0.1:7080/mcp
```

Clients must send `Authorization: Bearer <token>`. The token is the one in the shared
token file (`~/.config/godot-mcp/token`), or your own with `--http-token`.
`--no-http-auth` turns auth off, and is only allowed on a loopback address.

```bash
claude mcp add --transport http godot http://127.0.0.1:7080/mcp \
  --header "Authorization: Bearer $(cat ~/.config/godot-mcp/token)"
```

HTTP configs for Claude Code, Gemini CLI, VS Code and Codex are in
[`examples/`](examples/) (`*.http.*`, `gemini-http.settings.json`, the commented Codex
entry). They read the token from `GODOT_MCP_HTTP_TOKEN`.
</details>

<details>
<summary><b>Windows / PowerShell (from a clone)</b></summary>

[`scripts/install.ps1`](scripts/install.ps1) runs the server straight out of this
clone (`uv run --directory`, no `uvx` fetch), pointed at a specific project, and
registers it for you:

```powershell
./scripts/install.ps1 -ProjectPath C:\games\my-game -Harness claude-code    # or claude-desktop / codex
```

`-ProjectPath` (the Godot project folder, passed to the server as `--project`) and
`-Harness` are the only inputs. Requires `uv` and, for the `claude-code`/`codex`
harnesses, that CLI on `PATH`.
</details>

<details>
<summary><b>Clients that don't show images to the model</b></summary>

Screenshots come back as MCP image content. If your client drops images, run the server
with `--image-mode file` (or `both`): the PNG is saved (under the project's `.godot/`
folder) and its path is returned, so an agent with file access can open it.
</details>

## Configuration

Server: each option is a flag and an environment variable (`godot-mcp --help`):

| Flag | Variable | Default | |
| --- | --- | --- | --- |
| `--godot-port` / `--godot-host` | `GODOT_MCP_PORT` / `GODOT_MCP_HOST` | `9080` / `127.0.0.1` | where the editor plugin listens |
| `--token` / `--token-file` | `GODOT_MCP_TOKEN` / `GODOT_MCP_TOKEN_FILE` | the shared token file | plugin token |
| `--timeout` | `GODOT_MCP_TIMEOUT` | `30` | seconds per editor call |
| `--toolsets` | `GODOT_MCP_TOOLSETS` | `all` (66) | presets `core` (37), `minimal` (13), and/or `project,scene,edit,script,docs,view,run,assets,build,guides,exec` |
| `--asset-dir` | `GODOT_MCP_ASSET_DIRS` | the working directory | folders `import_asset` may read files from (`os.pathsep`-separated) |
| `--export-dir` | `GODOT_MCP_EXPORT_DIRS` | the working directory | folders `export_project` may write to (`os.pathsep`-separated) |
| `--godot-bin` | `GODOT_BIN` | the editor's, else `godot` on `PATH` or a usual install place | Godot binary for tests, exports and no-editor mode |
| `--project` | `GODOT_MCP_PROJECT` | the editor's, else the nearest `project.godot` from the working directory up | project for tests, exports and no-editor mode |
| `--lsp-port` / `--lsp-host` | `GODOT_MCP_LSP_PORT` / `GODOT_MCP_LSP_HOST` | from the editor | GDScript language server |
| `--image-mode` | `GODOT_MCP_IMAGE_MODE` | `inline` | `file` / `both`: save screenshots as PNGs and return their paths |
| `--http`, `--http-port`, `--http-host` | `GODOT_MCP_HTTP_PORT` / `_HOST` | stdio; `7080`, `127.0.0.1` | Streamable HTTP |
| `--http-token`, `--no-http-auth` | `GODOT_MCP_HTTP_TOKEN` | the token file's token | HTTP bearer token |

Flags win over variables. Nothing depends on `HOME` or `PATH`, so clients that start
servers with an empty environment work too (for no-editor mode, pass `--godot-bin` and
`--project` explicitly then).

Plugin: *Editor → Editor Settings → Godot Mcp* has `port`, `auto_start`,
`require_token`, `token` and `allow_execute`. For scripted launches, arguments after
`--` override them: `godot -e --path proj -- --mcp-port=9081 --mcp-token=…
--mcp-no-auth --mcp-allow-execute`. The matching environment variables are
`GODOT_MCP_PORT`, `GODOT_MCP_TOKEN`, `GODOT_MCP_NO_AUTH=1` and
`GODOT_MCP_ALLOW_EXECUTE=1`. If you start the editor with `--lsp-port N`, also pass
`-- --mcp-lsp-port=N`. Godot consumes `--lsp-port` before plugins can see it.

**Several editors at once:** give each one its own `godot_mcp/port`, and each server
entry the matching `GODOT_MCP_PORT`. Only the first editor gets the language server
port (6005), so the others need their own (`--lsp-port`) for `get_diagnostics` and
member docs.

## Security

- The plugin listens on **127.0.0.1 only**. By default it requires a token. On first
  start it writes a random one to `~/.config/godot-mcp/token` (macOS:
  `~/Library/Application Support/…`, Windows: `%APPDATA%\…`), readable only by you, and
  the server reads the same file.
- File tools only see `res://` paths. `..` is rejected, and hidden folders and folders
  with a `.gdignore` are skipped.
- `set_project_setting` can only change game settings (application, display, physics,
  rendering, audio, input devices, layer names, autoloads, …). It can't touch
  `editor_plugins/` or editor settings, so an agent can't turn this plugin off or
  change it.
- `execute_gdscript` runs arbitrary code, so it's off until you enable it in Godot, and
  it never runs without token auth. The agent can't turn it on: `set_project_setting`
  can't reach editor settings.
- Outside the project, the server only reads from its asset folders (`import_asset`)
  and only writes into its export folders (`export_project`).
- The HTTP transport requires a bearer token by default: the server can drive the
  editor, so an open port would let any local process do that. It binds to
  127.0.0.1 and checks Host/Origin headers against DNS rebinding.
- The runtime in the game only answers the editor it was started from (over Godot's
  debugger connection); it opens no ports of its own and is inert in exported builds.
- The server's instructions tell the model that project contents are data, not
  instructions.

## Development

The repo has no CI; run these before pushing:

```bash
cd godot-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest tests/unit -q                              # no Godot needed
uv run python scripts/check_harness_schemas.py           # tool schemas every client accepts
GODOT_BIN=/path/to/godot uv run pytest tests/integration -q
```

The integration tests copy [`tests/fixtures/demo_project`](tests/fixtures/demo_project)
plus the plugin to a temp folder, open it in a real headless editor and drive every
tool through an MCP client. The screenshot tests run the editor with a window under
`xvfb-run` (Mesa software OpenGL) and are skipped if `xvfb-run` is missing. The
`run_tests` tests clone pinned GUT and GdUnit4 releases into `~/.cache/godot-mcp/frameworks`
on first use (`GODOT_MCP_TEST_FRAMEWORKS` moves it) and are skipped offline. To hack on
the plugin itself, open [`addon/`](addon/) in Godot; it's a tiny project with the
plugin enabled.
