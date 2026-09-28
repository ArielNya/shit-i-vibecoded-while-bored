# godot-mcp — plan

Goal: let an AI agent in **any major MCP harness** (Claude Code, Claude Desktop,
Codex CLI, Gemini CLI, Cursor, VS Code / Copilot, Windsurf, Zed, opencode, Cline,
JetBrains AI, dsh, …) **see**, **edit**, **run** and **debug** a live Godot project
well enough to build real games: create scenes, write GDScript, wire signals, run the
game, look at it, read the errors, fix them, repeat.

Target engine: **Godot 4.7** (current stable is 4.7.2, Aug 2026). Minimum supported:
4.7. The 4.8 dev snapshots run in a non-blocking CI job so we see breakage early.

Status: **planning** — nothing implemented yet.

---

## 1. Core constraints that drive the design

1. **The engine API only exists inside a Godot process.** Scene editing, undo,
   `ClassDB`, the resource filesystem — all of that lives in the running editor.
   MCP clients, meanwhile, spawn servers as stdio subprocesses (or connect over
   HTTP) and expect them to start instantly.
2. **There are two Godot processes, not one.** The *editor* owns the scene files;
   the *running game* is a separate process started by the editor. "Play the game
   and tell me why the player falls through the floor" needs both.
3. **Harnesses disagree on the details.** Tool-count caps, JSON Schema dialects,
   whether images reach the model, whether prompts/resources are supported,
   stdio vs. HTTP, scrubbed environments. The server has to work with the
   *lowest common denominator* and opt into richer features where available.

So — same split that worked for `blender-mcp`, plus a third piece for the game:

```
┌──────────────┐ stdio or   ┌─────────────────┐ TCP 127.0.0.1  ┌──────────────────────────────┐
│ Claude Code  │ Streamable │  MCP server      │ JSON-RPC 2.0   │  Godot EDITOR                │
│ Codex, Gemini│ HTTP       │  (Python, no     │ length-framed  │  addons/godot_mcp (@tool     │
│ Cursor, VSC… │ ─────────▶ │   Godot deps)    │ ─────────────▶ │  EditorPlugin, GDScript)     │
│              │ ◀───────── │                  │ ◀───────────── │   TCPServer polled in        │
└──────────────┘            │  + LSP client ───┼── :6005 ──────▶│   _process() → main thread   │
                            │  + headless CLI  │                │                              │
                            └─────────────────┘                │  EditorDebuggerPlugin ◀──┐   │
                                                                └──────────────────────────┼───┘
                                                                  EngineDebugger messages  │
                                                                ┌──────────────────────────┴───┐
                                                                │  RUNNING GAME                │
                                                                │  autoload McpRuntime         │
                                                                │  (screenshots, input,        │
                                                                │   live tree, eval)           │
                                                                └──────────────────────────────┘
```

- **MCP server** (`src/godot_mcp/`): plain Python on the official `mcp` SDK (2.x,
  `MCPServer`). Defines tools, validates args, forwards to the editor, shapes
  results. No Godot dependency → fast to start, easy to unit-test, and the same
  toolchain (`uv`, `ruff`, `pytest`) as `blender-mcp`.
- **Editor plugin** (`addon/addons/godot_mcp/`): pure GDScript `@tool`
  `EditorPlugin`. Opens a `TCPServer` on `127.0.0.1:9080` (configurable) and polls
  it from `_process()`. Godot's editor already runs `_process` on the main thread,
  so there's **no thread/queue dance** like Blender's timers — requests are
  handled directly where the engine API is safe to call. Long jobs (imports,
  exports) are spread across frames with `await`.
- **Runtime bridge**: instead of opening a second socket inside the game, use
  Godot's own editor↔game debug channel. The editor plugin registers an
  `EditorDebuggerPlugin`; the plugin auto-adds an autoload (`McpRuntime`) that calls
  `EngineDebugger.register_message_capture("mcp", …)`. Messages ride the debugger
  connection the editor already has with every game it launches — no extra port,
  no auth problem, works for every "Run" the user or the agent starts. Autoload is
  only active when `EngineDebugger.is_active()`, so exported release builds carry
  zero overhead (and we strip it from export presets via an `EditorExportPlugin`).
