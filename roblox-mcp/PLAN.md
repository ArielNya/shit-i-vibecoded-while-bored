# roblox-mcp — plan

Goal: an AI agent in any MCP harness can **build a whole Roblox game**: write and
type-check Luau, shape the DataModel, bring in assets from disk, play-test, run
tests, and publish. Paired with an **agent skill** that teaches the agent to do it
the way an experienced Roblox developer would.

Target: **Roblox Studio 0.740** (week of 2026-09-21) and the Engine API reference
at [`Roblox/creator-docs`](https://github.com/Roblox/creator-docs) `0b817b5`
(2026-09-26, `reference/engine/STUDIO_VERSION` = `0.740.19`). Roblox ships weekly,
so the pin is bumped by a script (§7), not by hand.

Status: **M0 done** (see §8 notes). Next: M1 (docs grounding + skill v0).

---

## 1. The finding that shapes everything

**Studio already has a built-in MCP server** (Assistant → … → Manage MCP Servers →
*Enable Studio as MCP server*; stdio; Windows `%LOCALAPPDATA%\Roblox\mcp.bat`, macOS
`RobloxStudio.app/Contents/MacOS/StudioMCP`). The old
`Roblox/studio-rust-mcp-server` was archived 2026-04-03 in its favour. It exposes:

| Area | Built-in tools |
| --- | --- |
| Scripts | `script_read`, `multi_edit` (creates if missing), `script_search`, `script_grep` |
| DataModel | `search_game_tree`, `inspect_instance`, `subagent` (`explore`, `playtest`) |
| Luau | `execute_luau` (`datamodel_type` = Edit / Server / Client) |
| Play | `get_studio_state`, `start_stop_play`, `get_console_output`, `screen_capture` |
| Input | `character_navigation`, `user_keyboard_input`, `user_mouse_input` |
| Assets | `search_asset`, `insert_asset`, `upload_image` (URLs only), `store_image`, `generate_mesh`, `generate_material`, `generate_procedural_model`, `wait_job_finished` |
| Docs | `http_get` (Roblox docs allowlist), `skill` |
| Sessions | `list_roblox_studios`; every call takes `studio_id` |

`execute_luau` in Edit mode can already do *any* instance edit: create, reparent,
set properties, attributes, tags, lighting, terrain. Writing another Studio
plugin with 60 structured tools would duplicate Roblox and chase its weekly releases.

**So we don't build a second Studio bridge.** We build the pieces it lacks and
a skill that drives both servers:

| Gap in the built-in server | Who fills it |
| --- | --- |
| Code lives only inside the place: no files, no git, no diffs | **roblox-mcp** + Rojo |
| No type checker / linter / formatter feedback | **roblox-mcp** (luau-lsp, selene, StyLua) |
| No unit tests, nothing runs without Studio open | **roblox-mcp** (Lune; Open Cloud Luau Execution) |
| Can't import local files (FBX/glTF/rbxm/PNG/OGG/MP3); `upload_image` takes URLs | **roblox-mcp** (Open Cloud Assets API) → built-in `insert_asset` |
| No publish, no DataStores, no place versions | **roblox-mcp** (Open Cloud) |
| Docs only while Studio is connected, fetched live | **roblox-mcp** (pinned, offline Engine API reference) |
| The agent doesn't know how to combine it all, or modern Roblox idioms | **skill** |

Challenge: if you only ever work Studio-only, no git, no tests, the skill alone
(§5) covers you and the server is optional. The plan keeps them separable.

---

## 2. Architecture

```
┌──────────────┐  stdio  ┌───────────────────────────┐
│ Claude Code, │ ──────▶ │ Roblox_Studio (built-in)  │ ─▶ open Studio session(s)
│ Codex, Gemini│         └───────────────────────────┘        ▲
│ Cursor, VSC… │  stdio  ┌───────────────────────────┐        │ Rojo live sync
│  + skill     │ ──────▶ │ roblox-mcp (this project) │ ─▶ rojo serve ──┘
└──────────────┘  /HTTP  │  Python, no Studio deps   │ ─▶ luau-lsp / selene / StyLua / Lune
                         │                           │ ─▶ apis.roblox.com (Open Cloud)
                         └───────────────────────────┘
```

- **Python, `mcp` SDK 2.x, `uv`/`ruff`/`pytest`**, same as `godot-mcp` and
  `blender-mcp`. Copy their transport, schema-compat checker (`compat.py`) and
  config-by-flag-or-env code; don't share a package (repo convention).
- **CLI tools, not reimplementations.** Rojo 7.7, luau-lsp 1.70, selene 0.31,
  StyLua 2.5, Lune 0.10, jest-lua 3.10, pinned in the game project's
  `rokit.toml`. `roblox-mcp` shells out to them and parses their JSON output.
- **Two project modes**, detected, never asked:
  - **Rojo mode** (`default.project.json` present): code is files, and Rojo
    syncs it into Studio. The agent edits `.luau` with its own file tools, never
    `multi_edit` (Rojo would overwrite it). World and instances are still built in
    Studio via `execute_luau`, or as `.model.json` / `.rbxm` files when they belong
    in git.
  - **Studio mode** (no project file): built-in tools only for code;
    `roblox-mcp` still gives docs, assets, publish, and can `rojo init` a
    project from what's in the place when the user wants git.
- **No Studio on Linux.** Studio runs only on Windows and macOS; these cloud
  sessions are Linux. Everything in `roblox-mcp` must work without Studio, which
  is also what makes it testable here and in CI.

---

## 3. Tool surface (`roblox-mcp`)

Small on purpose, ~16 tools. Names don't collide with the built-in ones.

### 3.1 `project`
| Tool | Purpose |
| --- | --- |
| `get_project_info` | mode (Rojo/Studio), project tree from `*.project.json`, toolchain versions, missing tools, Open Cloud key present (scopes checked from M4, when a tool first uses the key), where Studio's built-in server is installed |
| `init_project` | `rojo init` + `rokit.toml` + `selene.toml` (`std = "roblox"`) + `.luaurc` (`--!strict` default, aliases) + `stylua.toml`; idempotent |
| `build_place` | `rojo build` → `.rbxl` / `.rbxm` in the project's `build/` |
| `sync_status` | is `rojo serve` running, port, sourcemap fresh; can start/stop it |

### 3.2 `code`
| Tool | Purpose |
| --- | --- |
| `check_code` | `rojo sourcemap` → `luau-lsp analyze` (Roblox definitions for Studio 0.740, new type solver) + `selene`; one list of `file:line:col severity code message` |
| `format_code` | `stylua` on files or the project; returns changed files |
| `run_tests` | `jest-lua` specs: pure modules under Lune locally; `target="cloud"` runs the built place via Open Cloud Luau Execution (real engine, headless, ≤5 min) and returns structured pass/fail + logs |

### 3.3 `assets`
| Tool | Purpose |
| --- | --- |
| `upload_asset` | local file (`.fbx .gltf .glb .rbxm .rbxmx .png .jpg .tga .bmp .ogg .mp3 .wav`) → Open Cloud Assets API → polls the operation → `rbxassetid://…`. Then the agent calls the built-in `insert_asset` |
| `list_uploaded_assets` | the project's `assets.lock.json` manifest: path, content hash, asset id; skips re-uploading unchanged files |

### 3.4 `cloud`
| Tool | Purpose |
| --- | --- |
| `publish_place` | upload a built `.rbxl` as a Saved or Published version; **off unless enabled** |
| `run_luau_cloud` | Open Cloud Luau Execution against a place version; returns output/logs |
| `datastore_read` / `datastore_list` | read-only DataStore inspection (entries, keys, versions); writes are an explicit opt-in toolset |

### 3.5 `docs`
| Tool | Purpose |
| --- | --- |
| `get_api_docs` | class / datatype / enum / global / library from the pinned `creator-docs` YAML: members, types, security, tags (`Deprecated`, `Yields`, `NotReplicated`), descriptions → Markdown |
| `search_api` | fuzzy search over names + summaries ("raycast" → `WorldRoot:Raycast`, `RaycastParams`) |
| `read_guide(topic)` | curated notes that ship with the skill (§5), also as MCP resources for harnesses that show them |

The docs index is built at package build time from the pinned commit (~1,200 YAML
files) and shipped in the wheel: no network, no Studio.

---

## 4. Safety

- Open Cloud API key from `ROBLOX_API_KEY` only, never logged or returned. The tool
  says which **scopes** are missing instead of failing opaquely.
- `publish_place`, DataStore writes and `run_luau_cloud` against a *Published*
  version are separate toolsets, **off by default** (`--toolsets +publish`).
  Publishing is what players see.
- File tools confined to the project root; the uploader reads only files under
  it (or an explicit `--asset-dir`), rejects symlink escapes and `..`.
- Uploads are idempotent by content hash (no duplicate assets, no wasted
  moderation queue).
- Tool results return file and log contents as data; descriptions carry no
  instructions (place scripts can contain hostile text).
- Rojo `serve` binds to localhost only.

---

## 5. The skill: `skills/roblox-studio/`

A standard agent skill (`SKILL.md` + `references/`). It works with the built-in
server alone, and gets more capable when `roblox-mcp` is connected. Written for
Studio 0.740; every reference file cites the `creator-docs` path it came from.

**`SKILL.md`** (short, the rules the agent must never skip):
1. **Orient first.** `list_roblox_studios` → pick `studio_id` → `get_studio_state`
   → `get_project_info` (mode). Never guess a `studio_id`.
2. **Which tool for what**: a routing table between the two servers, e.g. code in
   Rojo mode = files + `check_code`, never `multi_edit`; world edits =
   `execute_luau` Edit; local model = `upload_asset` → `insert_asset`.
3. **Edits are undoable.** Every Edit-mode `execute_luau` wraps its change in
   `ChangeHistoryService:TryBeginRecording` / `FinishRecording` (template
   provided) so the human can Ctrl+Z the agent.
4. **Client/server boundary.** Where each script type runs (`Script`
   `RunContext`, `LocalScript`, `ModuleScript`), what replicates, and
   **never trust the client** (validate every `RemoteEvent` arg on the server).
5. **The loop:** write → `check_code` → play (`start_stop_play`) →
   `get_console_output` + `screen_capture` + input tools → fix → stop. Use the
   built-in `playtest` subagent for longer scenarios.
6. **Modern Luau only:** `--!strict`, the new type solver, `task.*`,
   `Attributes`, `CollectionService` tags, `:GetPropertyChangedSignal`. A
   deprecated-API table (`wait`/`spawn`/`delay` → `task.*`, `BodyVelocity` →
   `LinearVelocity`, `Instance.new(class, parent)`, `LoadAnimation` on Humanoid →
   `Animator`, …) generated from the docs' `Deprecated` tags plus a hand list.

**`references/`** (read on demand): `project-layout.md` (services, where things
go, Rojo tree), `luau-types.md`, `networking.md` (remotes, rate limits,
replication), `ui.md` (ScreenGui, UIListLayout, scaling across devices),
`physics-and-characters.md`, `data.md` (DataStores, session locking,
`UpdateAsync`), `assets.md` (import rules, mesh/texture limits, packages),
`performance.md` (StreamingEnabled, instance counts, MicroProfiler),
`testing.md` (jest-lua, cloud runs), `publishing.md`, `recipes/` (obby,
round-based game, tycoon, inventory with DataStore).

Evaluated with `skill-creator`-style evals: same tasks with and without the skill,
graded on "runs without errors", "server-authoritative", "no deprecated APIs".

---

## 6. Harness compatibility

Carried over from `godot-mcp` §6: stdio default, Streamable HTTP with bearer token,
schema checker in CI (Gemini/OpenAI-strict rules, name length with the
`mcp__roblox__` prefix), toolset presets, every option as flag + env var.
The README gives **both** server configs side by side for Claude Code, Claude
Desktop, Codex, Gemini CLI, Cursor, VS Code, and says per client whether it was
verified.

---

## 7. Testing

- **Unit (here, Linux):** tool logic with fake CLIs and a fake Open Cloud (recorded
  responses); docs index; schema compat; manifest hashing.
- **Toolchain integration (here, Linux):** real Rojo/luau-lsp/selene/StyLua/Lune
  installed by `rokit` in the session hook; fixture game in
  `tests/fixtures/sample_game/` with deliberate type errors, lint hits and a
  failing jest-lua spec.
- **Open Cloud integration (CI, optional):** runs only when repo secrets
  `ROBLOX_API_KEY`, `ROBLOX_UNIVERSE_ID`, `ROBLOX_PLACE_ID` exist: build → upload
  test place → `run_tests target=cloud` → upload a tiny PNG. Note: this cloud
  container's network policy blocks some Roblox domains (`create.roblox.com`
  was); check `apis.roblox.com` before M3.
