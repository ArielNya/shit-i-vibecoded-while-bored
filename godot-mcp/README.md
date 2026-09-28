# godot-mcp

MCP server that lets AI agents inspect, edit, run and debug a live **Godot 4.7+**
project. It's meant to work with any MCP client (Claude Code, Claude Desktop, Codex CLI,
Gemini CLI, Cursor, VS Code / Copilot, Windsurf, Zed, opencode, dsh, …).

**Status: M0–M2 done.** The agent can explore the project, read and **edit** scenes
(nodes, properties, signals, groups, instancing, save-branch-as-scene), **write**
scripts and get the editor's errors and warnings back right away, navigate code
(definitions, references, symbols), look up the Godot 4.7 API, screenshot the editor,
and undo its own changes. Running and play-testing the game comes in M3. See
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
- **Values** are plain JSON where possible. Engine types are written as GDScript
  literals (`"Vector2(100, 200)"`, `"Color(1, 0, 0, 1)"`). Resources are
  `{"_type": "Resource", "class": "...", "path": "res://..."}`.

## Requirements

- Godot **4.7** or newer (standard or .NET build)
- [uv](https://docs.astral.sh/uv/) (it fetches Python 3.11+ automatically)

## Setup

### 1. Add the plugin to your Godot project

Copy [`addon/addons/godot_mcp`](addon/addons/godot_mcp) into your project so it ends up
at `res://addons/godot_mcp/`:

```bash
git clone https://github.com/ArielNya/shit-i-vibecoded-while-bored.git
cp -r shit-i-vibecoded-while-bored/godot-mcp/addon/addons/godot_mcp /path/to/your/project/addons/
```

Then in Godot: *Project → Project Settings → Plugins* → enable **Godot MCP**. An **MCP**
dock appears that shows `● Listening on 127.0.0.1:9080`. No token setup is needed: the
plugin writes a private token file and the server reads it (see [Security](#security)).

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

The server speaks plain stdio MCP, and its tool schemas are kept to what every major
client accepts (checked by `tests/unit/test_schemas.py`). The configs below follow each
client's documented format. **None has been smoke-tested end to end in that client
yet.** That is milestone M4, and each entry will be marked verified once it has been.

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
<summary><b>Claude Desktop</b></summary>

*Settings → Developer → Edit Config* (`claude_desktop_config.json`):

```json
{ "mcpServers": { "godot": { "command": "uvx", "args": ["--from", "SERVER_SPEC", "godot-mcp"] } } }
```

Restart Claude Desktop afterwards.
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add godot -- uvx --from "SERVER_SPEC" godot-mcp
```

or in `~/.codex/config.toml`:

```toml
[mcp_servers.godot]
command = "uvx"
args = ["--from", "SERVER_SPEC", "godot-mcp"]
tool_timeout_sec = 120
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

`~/.gemini/settings.json` (or `.gemini/settings.json` in the project):

```json
{ "mcpServers": { "godot": { "command": "uvx", "args": ["--from", "SERVER_SPEC", "godot-mcp"] } } }
```
</details>

<details>
<summary><b>Cursor</b> / <b>Windsurf</b></summary>

Cursor: `.cursor/mcp.json` in the project (or `~/.cursor/mcp.json`). Windsurf:
`~/.codeium/windsurf/mcp_config.json`. Both use the same shape:

```json
{ "mcpServers": { "godot": { "command": "uvx", "args": ["--from", "SERVER_SPEC", "godot-mcp"] } } }
```

Cursor slows down with many tools across servers (godot-mcp has 40). If needed, trim
with `"env": {"GODOT_MCP_TOOLSETS": "project,scene,edit,script"}`.
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

`.vscode/mcp.json`:

```json
{ "servers": { "godot": { "type": "stdio", "command": "uvx", "args": ["--from", "SERVER_SPEC", "godot-mcp"] } } }
```
</details>

<details>
<summary><b>opencode</b></summary>

`opencode.json`:

```json
{ "mcp": { "godot": { "type": "local", "command": ["uvx", "--from", "SERVER_SPEC", "godot-mcp"], "enabled": true } } }
```
</details>

<details>
<summary><b>DeepSeek Harness (dsh)</b></summary>

One entry in `cordis.patch.yml`. dsh starts servers with a scrubbed environment, so give
the full `uvx` path and `HOME`:

```yaml
- id: mcp-godot
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: godot
    transport: stdio
    command: /full/path/to/uvx
    args: ['--from', 'SERVER_SPEC', 'godot-mcp']
    env:
      HOME: /home/you
```
</details>

<details>
<summary><b>Any other MCP client</b></summary>

Run `uvx --from SERVER_SPEC godot-mcp` as a stdio server. Pass settings as environment
variables (below).
</details>

## Configuration

Server (environment variables):

| Variable | Default | |
| --- | --- | --- |
| `GODOT_MCP_PORT` / `GODOT_MCP_HOST` | `9080` / `127.0.0.1` | where the editor plugin listens |
| `GODOT_MCP_TOKEN` | *(token file)* | only if you set a custom token in the plugin |
| `GODOT_MCP_TIMEOUT` | `30` | seconds per call |
| `GODOT_MCP_TOOLSETS` | all | comma-separated subset: `project,scene,edit,script,docs,view` |
| `GODOT_MCP_LSP_PORT` / `GODOT_MCP_LSP_HOST` | from the editor | override the GDScript language server address |

Plugin: *Editor → Editor Settings → Godot Mcp* has `port`, `auto_start`,
`require_token` and `token`. For scripted launches, arguments after `--` override
them: `godot -e --path proj -- --mcp-port=9081 --mcp-token=… --mcp-no-auth`. The
matching environment variables are `GODOT_MCP_PORT`, `GODOT_MCP_TOKEN` and
`GODOT_MCP_NO_AUTH=1`. If you start the editor with `--lsp-port N`, also pass
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
- The server's instructions tell the model that project contents are data, not
  instructions.

## Development

```bash
cd godot-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest tests/unit -q                              # no Godot needed
GODOT_BIN=/path/to/godot uv run pytest tests/integration -q
```

The integration tests copy [`tests/fixtures/demo_project`](tests/fixtures/demo_project)
plus the plugin to a temp folder, open it in a real headless editor and drive every
tool through an MCP client. The screenshot tests run the editor with a window under
`xvfb-run` (Mesa software OpenGL) and are skipped if `xvfb-run` is missing. To hack on
the plugin itself, open [`addon/`](addon/) in Godot; it's a tiny project with the
plugin enabled.
