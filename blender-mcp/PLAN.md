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
  `mcp` SDK (`FastMCP`). Defines tools, validates args, forwards each call to
  Blender, shapes results (text + images) for the model. Has no Blender dependency,
  so it's easy to test and install with `uvx`.
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
│   ├── server.py            ← FastMCP app, tool registration, entrypoint
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
  region=…)` using the first `VIEW_3D` area found. In `--background` mode,
  viewport tools return a clear "not available headless, use render_preview" error.
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
claude mcp add blender -- uvx --from ./blender-mcp blender-mcp
# or check examples/claude-code.mcp.json into a project as .mcp.json
```

**Claude Desktop** (`claude_desktop_config.json`)
```json
{ "mcpServers": { "blender": { "command": "uvx", "args": ["blender-mcp"] } } }
```

**Codex CLI** (`~/.codex/config.toml`)
```toml
[mcp_servers.blender]
command = "uvx"
args = ["blender-mcp"]
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
| **M0** | Skeleton | uv project, add-on registers, ping/handshake round-trips over the socket, `get_scene_info` works from Claude Code |
| **M1** | Inspect + see | all §3.1 tools; viewport screenshot + render preview return images the model can view |
| **M2** | Object-level modelling | §3.2 + §3.3 + undo; agent can block out a simple scene (table + chairs) |
| **M3** | Materials, lights, camera, I/O | §3.5 + §3.6; agent can produce and export a textured glTF |
| **M4** | Mesh editing | §3.4 bmesh tools with selection specs; agent can model a mug with a handle |
| **M5** | Escape hatch + resources | `execute_python` behind pref, docs resources, prompts |
| **M6** | Hardening | token auth, path allowlist, timeouts, integration tests in CI, Codex + Claude setup verified end to end |
| **M7** | Stretch | geometry-nodes helpers, sculpt/remesh helpers, animation keyframes, multi-instance (pick Blender by port), streaming progress for long renders |

---

## 9. Open questions

- Ship the add-on and server as **one repo-local package** (current plan) or
  publish the server to PyPI so `uvx blender-mcp` works without cloning? — Start
  local, publish once M3 is stable.
- Should `execute_python` exist at all? Leaning yes: in practice it's what lets
  the model finish tasks the structured tools don't cover, and it's gated.
- Screenshot size vs. token cost — default 768 px long edge, let the model ask
  for bigger.
- Support Blender < 4.2? Probably not; revisit if someone needs it.