- **Language server client**: Godot's editor ships a GDScript LSP on `:6005`.
  The MCP server talks to it for diagnostics, hover docs, go-to-definition and
  symbol search instead of reimplementing any of that.
- **Headless fallback**: when no editor is connected, a subset of tools
  (validate project, run tests, export, class docs) runs by spawning
  `godot --headless --path <project> …` directly. This also makes CI possible.

Why not an MCP server written in GDScript inside the editor (Streamable HTTP
directly from Godot)? Tempting — no Python at all. Rejected for v1 because:
stdio is still the only transport every harness supports; a DIY HTTP/SSE server
in GDScript means reimplementing the MCP spec (and chasing its revisions — the
2026-07-28 stateless rework just changed the transport again); and we'd lose the
tested SDK. Revisit as a stretch goal (M8) once the protocol settles.

Why Python and not TypeScript/`npx`? Both are fine for reach. Python keeps one
toolchain across this monorepo and lets us reuse the `blender-mcp` framing,
bridge, and test harness nearly verbatim. `uvx` is as one-line as `npx`.

---

## 2. Folder layout

```
godot-mcp/
├── README.md
├── PLAN.md                     ← this file
├── pyproject.toml              ← uv project; the MCP server package
├── src/godot_mcp/
│   ├── server.py               ← MCPServer app, toolset selection, entrypoint
│   ├── transport.py            ← stdio (default) / Streamable HTTP (`--http`)
│   ├── bridge.py               ← async TCP client to the editor, framing, reconnect
│   ├── protocol.py             ← message schemas + protocol version (mirrored in GDScript)
│   ├── lsp.py                  ← minimal LSP client for Godot's :6005 server
│   ├── headless.py             ← spawn `godot --headless` for no-editor tools
│   ├── compat.py               ← per-harness quirks (schema flattening, image fallback)
│   ├── tools/                  ← one module per toolset (project, scene, script, run, …)
│   └── results.py              ← image content, truncation, error mapping
├── addon/                      ← a tiny Godot project used for dev + integration tests
│   ├── project.godot
│   └── addons/godot_mcp/
│       ├── plugin.cfg
│       ├── plugin.gd           ← EditorPlugin: start/stop, dock, settings
│       ├── listener.gd         ← TCPServer + framing + auth, polled in _process
│       ├── protocol.gd         ← GDScript mirror of protocol.py (generated + checked in CI)
│       ├── debugger_plugin.gd  ← EditorDebuggerPlugin: talks to running games
│       ├── export_plugin.gd    ← strips McpRuntime from export builds
│       ├── runtime/mcp_runtime.gd   ← autoload inside the game
│       ├── handlers/           ← mirror of tools/: project.gd, scene.gd, node.gd, …
│       └── dock/               ← status dock scene (port, token, log, toggles)
├── tests/
│   ├── unit/                   ← server-side with a fake bridge; schema compat checks
│   ├── integration/            ← real `godot --headless --editor` + plugin
│   └── fixtures/               ← sample projects (2D platformer, 3D scene, C#)
├── scripts/
│   ├── build_addon.py          ← zip addon for Asset Library, sync protocol.gd
│   ├── dev_godot.sh            ← open addon/ project with plugin symlinked
│   └── check_harness_schemas.py ← validate every tool schema against each harness's rules
├── skills/                     ← agent skills / playbooks (make a 2D platformer, …)
└── examples/                   ← ready-to-paste configs for every harness (§6)
```

Stack: Python ≥3.11, `uv`, `ruff`, `pytest`, `pydantic` (arg models), `mcp` SDK 2.x.
GDScript 2.0 with static typing everywhere in the add-on (`warnings/untyped_declaration=error`
for the addon folder) so the plugin itself doesn't regress silently.

---

## 3. Tool surface

Design principles (carried over from `blender-mcp`, adjusted for Godot):

1. **Structured tools first, escape hatch last.** Structured tools cover 90%;
   `execute_gdscript` covers the rest and is off by default.
2. **Every editor mutation goes through `EditorUndoRedoManager`** with an
   `"MCP: <tool>"` action name, so the human can Ctrl+Z the agent. Script file
   writes go through `ScriptEditor`/`ResourceSaver` so open tabs reload instead of
   clobbering unsaved human edits (conflict → error, never silent overwrite).
3. **Address nodes by NodePath relative to the scene root**, return the actual
   paths (Godot renames `Sprite2D` → `Sprite2D2` on collisions).
