# blender-mcp — plan

Goal: let an AI agent (Claude Code / Claude Desktop / Codex CLI) **see** and
**edit** a live Blender scene well enough to do real modelling work — block out
shapes, apply modifiers, set up materials, render a preview, look at it, and
iterate.

---

## 1. Core constraint that drives the design

`bpy` (Blender's Python API) only exists *inside* a Blender process, and it is
**not thread-safe** — every call must run on Blender's main thread. Meanwhile,
MCP clients want to spawn a server as a normal subprocess over stdio.

So we split it in two:

```
┌──────────────┐  stdio / MCP   ┌──────────────────┐  TCP localhost   ┌───────────────────────────┐
│ Claude Code  │ ─────────────▶ │  MCP server       │ ───────────────▶ │  Blender add-on           │
│ Codex CLI    │ ◀───────────── │  (plain Python,   │ ◀─────────────── │  socket listener thread   │
│ Claude Desk. │                │   no bpy)         │  JSON-RPC 2.0    │  → queue → bpy.app.timers │
└──────────────┘                └──────────────────┘   length-framed   │  → runs on main thread    │
                                                                        └───────────────────────────┘
```

- **MCP server** (`server/`): an ordinary Python package built on the official
  `mcp` SDK (v2, `MCPServer`). Defines tools, validates args, forwards each call to
  Blender, shapes results (text + images) for the model. Has no Blender dependency,
  so it's easy to test and run with `uv`.
- **Blender add-on** (`addon/`): installed into Blender. Opens a socket on
  `127.0.0.1:9876` (configurable). A background thread accepts connections and
  pushes requests onto a queue; a `bpy.app.timers` callback drains the queue on
  the main thread, executes the command handler, and sends the reply back.
- **Protocol** (`protocol/` or a shared module): JSON-RPC 2.0 messages, 4-byte
  length-prefixed framing (avoids the "did I get the whole JSON?" bug that
  newline/recv-until-parse approaches have). Versioned handshake so a mismatched
  add-on/server pair fails loudly.

Why not run the MCP server inside Blender directly? Clients spawn the server
themselves over stdio; Blender is a long-lived GUI app the user already has open.
The bridge also lets one server talk to a headless `blender --background`
instance for tests/CI with zero code changes.

---

## 2. Folder layout

```
blender-mcp/
├── README.md
├── PLAN.md                  ← this file
├── pyproject.toml           ← uv project; the MCP server package
├── src/blender_mcp/
│   ├── server.py            ← MCPServer app, tool registration, entrypoint
│   ├── bridge.py            ← async TCP client, framing, timeouts, reconnect
│   ├── protocol.py          ← message schemas + protocol version (shared w/ addon)
│   ├── tools/               ← one module per tool group (scene, objects, mesh, …)
│   └── results.py           ← helpers: image content, truncation, error mapping
├── addon/
│   └── blender_mcp_addon/
│       ├── __init__.py      ← bl_info / manifest, register(), N-panel UI
│       ├── blender_manifest.toml   ← Blender 4.2+ extension manifest
│       ├── listener.py      ← socket thread + main-thread queue via bpy.app.timers
│       ├── protocol.py      ← vendored copy of src/blender_mcp/protocol.py
│       └── handlers/        ← mirror of tools/: scene.py, objects.py, mesh.py, …
├── tests/
│   ├── unit/                ← server-side, with a fake bridge
│   └── integration/         ← spins up `blender --background` + add-on
├── scripts/
│   ├── build_addon.py       ← zip the add-on (+ sync vendored protocol.py)
│   └── dev_blender.sh       ← launch Blender with add-on symlinked for hot dev
└── examples/
    ├── claude-code.mcp.json
    └── codex.config.toml
```

Stack: Python 3.11 (Blender 4.2+ bundles 3.11), `uv` for env/lock, `ruff`,
`pytest`, `pydantic` for tool arg models. Target **Blender 4.2 LTS and newer**
(new extensions system; drop older versions to keep handlers simple).

---

## 3. Tool surface (what the agent can call)

Design principles:

1. **Structured tools first, `execute_python` as an escape hatch.** Structured
   tools are safer, easier for the model to use correctly, and return consistent
   data. The escape hatch covers the long tail (bmesh wizardry, geometry nodes).
2. **Everything mutating creates an undo step** (`bpy.ops.ed.undo_push`) with a
   `"MCP: <tool>"` label so the human can Ctrl+Z the agent.
3. **Reference objects by name**, return names (Blender may rename to `Cube.001`).
4. **Keep outputs small** — summaries by default, `detail=true` for more; cap
   lists and say when truncated.
5. **Let the model see.** Viewport/render screenshots come back as MCP image
   content, which is what makes iterative modelling actually work.

### 3.1 Inspect
| Tool | Purpose |
| --- | --- |
| `get_scene_info` | Scene name, frame, units, render engine, object count, collections tree, active/selected |
| `list_objects` | Name, type, parent, collection, location/rotation/scale, visibility; filter by type/collection |
| `get_object_info` | Full detail for one object: transforms, dimensions, bbox, modifiers, materials, constraints, custom props, mesh stats (verts/edges/faces, manifold?, n-gons) |
| `get_mesh_data` | Paginated raw verts/faces for small meshes (hard cap) |
| `list_materials` / `get_material_info` | Principled BSDF inputs, node summary |
| `get_viewport_screenshot` | Render the 3D viewport (OpenGL) to PNG → image content. Args: view (`front`/`top`/`persp`/`camera`…), size, shading mode, frame-selected |
| `render_preview` | Quick Eevee/Cycles render at low res/samples → image content |

### 3.2 Create / edit objects
| Tool | Purpose |
| --- | --- |
| `create_primitive` | cube, uv_sphere, ico_sphere, cylinder, cone, torus, plane, monkey, empty, camera, light — with size/segments/location/rotation/name |
| `transform_object` | set or delta location/rotation (deg)/scale; apply transforms |
| `duplicate_object` / `delete_object` / `rename_object` | |
| `set_parent`, `move_to_collection`, `create_collection` | scene organisation |
| `join_objects`, `separate_mesh` | |
| `boolean` | union/difference/intersect between two objects (modifier, optional apply) |

### 3.3 Modifiers
| Tool | Purpose |
| --- | --- |
| `add_modifier` | type + params dict (subsurf, bevel, mirror, array, solidify, boolean, remesh, decimate, displace, …) |
| `set_modifier_params`, `remove_modifier`, `apply_modifier`, `reorder_modifier` | |

### 3.4 Mesh editing (edit-mode operations done via `bmesh`, not `bpy.ops`, so they don't depend on UI context)
| Tool | Purpose |
| --- | --- |
| `extrude` | faces by index / selection spec, distance along normal |
| `inset`, `bevel_edges`, `subdivide`, `loop_cut` | |
| `select_elements` | select by index, by normal direction, by position predicate (e.g. "faces with z > 0.9") — returns indices |
| `merge_by_distance`, `recalc_normals`, `shade_smooth/flat`, `auto_smooth` | |
| `create_mesh_from_data` | build a mesh from verts/faces lists (lets the model do procedural stuff directly) |

### 3.5 Materials / look
| Tool | Purpose |
| --- | --- |
| `create_material` | Principled BSDF with base color, metallic, roughness, emission, alpha |
| `assign_material` | to object or face indices |
| `set_world` | background color / HDRI path, strength |
| `add_light`, `add_camera`, `look_at` | camera/light placement helpers |

### 3.6 Files & I/O
| Tool | Purpose |
| --- | --- |
| `save_blend` / `open_blend` | path-restricted (see §5) |
| `import_file` | obj, fbx, gltf/glb, stl, ply, usd |
| `export_file` | same formats, selection-only option |
| `undo` / `redo` | wrap `bpy.ops.ed.undo`/`redo` |

### 3.7 Escape hatch
| Tool | Purpose |
| --- | --- |
| `execute_python` | Run a code string on the main thread with `bpy`, `bmesh`, `mathutils` in scope; captures stdout/stderr + a `result` variable. **Disabled unless the add-on preference "Allow arbitrary Python" is on**, and always wrapped in an undo step. |

### 3.8 MCP resources & prompts (nice-to-have)
- Resource `blender://scene` — live scene summary the client can attach as context.
- Resource `blender://docs/{topic}` — short curated notes (bmesh cheatsheet,
  modifier param names) so the model writes correct `execute_python` code.
- Prompt `model_from_reference` — "block out → refine → material → render → compare" loop.

---

## 4. Blender add-on details

- **Threading:** listener thread does only socket I/O. Each request is put on a
  `queue.Queue` together with a `concurrent.futures.Future`. A timer registered
  with `bpy.app.timers.register(drain, persistent=True)` runs every ~20 ms,
  executes queued handlers on the main thread, and resolves the futures. The
  listener thread waits on the future and writes the reply.
- **Context overrides:** anything that must use `bpy.ops` (viewport screenshot,
  some importers) runs inside `bpy.context.temp_override(window=…, area=…,
  region=…)` using the largest `VIEW_3D` area. In `--background` mode there is no
  viewport, so `get_viewport_screenshot` falls back to a Workbench render from an
  auto-framed temporary camera and says so in its result.
- **Mode safety:** handlers ensure OBJECT mode before running and restore the
  user's previous mode/selection/active object afterwards where sensible.
- **Errors:** Python exceptions become JSON-RPC errors with the message and a
  short traceback tail; the MCP server surfaces them as `isError` tool results so
  the model can self-correct.
- **UI:** N-panel tab "MCP" with Start/Stop server, port, connection status,
  last N commands log, and the "Allow arbitrary Python" toggle.
- **Auto-start:** preference to start listening on file load
  (`bpy.app.handlers.load_post`).
- **Packaging:** Blender 4.2+ extension (`blender_manifest.toml`) zipped by
  `scripts/build_addon.py`; installable via drag-and-drop.

---

## 5. Safety

The agent is driving an app on the user's machine, so:

- Listen on **127.0.0.1 only**; random shared token generated by the add-on,
  shown in the panel, passed to the server via `BLENDER_MCP_TOKEN` env (optional
  but recommended).
- `execute_python` off by default (see §3.7).
- File tools restricted to an allowlist of roots (default: the current .blend's
  directory + a configurable workspace dir); refuse paths outside it.
- Every mutation is an undo step; `save_blend` never overwrites without
  `overwrite=true`.
- Per-call timeout (default 30 s, renders 120 s) so a runaway script doesn't hang
  the agent; the add-on can't kill the main thread, so we document that a long
  `execute_python` blocks Blender until it finishes.

---

## 6. Client setup (the whole point: works with both Claude and Codex)

The server is a normal stdio MCP server, so any client works.

**Claude Code**
```bash
claude mcp add blender -- uv run --directory /path/to/blender-mcp blender-mcp
# or check examples/claude-code.mcp.json into a project as .mcp.json
```

**Claude Desktop** (`claude_desktop_config.json`)
```json
{ "mcpServers": { "blender": { "command": "uv",
  "args": ["run", "--directory", "/path/to/blender-mcp", "blender-mcp"] } } }
```

**Codex CLI** (`~/.codex/config.toml`)
```toml
[mcp_servers.blender]
command = "uv"
args = ["run", "--directory", "/path/to/blender-mcp", "blender-mcp"]
env = { BLENDER_MCP_PORT = "9876" }
```

Env vars: `BLENDER_MCP_HOST`, `BLENDER_MCP_PORT`, `BLENDER_MCP_TOKEN`,
`BLENDER_MCP_TIMEOUT`.

Tool descriptions are written client-agnostically (no Claude-specific phrasing)
and kept short, since some clients load every tool description into context.
Consider a `BLENDER_MCP_TOOLSETS=inspect,objects,mesh,…` env to expose only a
subset for clients with tight tool limits.

---

## 7. Testing

- **Unit (fast, no Blender):** server tools against a fake bridge; protocol
  framing round-trips; arg validation.
- **Integration:** pytest fixture launches
  `blender --background --factory-startup --python scripts/start_addon.py`, waits
  for the port, runs real tool calls, asserts on scene state (e.g. "create cube,
  add bevel, apply → vertex count == 24+…"). Viewport tests skipped headless;
  `render_preview` tested with Eevee/Workbench.
- **Agent smoke test (manual, per milestone):** give Claude Code and Codex a
  task like "model a low-poly mug with a handle, red glossy material, render it"
  and keep the transcripts + renders in `examples/` as regression references.
- **CI:** `.github/workflows/blender-mcp.yml` with `paths: [blender-mcp/**]`;
  unit tests on every push, integration job downloads a pinned Blender LTS
  tarball (cached).

---

## 8. Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| **M0** ✅ | Skeleton | uv project, add-on registers, ping/handshake round-trips over the socket, `get_scene_info` works from Claude Code |
| **M1** ✅ | Inspect + see | all §3.1 tools; viewport screenshot + render preview return images the model can view |
| **M2** ✅ | Object-level modelling | §3.2 + §3.3 + undo; agent can block out a simple scene (table + chairs) |
| **M3** ✅ | Materials, lights, camera, I/O | §3.5 + §3.6; agent can produce and export a textured glTF |
| **M4** ✅ | Mesh editing | §3.4 bmesh tools with selection specs; agent can model a mug with a handle |
| **M5** ✅ | Escape hatch + resources | `execute_python` behind pref, docs resources, prompts |
| **M6** | Hardening | token auth, path allowlist, timeouts, integration tests in CI, Codex + Claude setup verified end to end |
| **M7** | Stretch | geometry-nodes helpers, sculpt/remesh helpers, animation keyframes, multi-instance (pick Blender by port), streaming progress for long renders |

---

### M1 notes

- Workbench shows a material's *viewport display* color (`diffuse_color`), not the
  node Base Color. M3's `create_material` should set both so quick previews match.
- The GUI path of `get_viewport_screenshot` (`render.opengl` with `view_context`)
  has not been run in CI yet: the test environment only has headless Blender (the
  `bpy` wheel), so only the Workbench fallback is covered. Verify by hand in the
  Blender app.
- Headless renders need OpenGL; Mesa's software driver works (Workbench ~0.05 s
  per frame at 384 px, EEVEE ~40 s on first use while shaders compile).

### M2 notes

- Edits use `bpy.data`/`bmesh` wherever possible (primitives are built with
  `bmesh.ops`, separate is done in bmesh); only `join`, `transform_apply` and
  `modifier_apply` go through operators, with an explicit context override.
- Every handler first runs `view_layer.update()`: between our calls nothing
  re-evaluates the depsgraph, so bounds/dimensions/world matrices were stale.
- Mutating handlers leave edit mode first (data edits made in edit mode would be
  overwritten on exit), then push an `MCP: <tool>` undo step — also on failure,
  so a partial change is still one Ctrl+Z away.
- A client-side timeout doesn't cancel the command in Blender; a retried edit
  can run twice. Edit timeouts are 120 s to make that unlikely.
- Undo/redo from a timer needs a window in the context override; verified
  headless, not yet in the GUI.

### M3 notes

- Path policy lives in `handlers/paths.py`: workspace (pref / `--workspace`) plus
  the open .blend's folder unless that is `~` or `/`; realpath before checking;
  per-tool extension allowlists; no overwrite by default. Modifier/data path
  properties are still refused entirely.
- `open_blend` passes `use_scripts=False`.
- Bug found by rendering: primitives had no UVs — `bmesh.ops.create_*(calc_uvs=True)`
  silently does nothing unless a UV layer already exists, so textures sampled a
  single texel. Every primitive now gets a `UVMap`, and a test checks it.
- `create_material` keeps `diffuse_color`/`metallic`/`roughness` (viewport display)
  in sync with the BSDF, so Workbench previews match (M1 note resolved).
- Known gap: importers follow references inside the model file (a .gltf's
  buffers/images, an .obj's .mtl textures), which may point outside the allowed
  folders. Only valid image/model data can be loaded that way, but M6 should
  check or sandbox those references.
- Not yet verified in the GUI: `open_blend` from a timer callback.

### M4 notes

- Selection is stateless: every mesh tool takes a `select` spec (all / indices /
  normal+max_angle / position ranges / material / boundary / sharp_angle, ANDed,
  local or world space), validated by a strict Pydantic schema on the server.
- All edits are bmesh on object data (no edit mode, no operators).
- `extrude_face_region` leaves the original faces as internal faces; they are
  deleted (as Blender's operator does), and only the new cap is reported.
- Guard: `subdivide` refuses edits estimated above 2M faces instead of hanging.
- The goal test models a mug: cylinder → inset top → extrude inner face down →
  bevel rim by sharp angle + height → half torus via bisect(fill) → boolean union
  → auto smooth. Result is manifold.

### M5 notes

- Done: resources `blender://scene`, `blender://objects/{name}`, `blender://docs`,
  `blender://docs/{topic}` (workflow, selection, modifiers, materials,
  troubleshooting — shipped as package data); prompts `model_object` and
  `review_scene`; `BLENDER_MCP_TOOLSETS` to expose a subset of tool groups.
- A test checks every modifier type/setting named in docs/modifiers.md exists in
  Blender. It caught that empty ID-pointer settings (e.g. MIRROR `mirror_object`)
  were hidden from `add_modifier` results; they are now reported as null.
- `execute_python` (owner decided to keep it): refused unless the add-on pref
  *and* a token are set — the token requirement is because other accounts on a
  shared machine can reach a localhost port. The gate is enforced in Blender, not
  the server. One undo step per run; stdout/stderr/result capped; tracebacks
  limited to the submitted code; `SystemExit`/`KeyboardInterrupt` from agent code
  become errors instead of stopping Blender's request loop (the main-thread queue
  also converts any BaseException). `keep_session` shares a namespace across runs.
- Found by tests: mathutils types iterate via `__getitem__`, not `__iter__`, so
  results like `Vector` were returned as their repr; fixed.

### Review (after M1)

Probing the listener with hostile input found and fixed: non-ASCII tokens
crashing the connection thread, deeply nested JSON (RecursionError), results
over the 64 MB frame limit dropping the connection, and unauthenticated clients
being able to announce 64 MB messages on unlimited connections. Now: 64 KB limit
before the handshake, at most 8 clients, every failure answered with an error
reply. A browser POSTing to the port is rejected by the framing (the "POST"
bytes read as a ~1.3 GB length). Modifier file-path properties (e.g. Mesh
Cache `filepath`) are refused, since they would allow reading arbitrary local
files back through `get_mesh_data`. Open: with no token (the default) any local
process can drive Blender — the panel now says so; make tokens the default in M6.

## 9. Open questions

- Ship the add-on and server as **one repo-local package** (current plan) or
  publish the server to PyPI? The name `blender-mcp` is already taken there by an
  unrelated project, so publishing needs a new distribution name. Start local,
  decide once M3 is stable.
- ~~Should `execute_python` exist at all?~~ Yes, opt-in with a required token (M5).
- Screenshot size vs. token cost — default 768 px long edge, let the model ask
  for bigger.
- Support Blender < 4.2? Probably not; revisit if someone needs it.