- **Studio (manual, Windows/macOS):** a scripted smoke task per milestone run by
  a human with both servers connected; transcripts in `examples/smoke/`. We
  never claim a Studio flow works without one.
- **Pin bump:** `scripts/bump_roblox.py` moves the `creator-docs` commit, luau-lsp
  definitions and tool pins, rebuilds the docs index and the deprecated table,
  and diffs the API (added / deprecated members) into the changelog.

---

## 8. Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| **M0** ✅ | Skeleton | uv project; `get_project_info`; stdio + HTTP; schema checker; README with both server configs |
| **M1** | Docs grounding | `get_api_docs`, `search_api`, deprecated table from pinned `creator-docs`; **skill v0** (`SKILL.md` + 3 references) usable with the built-in server alone |
| **M2** | Project & code | `init_project`, `build_place`, `sync_status`, `check_code`, `format_code` on the fixture game; session hook installs the toolchain |
| **M3** | Tests | `run_tests` local (Lune) and cloud (Luau Execution); acceptance: the agent fixes the fixture's failing spec using only tools |
| **M4** | Assets | `upload_asset` + manifest for models, images, audio; acceptance: a local `.glb` ends up in Studio via `insert_asset` (manual Studio smoke) |
| **M5** | Cloud ops | `publish_place`, `run_luau_cloud`, DataStore read (write opt-in) |
| **M6** | Skill complete | all references + recipes; evals with vs. without skill; full-game smoke (small obby: build, code, test, publish to a private place) in Claude Code + one other harness |
| **M7** | Wrapper | §9: `--wrap-studio` proxies the built-in server behind ours; the conflict rules there, each with a test against a fake built-in server; manual Studio smoke with only `roblox-mcp` configured |
| **M8** | Stretch, only if M6 shows a real gap | own Studio plugin for what `execute_luau` can't do; multi-place universes; Packages; `.rbxm` insert without uploading |

