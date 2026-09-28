# blender-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI coding agents
(Claude Code, Claude Desktop, OpenAI Codex, anything MCP-speaking) look at and
build things inside a running Blender session.

**Status:** M4 — the agent can inspect the scene, *see* it (screenshots and renders
come back as images), model at the object and mesh level (primitives, booleans,
modifiers, extrude/inset/bevel/loop cuts/bisect, raw meshes), set up materials,
textures, lighting and cameras, and save/open/import/export files. The test suite
models a mug with a handle using only tool calls. Every change is one named undo
step in Blender (`MCP: …`). M5 adds reference notes, workflow prompts, and an
opt-in `execute_python` escape hatch; M6 hardens it (automatic per-user auth, import
checks, CI) — see [Security](#security). M7 adds animation, sculpt-style helpers,
Geometry Nodes, several Blenders at once, and progress updates on long operations. See [`PLAN.md`](PLAN.md) for the roadmap.

```
agent ──stdio/MCP──▶ blender-mcp server ──TCP 127.0.0.1:9876──▶ Blender add-on ──▶ bpy (main thread)
```

## Tools

| Tool | What it does |
| --- | --- |
| `ping` | Check the connection; Blender and add-on versions |
| `get_scene_info` | Scene summary: units, frame range, render engine, object counts, selection, collection tree |
| `list_objects` | Objects with transforms, dimensions, visibility; filter by type/collection/name; paginated |
| `get_object_info` | One object in depth: modifiers + settings, materials, constraints, bounds, mesh topology (manifold, n-gons, post-modifier counts), camera/light data |
| `get_mesh_data` | Raw vertices/faces, local or world space, optionally with modifiers applied; paginated |
| `list_materials` / `get_material_info` | Materials, who uses them, Principled BSDF inputs, node graph |
| `get_viewport_screenshot` | Image of the 3D viewport; optional view angle (front/top/iso/…), shading mode, and object framing. The user's view is restored afterwards |
| `render_preview` | Quick Workbench / EEVEE / Cycles render from the scene camera or an auto-framed view angle; render settings restored afterwards |
| `create_primitive` | cube, plane, grid, circle, uv/ico sphere, cylinder, cone, torus, monkey, empty, camera, light — with size/segments/location/rotation/scale |
| `transform_object` / `apply_transform` | Set or offset location/rotation (degrees)/scale/dimensions; bake transforms into the mesh |
| `duplicate_object` / `rename_object` / `delete_objects` | Copies (full or linked), renames, deletes |
| `set_parent` / `create_collection` / `move_to_collection` | Scene organisation; parenting keeps world position |
| `join_objects` / `separate_mesh` | Merge meshes; split by loose parts or material |
| `boolean` | Difference/union/intersect with another mesh, applied or live; cutter hidden/deleted/kept |
| `add_modifier` / `set_modifier_params` / `move_modifier` / `apply_modifier` / `remove_modifier` | Any modifier type; params by Blender property name, angles in degrees, objects by name |
| `undo` / `redo` | Step through Blender's undo history |
| `select_elements` | Preview a selection spec: matching face/edge/vertex indices, with centers and normals |
| `extrude` / `inset` / `bevel` | Region or per-face extrude (returns the new cap faces), inset with depth, edge bevels |
| `loop_cut` / `subdivide` / `bisect` | Edge loops across quad strips, subdivision, plane cuts that can discard and cap a side |
| `transform_elements` | Move/rotate/scale selected vertices about a pivot (taper, raise, twist) |
| `delete_elements` / `merge_by_distance` / `recalc_normals` / `shade` | Clean-up and shading (smooth with an auto-smooth angle) |
| `create_mesh_from_data` | Build a mesh from raw vertices and faces |
| `create_material` / `update_material` | Principled BSDF: color, metallic, roughness, alpha, transmission, emission; image or generated (checker/color grid) textures |
| `assign_material` | Whole object, or specific faces |
| `set_world` | Background color or HDRI, strength, rotation |
| `look_at` / `set_active_camera` / `set_data_params` | Aim cameras/lights, pick the scene camera, change lens/energy/size/... |
| `list_files` | What's in the workspace, and which folders are allowed |
| `save_blend` / `open_blend` | Save (in place or to a path) / open a .blend — embedded scripts never run |
| `import_file` / `export_file` | .obj .fbx .glb/.gltf .stl .ply .usd*; export chosen objects or everything |
| `execute_python` | Run Python in Blender for anything the tools don't cover — **off by default**, see below |
| `set_keyframe` / `list_keyframes` / `clear_animation` / `set_frame_range` | Keyframe location/rotation (degrees)/scale or object properties; frame range, FPS, current frame |
| `remesh` / `smooth_vertices` / `add_noise` | Voxel remesh, relax vertices, fractal noise displacement — rocks, terrain, clay |
| `find_node_types` / `build_geometry_nodes` / `get_geometry_nodes` | Search node types; build a Geometry Nodes setup from nodes + links; inspect it |
| `list_blender_instances` / `use_blender` | Find every running Blender with the add-on (each takes the next free port) and switch between them |

Long operations (renders, file I/O, booleans, remesh, `execute_python`, …) send
progress notifications with the elapsed time, so clients show activity while Blender
works.

### `execute_python` (opt-in)

Arbitrary Python runs with your user account's full permissions, so it stays off
unless you turn on **Allow arbitrary Python** in the add-on preferences. It also
requires authentication (on by default, see [Security](#security)). Each run
is one undo step; `print()` output and a `result` variable come back to the agent.
Blender is busy while the code runs, and a timeout doesn't stop it.

### Resources and prompts

| URI / prompt | What it gives the agent |
| --- | --- |
| `blender://scene` | Live scene summary |
| `blender://objects/{name}` | Live details of one object |
| `blender://docs` + `blender://docs/{topic}` | Reference notes: `workflow`, `selection`, `modifiers`, `materials`, `troubleshooting` |
| prompt `model_object(subject, details, style)` | A staged modelling workflow with visual checks |
| prompt `review_scene` | Audit the scene for modelling problems, report without changing anything |

### Selecting mesh elements

Mesh tools don't use Blender's edit-mode selection. Each takes a `select` spec
whose criteria must all match:

```json
{"normal": [0, 0, 1], "max_angle": 10}                faces pointing up
{"position": {"axis": "z", "min": 0.9}}                centers above z = 0.9
{"sharp_angle": 30}                                    edges meeting at >= 30 degrees
{"indices": [3, 4]}   {"material": "Glass"}   {"boundary": true}   {"all": true}
```

Tools return the indices of what they created (e.g. an extrude's new cap), which
stay valid until the next topology change, so steps chain without guessing.

## Security

- **Authentication is automatic.** When the add-on starts it creates a random token
  in a file only your OS user can read (`~/.config/blender-mcp/token` on Linux,
  `~/Library/Application Support/blender-mcp/token` on macOS,
  `%APPDATA%\blender-mcp\token` on Windows); the server reads the same file. Other
  accounts on the machine can reach the localhost port but can't connect. A custom
  token in the add-on preferences (with `BLENDER_MCP_TOKEN` for the server) overrides
  it; **Copy Token** in the panel helps when the server can't read the file.
- **Localhost only**, at most 8 connections, 10 s to authenticate, small messages
  until authenticated.
- **Files**: file tools only touch the **workspace folder** (add-on preference;
  default `~/BlenderMCP`) and the open .blend's folder — unless that is your home
  folder or a filesystem root. Paths are checked after following symlinks, each tool
  accepts only its own file types, and nothing is overwritten without
  `overwrite=true`. Imports that reference files elsewhere (.gltf/.glb, .obj/.mtl)
  are refused; anything other formats load from elsewhere is removed after import.
  Opening a .blend never runs its embedded scripts.
- **`execute_python`** is off unless you enable it.
- **Undo**: every change is one named undo step (`MCP: …`).
- The server tells the agent that scene content (names, text, imported files) is
  data, not instructions.

## Requirements

- Blender 4.2 LTS or newer
- [uv](https://docs.astral.sh/uv/) (Python 3.11+ is fetched automatically)

## Setup

### Quick install from a release

Download from the [Releases](https://github.com/ArielNya/shit-i-vibecoded-while-bored/releases) page (tags `blender-mcp-v*`):

1. `blender_mcp_addon-<version>.zip` → Blender: *Edit → Preferences → Get Extensions →
   ⌄ → Install from Disk…*, then 3D Viewport sidebar (`N`) → **MCP** → **Start**.
2. The server wheel: `claude mcp add blender -- uvx --from <wheel URL> blender-mcp`
   (Codex: the same `uvx --from <wheel URL> blender-mcp` as the command).

### 1. Install the Blender add-on (from source)

```bash
cd blender-mcp
python3 scripts/build_addon.py        # writes dist/blender_mcp_addon-<version>.zip
```

In Blender: *Edit → Preferences → Get Extensions → ⌄ → Install from Disk…* and pick the
zip. Then open the 3D Viewport sidebar (`N`) → **MCP** tab → **Start MCP Listener**.
Tick *Start automatically* in the add-on preferences to skip that step next time.

For development, load the add-on straight from the repo instead of installing it:

```bash
blender --python scripts/run_in_blender.py
```

### 2. Point your agent at the server

**Claude Code**

```bash
claude mcp add blender -- uv run --directory /path/to/blender-mcp blender-mcp
```

**Codex CLI** — add to `~/.codex/config.toml`:

```toml
[mcp_servers.blender]
command = "uv"
args = ["run", "--directory", "/path/to/blender-mcp", "blender-mcp"]
```

**Claude Desktop** — see [`examples/claude-code.mcp.json`](examples/claude-code.mcp.json);
the same `mcpServers` block goes in `claude_desktop_config.json`.

Then ask the agent something like *"what's in my Blender scene?"*. No token setup is
needed: the server finds the add-on's token file on its own.

Verified end to end with Claude Code 2.1 (the agent created objects in Blender through
the server) and with Codex CLI 0.157 (`codex mcp list` shows the server enabled).

> Don't use `uvx blender-mcp`: that name on PyPI belongs to a different project.

### Configuration

| Env var (server) | Default | Meaning |
| --- | --- | --- |
| `BLENDER_MCP_HOST` | `127.0.0.1` | Where the add-on is listening |
| `BLENDER_MCP_PORT` | `9876` | Must match the port in the add-on panel |
| `BLENDER_MCP_TOKEN` | token file | Only needed if the add-on uses a custom token |
| `BLENDER_MCP_TOKEN_FILE` | per-user path above | Where to find the token file (both sides honour it) |
| `BLENDER_MCP_TIMEOUT` | `30` | Seconds to wait for Blender per call |
| `BLENDER_MCP_TOOLSETS` | all | Comma-separated subset to expose, for clients with tool limits: `inspect`, `view`, `edit`, `mesh`, `sculpt`, `nodes`, `animate`, `look`, `files`, `python`, `instances` |

## Development

```bash
uv sync
uv run pytest                 # unit tests; no Blender needed
uv run ruff check . && uv run ruff format --check .
```

Integration tests run the add-on inside a real headless Blender. Rendering needs
OpenGL; on a Linux box without a GPU install Mesa (`apt install libegl1 libgl1-mesa-dri`). Point them at
either a Blender binary or a Python that has the `bpy` wheel:

```bash
BLENDER_BIN=/path/to/blender uv run pytest tests/integration
# or
uv venv -p 3.11 /tmp/bpyenv && uv pip install -p /tmp/bpyenv/bin/python "bpy>=4.2,<4.3"
BLENDER_PYTHON=/tmp/bpyenv/bin/python uv run pytest tests/integration
```

### Releasing

Bump the version (pyproject, `__init__`, add-on manifest and `bl_info` — a test checks
they match), add a `CHANGELOG.md` section, then push a tag `blender-mcp-v<version>`.
The release workflow checks, builds the add-on zip and the server wheel/sdist, and
publishes a GitHub release with the changelog section as notes.

`src/blender_mcp/protocol.py` is vendored into the add-on. After editing it, run
`python3 scripts/build_addon.py --sync` (a unit test fails if the copies drift).