4. **Address files by `res://` paths**, never absolute OS paths.
5. **Small outputs by default**, `detail=true` / pagination for more; always say when
   something was truncated.
6. **Let the model see *and* read errors.** Screenshots of editor viewports and the
   running game, plus the Output/Debugger panes and LSP diagnostics. For Godot the
   error loop matters more than the visuals: most agent failures are GDScript
   typos and wrong API names.
7. **Ground the model in the real 4.7 API.** LLM training data is full of Godot 3
   (`KinematicBody`, `yield`, `export var`). A `get_class_docs` tool backed by live
   `ClassDB` + a curated "Godot 3 → 4 pitfalls" resource are first-class, not extras.

Tools are grouped into **toolsets** (§6.3) so tool-capped harnesses can load a subset.

### 3.1 `project` — orient
| Tool | Purpose |
| --- | --- |
| `get_project_info` | Name, Godot version, renderer, main scene, autoloads, input map summary, enabled plugins, C# or not, connection status of editor/game |
| `list_files` | `res://` tree with type filter (scenes, scripts, resources, assets), paginated; respects `.gdignore` |
| `search_files` | text/regex search across project files (scripts, `.tscn`, `.tres`) |
| `get_project_settings` / `set_project_setting` | read any setting; write an allowlisted subset (display, input, physics layers names, autoloads) |
| `edit_input_map` | add/remove actions and their events |

### 3.2 `scene` — structure
| Tool | Purpose |
| --- | --- |
| `get_scene_tree` | Edited scene as a tree: path, type, script, instance-of, groups; depth + filter args |
| `open_scene` / `new_scene` / `save_scene` / `close_scene` | new_scene takes root type (`Node2D`, `Node3D`, `Control`, …) |
| `add_node` | type or scene-to-instance, parent path, name, initial properties |
| `remove_node` / `rename_node` / `move_node` (reparent + reorder) / `duplicate_node` | |
| `get_node_properties` | editor-visible properties with current values (typed: Vector2/Color/NodePath/Resource ref serialised consistently) |
| `set_node_properties` | batch set; values in the same typed JSON form; returns what actually changed |
| `connect_signal` / `disconnect_signal` / `list_signals` | persistent (`CONNECT_PERSIST`) connections saved into the scene |
| `set_groups` | add/remove groups |
| `save_branch_as_scene` | turn a subtree into its own `.tscn` and instance it back |

### 3.3 `script` — code
| Tool | Purpose |
| --- | --- |
| `read_script` | GDScript/C#/shader source with line numbers, optional range |
| `write_script` / `edit_script` | full write, or exact-string replace (like an editor tool); reloads the script in the editor; returns fresh diagnostics |
| `create_script` | from a template: `extends`, `class_name`, typical callbacks; optionally attach to a node |
| `attach_script` / `detach_script` | |
| `get_diagnostics` | LSP diagnostics for one file or the whole project (errors + warnings, file:line) |
| `find_symbol` / `get_definition` / `get_references` | via LSP |

### 3.4 `resources` & assets
| Tool | Purpose |
| --- | --- |
| `create_resource` | any `Resource` subclass (materials, `Theme`, `Curve`, `SpriteFrames`, `TileSet`, custom `class_name` resources) → `.tres` |
| `get_resource` / `set_resource_properties` | same typed-JSON property model as nodes |
| `import_asset` | copy a file from an allowed folder into `res://`, trigger reimport, set import options (e.g. pixel-art filter off) |
| `reimport` | |
| `set_tiles` / `get_tiles` | paint cells on a `TileMapLayer` (rects, lists, terrain fill) — tilemaps are painful to do by property-setting |

### 3.5 `run` — play & observe (the runtime bridge)
| Tool | Purpose |
| --- | --- |
| `run_project` / `run_scene` / `stop` | via `EditorInterface.play_*`; returns once the debugger session is live |
| `get_output` | Output-pane / game stdout since a cursor, filtered by level; includes `push_error`/`push_warning` with file:line |
| `get_runtime_errors` | debugger errors + script backtraces from the running game |
| `get_game_screenshot` | viewport texture of the running game → image |
| `get_live_tree` / `get_live_properties` / `set_live_property` | remote scene tree inspection & tweaking (like the Remote tab) |
| `send_input` | inject actions / keys / mouse / joypad events (`Input.parse_input_event`) for N frames — lets the agent actually *play-test* |
| `wait` | advance until a condition (frames, seconds, signal, node exists, property predicate) — no blind sleeps |
| `get_performance` | FPS, frame time, draw calls, object/node counts from `Performance` monitors |