### M0 notes

- `get_project_info` is the only tool: mode (`rojo` if a `*.project.json` exists,
  `default.project.json` preferred), the Rojo tree (class + synced path, 3 levels),
  toolchain versions via `--version` (null when missing), Open Cloud env presence
  (the key's value never appears), and Studio's `StudioMCP` / `mcp.bat` path
  (null on Linux).
- Transport, bearer auth and schema checks are `godot-mcp`'s, copied. HTTP always
  needs a token (`--http-token`); there's no shared token file since there's no
  plugin to create one. Port 7090, so it can run next to `godot-mcp` on 7080.
- No toolsets/presets yet: one tool. They come back when the tool count needs them.
- Tested: unit tests, plus the server as a separate process over stdio (with an
  empty environment) and HTTP (with and without the token). Not yet tried in a
  harness next to Studio's server.

---

## 9. The wrapper (M7): managing conflicts between the two servers

Until M7 the two servers are configured side by side and the skill (§5) keeps
them out of each other's way. Rules in a skill are requests; M7 makes the
important ones enforced.

`roblox-mcp --wrap-studio` starts the built-in server (`StudioMCP` /
`mcp.bat`, auto-detected or `--studio-mcp <path>`) as a **child process**, talks
to it as an MCP client over stdio, and lists its tools next to ours. The user
configures one server. Tool lists are fetched from the child at startup and on
its `tools/list_changed`, so new or renamed Roblox tools pass through with no
code change. Off by default; without Studio (Linux) it logs one line and serves
our tools only.

Calls pass through untouched, except where the servers can conflict:

| Conflict | What the wrapper does |
| --- | --- |
| `multi_edit` on a script Rojo owns (Rojo would overwrite it on the next sync) | refuse, naming the file to edit instead (path from the sourcemap) |
| Play-testing while Rojo still has unsynced file changes (the test runs old code) | before `start_stop_play`: if `rojo serve` runs, wait until Studio has the latest files (bounded), else warn in the result |
| `execute_luau` Edit changes not undoable | wrap the code in `ChangeHistoryService:TryBeginRecording` / `FinishRecording` unless it already records |
| Wrong Studio window (several open) | when `studio_id` is omitted and more than one Studio is connected, pick the one whose place ID matches the project, else refuse and list them |
| Inserting an uploaded asset still in moderation | `insert_asset` of an ID from our manifest that isn't approved yet → explain instead of failing opaquely |

Each rule is a small function over (tool name, arguments) → pass, rewrite, or
refuse, so rules can be added as smoke tests find new conflicts. Tested against a
fake child server implementing the built-in tools' names and schemas.

Not doing: renaming, merging or hiding the built-in tools. The skill and Roblox's
own docs describe them by their real names.

---

## 10. Open questions

- **Is a companion server the right call vs. replacing the built-in one?**
  Recommended yes (§1). Revisit at M6 with the smoke transcripts.
- **Wrapper and Studio's client indicator:** does Studio still show the
  connection (and does quick connect still work) when its server is a child of
  ours? Check at M7.
- **Local `.rbxm` into Studio without uploading:** can a plugin or `execute_luau`
  use `SerializationService` on bytes we pass in? If yes, a later tool can skip
  Open Cloud for rbxm. Verify in Studio 0.740.
- **Local meshes without uploading:** `EditableMesh` → `CreateMeshPartAsync`
  works in edit mode, but the result must be published to persist. Probably
  not worth it; upload is the supported path.
- **Rojo two-way sync** is experimental in 7.7; the skill assumes files → Studio
  only, and uses `rojo syncback` for a one-off Studio → files import.
- **PyPI name:** `roblox-mcp` is surely taken; pick one before the first release.
