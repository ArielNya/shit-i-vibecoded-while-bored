# roblox-mcp — plan

Goal: an AI agent in any MCP harness can **build a whole Roblox game**: write and
type-check Luau, shape the DataModel, bring in assets from disk, play-test, run
tests, and publish. Paired with an **agent skill** that teaches the agent to do it
the way an experienced Roblox developer would.

Target: **Roblox Studio 0.740** (week of 2026-09-21) and the Engine API reference
at [`Roblox/creator-docs`](https://github.com/Roblox/creator-docs) `0b817b5`
(2026-09-26, `reference/engine/STUDIO_VERSION` = `0.740.19`). Roblox ships weekly,
so the pin is bumped by a script (§7), not by hand.

Status: **M0–M5 done, M6 done except what needs Studio, Open Cloud or another client** (see §8 notes; the Open Cloud parts of M3–M5 aren't verified against Roblox yet). Next: M6's remaining manual checks, then M7 (the wrapper).

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
- **CLI tools, not reimplementations.** Rojo 7.7, luau-lsp 1.70, selene 0.31 (optional, M2 notes),
  StyLua 2.5, Lune 0.10, pinned in the game project's
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
| `init_project` | Rojo project in the recommended structure + `rokit.toml` + strict `.luaurc`; never overwrites (M2 notes) |
| `build_place` | `rojo build` → `.rbxl` / `.rbxm` in the project's `build/` |
| `sync_status` | is `rojo serve` running, port, sourcemap fresh; can start/stop it |

### 3.2 `code`
| Tool | Purpose |
| --- | --- |
| `check_code` | `rojo sourcemap` → `luau-lsp analyze` (Roblox definitions, new type solver), + `selene` if the project has a `selene.toml`; one list of `file:line:col severity code message` |
| `format_code` | `stylua` on files or the project; returns changed files |
| `run_tests` | `*.spec.luau` specs on roblox-mcp's own harness (M3 notes): pure modules under Lune locally; `target="cloud"` runs the built place via Open Cloud Luau Execution (real engine, headless, ≤5 min) and returns structured pass/fail + logs |

### 3.3 `assets`
| Tool | Purpose |
| --- | --- |
| `upload_asset` | local file (`.fbx .gltf .glb .rbxm .rbxmx .png .jpg .tga .bmp .ogg .mp3 .wav .flac .mp4 .mov`) → Open Cloud Assets API → polls the operation → `rbxassetid://…`. Then the agent calls the built-in `insert_asset` |
| `list_uploaded_assets` | the project's `assets.lock.json` manifest: path, content hash, asset id; skips re-uploading unchanged files |

### 3.4 `cloud`
| Tool | Purpose |
| --- | --- |
| `publish_place` | upload a `.rbxl`/`.rbxlx` as a Saved or Published version; **off unless `--allow-publish`** |
| `run_luau_cloud` | Open Cloud Luau Execution on the latest version of the test place (live needs `--allow-publish`); returns results/output |
| `datastore_read` / `datastore_list` | read-only DataStore inspection (stores, keys, entries); `datastore_set` only with `--allow-datastore-writes` |

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
- `publish_place`, `datastore_set` and `run_luau_cloud` against the live place exist
  only when the server is started with `--allow-publish` / `--allow-datastore-writes`
  (**off by default**; M5 notes).
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
`testing.md` (spec format, local and cloud runs), `publishing.md`, `recipes/` (obby,
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
  failing spec.
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
| **M1** ✅ | Docs grounding | `get_api_docs`, `search_api`, deprecated table from pinned `creator-docs`; **skill v0** (`SKILL.md` + 3 references) usable with the built-in server alone |
| **M2** ✅ | Project & code | `init_project`, `build_place`, `sync_status`, `check_code`, `format_code` on the fixture game; session hook installs the toolchain |
| **M3** ✅ | Tests | `run_tests` local (Lune) and cloud (Luau Execution); acceptance: the agent fixes the fixture's failing spec using only tools |
| **M4** ✅ | Assets | `upload_asset` + manifest for models, images, audio; acceptance: a local `.glb` ends up in Studio via `insert_asset` (manual Studio smoke) |
| **M5** ✅ | Cloud ops | `publish_place`, `run_luau_cloud`, DataStore read (write opt-in) |
| **M6** ◐ | Skill complete | all references + recipes; evals with vs. without skill; full-game smoke (small obby: build, code, test, publish to a private place) in Claude Code + one other harness |
| **M7** | Wrapper | §9: `--wrap-studio` proxies the built-in server behind ours; the conflict rules there, each with a test against a fake built-in server; manual Studio smoke with only `roblox-mcp` configured |
| **M8** | Stretch, only if M6 shows a real gap | own Studio plugin for what `execute_luau` can't do; multi-place universes; Packages; `.rbxm` insert without uploading |

### M6 notes

- **Done:** all planned references (`data`, `ui`, `physics-and-characters`,
  `performance`, `luau-types` added), three recipes, evals, a full-game smoke run without
  Studio. **Open:** the Studio half of the smoke test, publishing to a private place (needs
  Open Cloud), and a second client (no other MCP client is installed here). Those need your
  machine.
- **Recipes are projects, not prose:** `recipes/obby`, `round-based`, `inventory` are Rojo
  projects inside the skill. The integration tests copy each one and require
  `check_code` clean, `format_code` clean, specs passing and `build_place` working;
  `read_guide("recipe-<name>")` returns the README plus every file. Writing them caught
  five of my own mistakes: `hit.Parent` isn't a `Model` for `GetPlayerFromCharacter`, a
  type annotation on a table field (not valid Luau), `Player:LoadCharacter` (deprecated),
  an `UpdateAsync` "read" that was really a write on every join (now `GetAsync`), and
  untyped spec parameters.
- **Specs take `t: any`:** with the new solver an unannotated `t` is inferred from its
  first use and the other matchers become errors. The M3 fixture passed only by luck;
  every spec, the testing guide and `run_tests`' hint now say `function(t: any)`.
- Every API the references name was checked against the index; `PhysicsService`
  collision-group methods and `TextFilterResult:GetChatForUserAsync` are deprecated and the
  references say so.
- **Evals** (`evals/run_evals.py`): fresh `init_project` per run, `claude -p` with only
  roblox-mcp; "with" installs the skill, "without" blocks `read_guide`. Graded
  automatically: type errors, deprecated APIs (luau-lsp + patterns), specs, task checks.
  - Round 1 (3 tasks × 2 × 2): the agent loaded the skill in only 2 of 6 "with" runs. Two
    graders were too narrow (`type()` validation, truncation with `:sub`) and the
    container's ponytail plugin was active in both conditions. Re-graded: 5/6 vs 5/6.
  - Fixes: a directive skill description naming the rules agents get wrong; server
    instructions to read the skill before writing code; user plugins disabled in eval runs;
    the skill name recorded per run.
  - Round 2 (5 tasks incl. two deprecated-API traps × 2 × 2): skill loaded in 10/10 "with"
    runs. One more grader was presumptuous (it required collision groups; every run used
    anchored parts with raycast exclude filters, which is as good or better); corrected.
    **Result: 10/10 vs 9/10 runs pass every check** — within noise. No run in either
    condition used a deprecated API, even on the trap tasks. The "without" condition still
    has `check_code`, `run_tests` and `get_api_docs`, which catch those; on automatable
    checks the tools do most of the work. The skill's value is in things these checks
    can't see (structure, studio_id discipline, undoable edits, safe publishing), which
    need Studio runs to measure.
  - Small n (2 per cell), one model; results and graded outputs are in `evals/results/`.
- **Smoke** (`examples/smoke/2026-09-28-obby.md`): from an empty folder, with the skill,
  Claude Code loaded the skill, read `recipe-obby`, ran `init_project`, wrote 8 modules and
  3 specs, then `format_code` → `check_code` → `run_tests` → `build_place`. Re-verified
  independently: 0 errors, 16/16 tests, place built. Not played in Studio.

### M5 notes

- 5 tools: `run_luau_cloud`, `datastore_list`, `datastore_read` always; `datastore_set`
  with `--allow-datastore-writes`, `publish_place` with `--allow-publish` (flags or
  `ROBLOX_MCP_ALLOW_*=1`). Gated tools aren't registered at all, rather than refusing at
  call time, so an agent (or text in a place it reads) can't talk its way into using
  them. `run_luau_cloud place="live"` also needs `--allow-publish`: a script can call
  `AssetService:SavePlaceAsync`.
- `run_luau_cloud` uses the version-less task endpoint (latest saved version), test place
  by default. `opencloud.run_luau` takes an optional version; M3's test runs still pin the
  version they uploaded.
- **Publishing hazard found in the docs:** the API replaces the whole place with the file,
  and our template keeps the world out of the Rojo project, so publishing a Rojo build
  would delete the world. `publish_place` needs an explicit file and refuses files under
  `build/` when the project tree has no `Workspace`; the skill routes Studio-built places
  to Studio's own publish. The API also skips `Editable*`, `PartOperation`,
  `SurfaceAppearance` and `BaseWrap` (documented in `references/publishing.md`).
- **Data store write hazard found in the docs:** an entry update that omits `users` or
  `attributes` clears them (losing the user association that GDPR deletion relies on).
  `datastore_set` reads the entry first and carries both over; a 404 means create. The
  caller's `etag` makes the write fail if a live server changed the entry in between.
  Keys and store names are URL-encoded (a key can contain `/`); prefix listing uses the
  API's only filter, `id.startsWith("…")`.
- Default-scope standard data stores only (no `/scopes/`, ordered stores, deletes or
  revisions): enough to inspect and fix player data; add when needed.
- `CloudError` now carries the HTTP status. The schema checker covers the opt-in tools
  too (17 tools, ~2k tokens).
- Tested against a fake Open Cloud: endpoints, query strings, encoding, bodies, the
  read-then-write, create on 404, publish guard and content types, gating of the tool
  list and flags. **Not verified against Roblox** (`apis.roblox.com` blocked here).

### M4 notes

- `upload_asset(path, name, description, asset_type)` and
  `list_uploaded_assets(refresh)`. Types, content types and limits come from creator-docs
  `cloud/guides/usage-assets.md`; request shape from `reference/cloud/assets/v1.json`:
  multipart `request` (JSON Asset) + `fileContent`, returns an Operation polled at
  `assets/v1/operations/{id}` until `done`, then the Asset (`assetId`,
  `moderationResult`). Multipart is encoded by hand (stdlib has no encoder); no new
  dependency.
- Extension decides the type (Model/Image/Audio/Video); `asset_type` overrides only
  where the docs allow (`.rbxm` → Animation, images → Decal). 20 MB cap (except video),
  confined to the project root. Owner from `ROBLOX_CREATOR_USER_ID` or
  `ROBLOX_CREATOR_GROUP_ID`.
- `assets.lock.json` (committed with the game) maps file → sha256, id, type,
  moderation, time. Same bytes and type → the recorded id, no upload. That matters
  beyond speed: unverified accounts get 10 audio uploads a month.
- Results say where the id goes. Checking those hints against the index caught
  `Decal.Texture` as deprecated (→ `ColorMapContent`); image hints use the `Content`
  properties (`Content.fromAssetId`).
- Tested against a fake Assets API that parses the multipart body with the stdlib email
  parser: fields, filename, content type and bytes; caching; re-upload on change; type
  overrides and refusals (extension, outside the project, size, missing owner) before any
  request; group owner; moderation refresh. **Not verified against Roblox**
  (`apis.roblox.com` blocked here), and the acceptance step (a local `.glb` inserted
  into Studio with `insert_asset`) needs Studio: both are for a machine with network and
  Studio.
- Skill: `references/assets.md` (which route for which asset, limits, where each id goes),
  plus a routing row in `SKILL.md`.

### M3 notes

- `run_tests(paths, target, filter)`: `local` runs under Lune, `cloud` through Open Cloud.
- **No jest-lua:** its README says it only runs inside Roblox (Lune support is an open
  issue), so it can't be the local runner. roblox-mcp ships its own harness instead,
  `data/test_harness.luau`: ~110 lines of plain Luau, prepended to both runners. A spec
  is `X.spec.luau` returning `function(t)` with `t.describe`, `t.test`, `t.expect`
  (`toBe`, `toEqual`, `toBeCloseTo`, `toBeNil`, `toBeTruthy`, `toThrow`). No globals and
  no harness module to install, so specs type-check under `--!strict` and run anywhere.
- **Same spec in both places** because Roblox now supports require-by-string (`./X`,
  `../X`, `@self`, `@game`; creator-docs `LuaGlobals.require`), as does Lune, and Rojo
  keeps disk and DataModel layouts aligned. Instance-path requires are Roblox-only.
- Local: the runner file is written into the project root (so relative requires
  resolve), run with `lune run`, deleted afterwards; results come back as one JSON line.
  Lune has no engine globals (`Vector3` is nil), which the testing guide says plainly.
- Cloud: `opencloud.py` (stdlib `urllib`) builds with `rojo build`, uploads a **Saved**
  version (`POST universes/v1/{u}/places/{p}/versions?versionType=Saved`), creates a Luau
  execution task on that version, polls until COMPLETE/FAILED, then reads the logs.
  Shapes and scopes from creator-docs `reference/cloud/openapi.json` and
  `universes-api/v1.json`; 5 task creations per minute per key owner. The driver finds
  every ModuleScript named `*.spec` in the game's content services and returns the
  results table as the task output.
- **Safety:** cloud tests need `ROBLOX_TEST_PLACE_ID` and refuse when it equals
  `ROBLOX_PLACE_ID`: a saved version is what Studio opens next, so uploading test builds
  to the real place could replace someone's work.
- Tested: local runs against real Lune (pass; a regression caught with the spec line;
  filter; a spec returning a non-function; a failing require), with absolute paths and
  Lune stack traces stripped from messages. **Cloud runs are not verified against Roblox**
  (`apis.roblox.com` is blocked here): a fake Open Cloud server checks the exact request
  sequence (key header, upload body and content type, task body, polling, logs), failure
  states and HTTP error hints, and the generated cloud script type-checks against
  Roblox's definitions. First real run needs a key and a test place (CI secrets or a
  machine with network).
- Acceptance: Claude Code 2.1.283 (`claude -p`, only roblox-mcp) on a copy of the fixture
  with a broken `Damage.apply`: `get_project_info` → `run_tests` (1 failing) → read →
  edit the module (not the spec) → `run_tests` 2/2 → `check_code` clean.

### M2 notes

- 5 new tools (9 total): `init_project`, `build_place`, `sync_status`, `check_code`,
  `format_code`. Pins live in one place, `toolchain.PINS` (rojo 7.7.0, luau-lsp 1.70.1,
  stylua 2.5.2, lune 0.10.5): `init_project` writes them to the game's `rokit.toml`,
  `scripts/install_toolchain.py` installs them on Linux, and the session hook and CI
  call that script. Tools are found in `ROBLOX_MCP_BIN_DIR`, then `PATH`.
- **No rokit here:** it needs the GitHub API, blocked in this sandbox (release
  downloads aren't). Also blocked: `apis.roblox.com` and Roblox's CDN, which matters
  for M3 cloud runs and M4 uploads; those will need a machine with network or CI.
- **Type checking:** `luau-lsp analyze` with `--flag:LuauSolverV2=true`. The old solver
  missed a misspelled `player.Nmae` inside a callback and a plugin-only API in game
  code; the new one (Roblox's default since the Nov 2025 release) catches both.
  Definitions: `globalTypes.None.d.luau` from luau-lsp 1.70.1, bundled (105 KB gz), the
  lowest security level so plugin-only APIs are errors. `rojo sourcemap` runs first, so
  `require(ReplicatedStorage.Shared.X)` resolves and typos in module members are caught.
  luau-lsp exits 0 even with errors and prints type errors with absolute paths but lints
  with relative ones; the output is parsed and normalised. `TypeError`/`SyntaxError` are
  errors, lints warnings.
- **selene dropped from the default:** its `roblox` std downloads Roblox's API dump
  (blocked here, and a network dependency for every user), and luau-lsp's lints already
  cover unused/shadowed/deprecated. It still runs when a project has `selene.toml`.
- **Template:** `rojo init`'s template is the old layout (client in
  `StarterPlayerScripts`, `FilteringEnabled`, legacy Lighting), and it overwrites the
  world on sync, so `init_project` writes its own: `emitLegacyScripts: false`, client
  entry `Script` in `ReplicatedStorage`, no Workspace/Lighting in the tree, strict
  `.luaurc`. Entries list their `require`s explicitly: a generic "require every child
  module" loader can't be type-checked (dynamic require is an error under the new
  solver). `stylua.toml` skipped: StyLua's defaults handle `.luau`.
- `sync_status` owns at most one `rojo serve` child (stopped at exit); Rojo 7.7's
  `/api/rojo` replies in msgpack, from which project name and version are read.
  Whether Studio's Rojo plugin is connected isn't visible from the server side.
- Tested: unit tests (parsing, paths, template, missing-tool error); integration tests
  against the real binaries (clean fixture checks clean; a broken file yields the type
  error, the `Nmae` typo, a misspelled module member via the sourcemap, the plugin-only
  API, deprecated `wait`; format; build; serve start/status/stop/port clash; selene when
  installed). A new `init_project` project checks clean, formats clean and builds.
  Not tried with Studio's Rojo plugin (no Studio on Linux).
- Smoke: Claude Code 2.1.283 (`claude -p`, only roblox-mcp connected), asked to set up
  a project and write a typed damage module used from the server entry, chained
  `get_project_info` → `init_project` → file writes → `check_code` → `format_code` and
  ended clean.

### M1 notes

- `scripts/build_api_index.py <creator-docs checkout>` turns the 1,194 YAML files of
  `content/en-us/reference/engine` (commit `0b817b5`, Studio `0.740.19`) into
  `src/roblox_mcp/data/engine_api.json.gz` (1 MB, committed, shipped in the wheel) and
  generates `references/deprecated.md`. A sparse checkout of that folder is enough.
  Docs cross-references (`` `Class.X:Y()|Y()` ``) become plain names; docs-relative
  links become `create.roblox.com/docs` URLs. Code samples (IDs only) are dropped.
- Name clashes in the reference: `Instance` is both a class and a datatype (holding
  only `Instance.new`/`fromExisting`), merged into the class; `Platform`, `Status`
  (class + enum) and `Font` (datatype + enum): bare names find the class/datatype,
  `Enum.X` the enum.
- `get_api_docs` resolves members through superclasses (`Workspace:Raycast` →
  `WorldRoot:Raycast`), `Enum.X.Item`, `task.wait`, bare globals (`wait`); lists own
  members with signatures, inherited members by name per ancestor, deprecated ones
  separately; skips `Hidden` / `NotScriptable`. Unknown names get search suggestions.
- `search_api`: word matches on names (whole word > prefix) and summaries, deprecated
  APIs excluded unless asked. Good for names and "what does X" queries; weak for
  intent phrasing that shares no words with the summary ("save player data" doesn't
  find DataStores). Revisit with the M6 evals.
- The skill lives in the package (`src/roblox_mcp/skills/roblox-studio/`), so
  `read_guide` serves the same files and there's one copy. v0: `SKILL.md`,
  `project-layout.md`, `networking.md`, `deprecated.md`. Grounded in creator-docs
  pages (cited at the top of each reference) and Rojo 7.7's docs and changelog; every
  API they name was checked against the index (none deprecated). Correction found on
  the way: Roblox now recommends a single `Script` with `RunContext = Client` in
  `ReplicatedStorage` as the client entry, `LocalScript`s sparingly; with Rojo that
  needs `"emitLegacyScripts": false`.
- Smoke: Claude Code 2.1.283 (`claude -p`, only roblox-mcp connected) answered "what
  replaces BodyGyro and Humanoid:LoadAnimation, and the new signature" correctly via
  `get_api_docs`. The skill hasn't been used against a real Studio yet.

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