### 3.6 `view` — see the editor
| Tool | Purpose |
| --- | --- |
| `get_editor_screenshot` | 2D or 3D editor viewport (`EditorInterface.get_editor_viewport_2d/3d`) or whole editor window → image |
| `focus_node` | select + frame a node in the viewport before a screenshot |
| `set_editor_camera` | 3D: view preset (front/top/persp), orbit, distance |

### 3.7 `docs` — grounding
| Tool | Purpose |
| --- | --- |
| `get_class_docs` | methods, properties, signals, constants, enums for a class from live `ClassDB` + the built-in XML descriptions; includes user `class_name` types |
| `search_docs` | fuzzy search over class/method names ("how do I raycast" → `PhysicsDirectSpaceState3D.intersect_ray`) |

### 3.8 `build` — ship & test
| Tool | Purpose |
| --- | --- |
| `list_export_presets` / `export_project` | headless export of a preset to an allowed folder |
| `run_tests` | detect + run GUT or GdUnit4 headless, return structured pass/fail |
| `validate_project` | headless `--check-only` style pass over all scripts + missing-dependency scan of scenes |

### 3.9 Escape hatch
| Tool | Purpose |
| --- | --- |
| `execute_gdscript` | run a snippet in the **editor** (`EditorScript`-like context) or in the **running game**; captures prints + return value. **Off unless the dock toggle is on and a token is set.** Editor-side runs are wrapped in an undo action where possible. |

### 3.10 MCP resources & prompts (optional; tools must never depend on them)
- `godot://project` — live project summary.
- `godot://docs/pitfalls` — Godot 3 → 4.7 migration traps (`yield`→`await`,
  `export`→`@export`, `KinematicBody`→`CharacterBody`, `TileMap`→`TileMapLayer`, …).
- `godot://docs/{topic}` — short curated notes: typed-JSON value format, scene
  instancing, physics layers, `CharacterBody2D` movement recipe, UI anchors.
- Prompts: `make_prototype`, `fix_errors_loop`, `playtest`.
- Every resource is **also exposed as a tool** (`read_guide(topic)`) because several
  harnesses (Codex, dsh, some Cursor versions) don't surface resources/prompts to the
  model at all.

---

## 4. Godot-side details

- **Main thread:** `listener.gd` polls `TCPServer.is_connection_available()` and each
  `StreamPeerTCP` in `_process()` with a per-frame time budget (~4 ms) so the editor
  stays responsive. Handlers are `async` (`await`) when they must wait for the
  filesystem scan, an import, or the game to start.
- **Framing & protocol:** 4-byte big-endian length + UTF-8 JSON, JSON-RPC 2.0,
  versioned `hello` handshake (same as `blender-mcp`, so bridge code is shared).
  Hard limits: 64 KB before auth, 32 MB after, max 8 clients, bounded JSON depth.
- **Typed JSON values:** one serializer shared by all handlers.
  `{"_type":"Vector2","x":1,"y":2}`, `{"_type":"Color","html":"#ff0000"}`,
  `{"_type":"Resource","path":"res://…"}`, `{"_type":"NodePath","path":"../Player"}`.
  Plain JSON numbers/strings/bools pass through. The same shape is accepted as
  input, and string shorthands (`"Vector2(1, 2)"`) are parsed with `str_to_var` for
  forgiveness.
- **Undo:** `EditorUndoRedoManager.create_action("MCP: add_node")`, `add_do_method`
  / `add_undo_method` / `add_do_reference`. Failures roll back before committing.
- **Filesystem sync:** after any file write → `EditorFileSystem.update_file()` or
  `scan()` and `await` `filesystem_changed` so the next call sees the new file.
- **Unsaved human edits:** before touching a script open in the editor with unsaved
  changes, refuse with a clear error unless `force=true`.
- **Runtime autoload:** added/removed by the plugin in `_enable_plugin` /
  `_disable_plugin`; no-op when `EngineDebugger.is_active()` is false.
  Screenshot = `get_viewport().get_texture().get_image()` → PNG → base64 over the
  debugger channel (chunked for big frames).
