# blender-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI coding agents
(Claude Code, Claude Desktop, OpenAI Codex, anything MCP-speaking) look at and
build things inside a running Blender session.

**Status:** M2 — the agent can inspect the scene, *see* it (screenshots and renders
come back as images), and do object-level modelling: primitives, transforms,
parenting, collections, booleans and modifiers. Every change is one named undo
step in Blender (`MCP: …`), so Ctrl+Z reverts what the agent did. Mesh editing,
materials and file I/O come next. See [`PLAN.md`](PLAN.md) for the roadmap.

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

## Requirements

- Blender 4.2 LTS or newer
- [uv](https://docs.astral.sh/uv/) (Python 3.11+ is fetched automatically)

## Setup

### 1. Install the Blender add-on

```bash
cd blender-mcp
python3 scripts/build_addon.py        # writes dist/blender_mcp_addon-0.1.0.zip
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

Then ask the agent something like *"what's in my Blender scene?"*.

> Don't use `uvx blender-mcp`: that name on PyPI belongs to a different project.

### Configuration

| Env var (server) | Default | Meaning |
| --- | --- | --- |
| `BLENDER_MCP_HOST` | `127.0.0.1` | Where the add-on is listening |
| `BLENDER_MCP_PORT` | `9876` | Must match the port in the add-on panel |
| `BLENDER_MCP_TOKEN` | — | Must match the add-on's token, if one is set |
| `BLENDER_MCP_TIMEOUT` | `30` | Seconds to wait for Blender per call |

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

`src/blender_mcp/protocol.py` is vendored into the add-on. After editing it, run
`python3 scripts/build_addon.py --sync` (a unit test fails if the copies drift).