- **Dock UI:** start/stop, port, token (copy button), connected clients, last N
  commands log, toggles: *Allow execute_gdscript*, *Allow export*, *Auto-start*.
- **C# projects:** script tools handle `.cs` as text; diagnostics come from
  `dotnet build` output instead of the GDScript LSP; `run_project` triggers the
  editor's build first. Scene/node tools are language-agnostic.
- **Distribution:** Godot Asset Library zip (`addons/godot_mcp/` only), plus a
  `uvx godot-mcp install-addon <project>` helper that copies it and enables it in
  `project.godot`.

---

## 5. Safety

- Listen on **127.0.0.1 only**. A random token is generated **by default** (lesson
  from `blender-mcp` M6) and stored in the editor settings; the server reads
  `GODOT_MCP_TOKEN`. The dock shows it with a copy button and a ready-made config
  snippet.
- File tools are confined to `res://` plus explicit allowlisted import/export
  folders; `..`, symlink escapes and `user://`-to-OS tricks are rejected.
  `.godot/`, `addons/godot_mcp/` and `project.godot` are write-protected except
  through the dedicated settings tools.
- `execute_gdscript` and `export_project` are opt-in toggles.
- Per-call timeouts (default 30 s; runs/exports 300 s). A client-side timeout
  can't cancel work already started in the editor — document it, and make
  mutating tools idempotent where cheap (e.g. `add_node` with an explicit name
  fails instead of creating `Node2`).
- Tool descriptions and results never contain instructions to the model beyond
  describing the tool (keeps us out of prompt-injection territory when
  project files contain hostile text; file contents are returned as data).

---

## 6. Harness compatibility (the "works everywhere" part)

### 6.1 Transports
- **stdio** (default) — every harness supports it.
- **Streamable HTTP** (`godot-mcp --http --port 7080`, localhost, bearer token) for
  harnesses/setups that prefer a URL (remote dev containers, VS Code remote,
  multiple agents sharing one editor). Supports both the pre-2026 session-based
  protocol and the stateless **2026-07-28** revision via the SDK's version
  negotiation — clients are upgrading at different speeds.

### 6.2 Schema lowest-common-denominator
Some harnesses (notably Gemini and OpenAI-strict tool calling) reject parts of
JSON Schema. Every tool schema must pass `scripts/check_harness_schemas.py`:
- no `$ref`/`$defs`, no `oneOf`/`anyOf`/`allOf` at top level, no `patternProperties`;
- every property has an explicit `type`; enums are strings;
- object args that are genuinely free-form (property dicts) are typed as `object`
  with a description of the typed-JSON format rather than a union schema;
- tool names `^[a-z0-9_]{1,48}$` (safe under every prefixing scheme: Claude
  `mcp__godot__…`, Cursor/Copilot namespacing, 64-char caps);
- descriptions ≤ ~300 chars, no harness-specific wording.

### 6.3 Tool budgets
Cursor, Copilot and others cap or degrade with many tools. `GODOT_MCP_TOOLSETS`
selects groups (`project,scene,script,run,view,docs,build,resources,exec`). Presets:
- `core` (default, ~25 tools): project, scene, script, run, docs.
- `all`: everything (~60 tools).
- `minimal` (~10 tools): the essentials for strict caps.

### 6.4 Images
Not every harness passes image content to the model. Screenshots return MCP
`image` content **and** (when `GODOT_MCP_IMAGE_MODE=file` or the client didn't
advertise image support) save a PNG under `res://.mcp/screens/` (gitignored) and
return the path, so file-reading agents can still look.

### 6.5 Environment
Harnesses like dsh and some IDEs spawn servers with a scrubbed env and odd cwd.
Everything configurable by env var *and* CLI flag; no reliance on `PATH` for the
Godot binary (`GODOT_BIN` / auto-detect common install paths / Steam / Flatpak);
project dir from `--project`, env, or the connected editor.

### 6.6 Configs shipped in `examples/` (and in the README, one `<details>` each)
Claude Code (`claude mcp add` + `.mcp.json`), Claude Desktop, Codex CLI
(`config.toml`), Gemini CLI (`settings.json`), Cursor (`.cursor/mcp.json`),
VS Code / Copilot (`.vscode/mcp.json`), Windsurf, Zed (`context_servers`),
opencode, Cline / Roo, JetBrains AI Assistant, dsh (`cordis.patch.yml`), and a
generic stdio/HTTP section. Each entry records *"verified on <date> with <version>"*
or *"untested"* — never claim a harness works that we haven't run.

### 6.7 Harness smoke matrix
A scripted task (`skills/smoke.md`: "make a 2D scene with a CharacterBody2D that
moves with arrow keys, run it, press right for 30 frames, screenshot") run manually
per milestone in each harness we can access; transcripts + screenshots kept in
`examples/smoke/`.

---

## 7. Testing

- **Unit (no Godot):** tools vs. fake bridge, framing round-trips, typed-JSON codec,
  arg validation, **schema-compat checker** over every tool.
- **Protocol parity:** CI fails if `protocol.gd` drifts from `protocol.py`.
- **Integration:** pytest fixture launches
  `godot --headless --editor --path addon/` with the plugin enabled, waits for the
  port, drives real tools, asserts on saved `.tscn` contents and the live tree.
  Runtime tests start the game headless (`--headless` run via the editor) and use
  `send_input` + `wait` + `get_live_properties`. Screenshot tests need a GPU-less
  renderer → run with `--rendering-driver opengl3` on Mesa llvmpipe (or skip and
  mark), as with `blender-mcp` headless renders.
- **GDScript-side unit tests** with GdUnit4 for the typed-JSON serializer and path
  guards.
- **CI:** `.github/workflows/godot-mcp.yml` with `paths:` filters; pinned Godot 4.7.2
  Linux headless binary (cached); a non-blocking job on the latest 4.8 dev snapshot.

---

## 8. Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| **M0** | Skeleton | uv project; plugin enables, dock shows status; `hello` handshake + `get_project_info` works from Claude Code *and* one non-Claude harness |
| **M1** | Read the project | §3.1 + `get_scene_tree`, `get_node_properties`, `read_script`, `get_class_docs`, `get_diagnostics` (LSP); editor screenshots |
| **M2** | Edit scenes & scripts | rest of §3.2 + §3.3 with undo; typed-JSON codec; agent builds a small 2D scene with a moving player |
| **M3** | Run & observe | runtime bridge: run/stop, output, runtime errors, game screenshot, live tree, `send_input`, `wait`; the *fix-errors loop* works end to end |
| **M4** | Harness hardening | Streamable HTTP, toolsets, schema checker in CI, image-file fallback, configs + smoke run on ≥6 harnesses |
| **M5** | Resources, tiles, assets | §3.4; agent makes a tile-based level with imported pixel art |
| **M6** | Build & test | §3.8 export + GUT/GdUnit4 runner + headless fallback mode with no editor open |
| **M7** | Escape hatch, guides, skills | `execute_gdscript` behind toggle+token, `godot://docs` + `read_guide`, prompts, skills (2D platformer, 3D third-person, UI menu) |
| **M8** | Stretch | C# depth (build errors, `[Export]` awareness), multi-editor (pick by port/project), animation/AnimationTree helpers, shader tools, native in-editor HTTP transport experiment, Asset Library release |

Release tags: `godot-mcp-v*`, mirroring `blender-mcp`'s release workflow.

---

## 9. Open questions

- **Name on PyPI / Asset Library.** `godot-mcp` is almost certainly taken by
  existing community projects — pick a distinct distribution name before M4.
- **Minimum version.** 4.7 only (simpler, `TileMapLayer`/typed-dict era), or back to
  4.5 LTS-ish users? Start 4.7-only; revisit if people ask.
- **Runtime channel:** the `EngineDebugger` route only works for games launched
  from the editor. Do we also need to attach to a standalone build (`--remote-debug`)?
  Probably yes for exported-build testing — cheap to add since it's the same protocol.
- **GDExtension instead of GDScript for the plugin?** Faster and could embed an
  HTTP server, but needs per-platform binaries. GDScript until profiling says otherwise.
- **Screenshot size vs. token cost:** default 768 px long edge, as in `blender-mcp`.
- **How much of `blender-mcp` to share?** Framing/bridge/results are near-identical.
  Copy for now (projects are self-contained per repo conventions); extract a shared
  package only if a third MCP project appears.
