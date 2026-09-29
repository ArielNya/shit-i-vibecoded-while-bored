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
checks) — see [Security](#security). M7 adds animation, sculpt-style helpers,
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
| `render_preview` | Quick Workbench / EEVEE / Cycles render from the scene camera or an auto-framed view angle; `ortho`, `textures` and `xray` for comparing against reference images; render settings restored afterwards |
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
| `transform_elements` | Move/rotate/scale selected vertices about a pivot (taper, raise, twist), or fit them to an absolute `size`/`center` |
| `delete_elements` / `merge_by_distance` / `recalc_normals` / `shade` | Clean-up and shading (smooth with an auto-smooth angle) |
| `create_mesh_from_data` | Build a mesh from raw vertices and faces |
| `create_material` / `update_material` | Principled BSDF: color, metallic, roughness, alpha, transmission, emission; image or generated (checker/color grid) textures |
| `assign_material` | Whole object, or specific faces |
| `set_world` | Background color or HDRI, strength, rotation |
| `look_at` / `set_active_camera` / `set_data_params` | Aim cameras/lights, pick the scene camera, change lens/energy/size/... |
| `list_files` | What's in the workspace, and which folders are allowed |
| `save_blend` / `open_blend` | Save (in place or to a path) / open a .blend — embedded scripts never run |
| `import_file` / `export_file` | .obj .fbx .glb/.gltf .stl .ply .usd*; export chosen objects or everything; `roblox=true` for Roblox Studio's FBX settings |
| `execute_python` | Run Python in Blender for anything the tools don't cover — **off by default**, see below |
| `set_keyframe` / `list_keyframes` / `clear_animation` / `set_frame_range` | Keyframe location/rotation (degrees)/scale or object properties; frame range, FPS, current frame |
| `remesh` / `smooth_vertices` / `add_noise` | Voxel remesh, relax vertices, fractal noise displacement — rocks, terrain, clay |
| `find_node_types` / `build_geometry_nodes` / `get_geometry_nodes` | Search node types; build a Geometry Nodes setup from nodes + links; inspect it |
| `add_reference_image` / `set_visibility` | Put a front/side/back reference sheet behind the model at true scale (feet on z=0, head at the given height); hide references or rigs |
| `create_humanoid_rig` / `create_armature` | A 22-bone humanoid skeleton from landmarks measured on the sheet (or average proportions), extra bones for tails/ears/props; or any custom armature |
| `bind_to_armature` / `set_vertex_weights` | Skin meshes (automatic heat weights or nearest bone), limited to 4 influences per vertex and normalised, with a weight report; fix weights on selected vertices |
| `mark_seams` / `uv_unwrap` / `get_uv_info` | UV seams and unwrapping (smart, along seams, or box); reports islands, 0–1 coverage and overlaps |
| `bake_maps` | Bake normal / AO / colour / roughness from high-poly meshes onto a low-poly one (Cycles), saved as PNGs and wired into its material |
| `check_game_ready` | One-call validation: transforms, placement, n-gons, holes, loose/doubled vertices, normals, triangle budget, UVs, materials, skin weights |
| `pose_bone` / `reset_pose` / `get_armature_info` | Pose (optionally mirrored to the other side) and keyframe bones; +X is the natural bend on the humanoid rig |
| `bake_texture` | Unwrap a mesh to a fresh UV map and bake all its materials' colour into one PNG and one material (game engines, Roblox) |
| `check_roblox_asset` | Check a rigid accessory, layered clothing or character body against Roblox's specs: triangles, watertight, one material/UV/texture, size around the attachment, cages, R15 bones, influences |
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
| `blender://docs` + `blender://docs/{topic}` | Reference notes: `efficiency`, `workflow`, `selection`, `modifiers`, `materials`, `troubleshooting`, `game-character`, `character`, `character-highpoly`, `rigging`, `img2model` |
| prompt `model_object(subject, details, style)` | A staged modelling workflow with visual checks |
| prompt `review_scene` | Audit the scene for modelling problems, report without changing anything |
| prompt `model_character(front, side, height, style)` | Build a rigged low-poly character from a reference sheet (follows `blender://docs/character`) |
| prompt `image_to_model(images, subject, budget, output)` | Model something from images within a triangle budget (follows `blender://docs/img2model`) |

### Skills

A skill suite in [`skills/`](skills/) teaches agents to use these tools well. Each
skill is a `SKILL.md` plus reference notes:

| Skill | For | Covers |
| --- | --- | --- |
| [`blender-mcp`](skills/blender-mcp/SKILL.md) | every session | the build/verify loop, **token-efficient** checks (numbers before pictures, image sizes and their cost, trimming toolsets), selection rules, **polygon budgets** per platform, LODs |
| [`game-character`](skills/game-character/SKILL.md) | characters, creatures, mascots, avatars | **rig-ready** standards (bind pose, deforming topology, UVs, parts, budgets), then routes: low poly from a front/side sheet, high poly (subdivision cage for film; high → low normal-map bakes for games), rigging, skinning, pose tests, animation, LODs and export for Unity, Unreal, Godot, Mixamo |
| [`img2model`](skills/img2model/SKILL.md) | "model this image" | classifying the input (ortho sheet, single view, perspective, photos), a one-time shape inventory, reference planes or a matching camera, silhouette checks, refining to a budget |

The skills are generated from `src/blender_mcp/docs/` (`python scripts/build_addon.py
--sync`), and the server serves the same notes as `blender://docs/<topic>`. Clients
without skill support get them through the resources and the `model_character` /
`image_to_model` prompts.

- **Claude Code:** copy the folders into your skills. For every project, run
  `cp -r skills/* ~/.claude/skills/`; for one project, use `.claude/skills/` in that
  repo. Claude picks the right one from the request, or you can invoke them with
  `/game-character`, `/img2model` or `/blender-mcp`.
- **Claude Desktop / claude.ai:** zip each skill folder and upload it under
  *Settings → Capabilities → Skills*.
- **Codex:** recent Codex CLI versions read the same `SKILL.md` format from
  `~/.codex/skills/`: `cp -r skills/* ~/.codex/skills/`.
- **Any MCP client (dsh included):** use the prompts, or tell the agent to read
  `blender://docs/efficiency` first. No install is needed.

[`skills/roblox-avatar`](skills/roblox-avatar/SKILL.md) covers **Roblox avatar items**:
rigid accessories (hats, hair, wings…), layered clothing (cages, skinning) and character
bodies, from Blender through `bake_texture`, `check_roblox_asset` and
`export_file(roblox=true)` to Studio (Accessory Fitting Tool, an Accessory by script,
trying it on, uploading). Its references hold Roblox's size tables, budgets and naming
rules, and where to download the official templates. It installs like the others
(`cp -r skills/* ~/.claude/skills/` includes it). Unlike the three above, it is
written by hand, not generated from `docs/`. For the Studio side, pair it with
roblox-mcp's `roblox-studio` skill. It was tested by an agent making an Umbreon hat; see
[`examples/roblox-umbreon-hat/`](examples/roblox-umbreon-hat/).

Examples: *"build a rigged low-poly character from ref_front.png and ref_side.png,
1.6 m, mobile budget"*, *"model the chest in chest.jpg for a mobile game, under 300
triangles"*, *"make a high-poly version of Body and bake its normals onto the low
one"*.

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

Two parts: the **add-on** runs inside Blender, and the **server** is started by your
AI client. Install the add-on once, then register the server with every client you
use. No token setup is needed: the add-on writes a private token file and the
server reads it (see [Security](#security)).

### 1. Install the Blender add-on

Get `blender_mcp_addon-<version>.zip` from the
[Releases](https://github.com/ArielNya/shit-i-vibecoded-while-bored/releases) page, or
build it from a clone:

```bash
git clone https://github.com/ArielNya/shit-i-vibecoded-while-bored.git
cd shit-i-vibecoded-while-bored/blender-mcp
python3 scripts/build_addon.py        # writes dist/blender_mcp_addon-<version>.zip
```

In Blender: *Edit → Preferences → Get Extensions → ⌄ (top right) → Install from Disk…*
and pick the zip. Then open the 3D Viewport sidebar (`N`) → **MCP** tab → **Start MCP
Listener**. Tick *Start automatically* in the add-on preferences to skip that step
next time.

For development, load the add-on straight from the repo instead of installing it:
`blender --python scripts/run_in_blender.py`.

### 2. The server command

Every client below runs the same command. It needs [uv](https://docs.astral.sh/uv/);
`uvx` downloads the server into a cache on first use.

```bash
uvx --from "git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=blender-mcp" blender-mcp
```

- **Pin a release:** replace `@main` with a tag, e.g. `@blender-mcp-v0.7.0`, or use
  the release's wheel URL: `uvx --from https://github.com/ArielNya/shit-i-vibecoded-while-bored/releases/download/blender-mcp-v0.7.0/blender_mcp-0.7.0-py3-none-any.whl blender-mcp`.
- **From a clone** (for development): `uv run --directory /path/to/blender-mcp blender-mcp`.
- **Don't** use `uvx blender-mcp` alone: that name on PyPI is a different project.
- **GUI apps and `uvx`:** desktop apps often don't inherit your shell's PATH. If a
  client says it can't find `uvx`, use its full path (`which uvx` on macOS/Linux,
  `where uvx` on Windows) as the command.

In the snippets below, `SERVER_SPEC` stands for
`git+https://github.com/ArielNya/shit-i-vibecoded-while-bored@main#subdirectory=blender-mcp`.
Ready-to-copy versions with it filled in are in [`examples/`](examples/):
`claude-code.mcp.json`, `claude_desktop_config.json`, `codex.config.toml`,
`dsh.cordis.patch.yml`.

### 3. Register it with your client

<details open>
<summary><b>Claude Code</b></summary>

Command (available in all your projects):

```bash
claude mcp add blender -s user -- uvx --from "SERVER_SPEC" blender-mcp
claude mcp list          # blender … ✓ Connected
```

Use `-s project` instead to share it with a repository's collaborators; that writes
`.mcp.json` in the project root. Or create that file by hand:

```json
{
  "mcpServers": {
    "blender": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "SERVER_SPEC", "blender-mcp"],
      "env": {}
    }
  }
}
```

Start a new session afterwards; `/mcp` inside Claude Code shows the server and its tools.
</details>

<details>
<summary><b>Claude Desktop</b></summary>

*Settings → Developer → Edit Config* opens `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add (merge into an existing `mcpServers` block if there is one):

```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["--from", "SERVER_SPEC", "blender-mcp"]
    }
  }
}
```

Quit and restart Claude Desktop. The tools appear under the tools/connectors menu in
the chat box. If it can't start the server, put the full path to `uvx` in `command`.
</details>

<details>
<summary><b>Codex CLI</b></summary>

Command:

```bash
codex mcp add blender -- uvx --from "SERVER_SPEC" blender-mcp
codex mcp list           # blender … enabled
```

That writes `~/.codex/config.toml`. By hand, plus a longer tool timeout so renders
and remeshes can finish:

```toml
[mcp_servers.blender]
command = "uvx"
args = ["--from", "SERVER_SPEC", "blender-mcp"]
tool_timeout_sec = 300
```

Environment variables go in an `env` table, e.g.
`env = { BLENDER_MCP_TOOLSETS = "inspect,view,edit,mesh,look" }` (or `--env KEY=VALUE`
on `codex mcp add`).
</details>

<details>
<summary><b>DeepSeek Harness (dsh)</b></summary>

dsh connects MCP servers through its official `@deepseek-ai/dsh-mcp-client` plugin:
one entry per server in `cordis.patch.yml` (or a file passed with `--patch`):

```yaml
- id: mcp-blender
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: blender
    transport: stdio
    command: /full/path/to/uvx                 # `which uvx`
    args: ['--from', 'SERVER_SPEC', 'blender-mcp']
    env:
      HOME: !!js process.env.HOME              # the server finds the token file here
    toolCallTimeoutMs: 300000                  # renders/remesh can exceed the 60 s default
```

Tools appear as `mcp__blender__<tool>`, e.g. `mcp__blender__create_primitive`.
Notes: dsh starts servers with a scrubbed environment (hence the full `uvx` path and
`HOME`); it doesn't support MCP prompt templates, so `model_object` / `review_scene`
aren't available there (tools and `blender://docs` resources are). This entry follows
the [dsh MCP client docs](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
and hasn't been tested here yet.
</details>

<details>
<summary><b>Any other MCP client</b></summary>

It's a standard stdio server: command `uvx`, arguments
`--from SERVER_SPEC blender-mcp`, plus any of the environment variables under
[Configuration](#configuration).
</details>

<details>
<summary><b>Windows / PowerShell (from a clone)</b></summary>

[`scripts/install.ps1`](scripts/install.ps1) runs the server straight out of this
clone (`uv run --directory`, no `uvx` fetch) and registers it for you:

```powershell
./scripts/install.ps1 -Harness claude-code    # or claude-desktop / codex
```

`-Harness` is the only required parameter (blender-mcp has no `--project` flag, so
`-ProjectPath` just picks where `claude mcp add -s project` writes `.mcp.json`; it
defaults to the current directory). Requires `uv` and, for the `claude-code`/`codex`
harnesses, that CLI on `PATH`.
</details>

### 4. Try it

With Blender running and the add-on started, ask the agent something like *"ping
Blender and tell me what's in the scene"*, then *"model a mug with a handle"*.

Verified end to end with Claude Code 2.1 (the agent created objects in Blender through
the server) and Codex CLI 0.157 (config parsed, server listed as enabled).

### Configuration

| Env var (server) | Default | Meaning |
| --- | --- | --- |
| `BLENDER_MCP_HOST` | `127.0.0.1` | Where the add-on is listening |
| `BLENDER_MCP_PORT` | `9876` | Must match the port in the add-on panel |
| `BLENDER_MCP_TOKEN` | token file | Only needed if the add-on uses a custom token |
| `BLENDER_MCP_TOKEN_FILE` | per-user path above | Where to find the token file (both sides honour it) |
| `BLENDER_MCP_TIMEOUT` | `30` | Seconds to wait for Blender per call |
| `BLENDER_MCP_TOOLSETS` | all | Comma-separated subset to expose, for clients with tool limits: `inspect`, `view`, `edit`, `mesh`, `sculpt`, `nodes`, `animate`, `rig`, `gameready`, `look`, `files`, `python`, `instances`, `roblox` |

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
```

blender-mcp no longer has a test suite in this repo; lint before pushing.

### Releasing

Bump the version (pyproject, `__init__`, add-on manifest and `bl_info` — keep them
in sync) and add a `CHANGELOG.md` section. Build the add-on zip with
`python3 scripts/build_addon.py` and the server with `uv build`.

`src/blender_mcp/protocol.py` is vendored into the add-on. After editing it, run
`python3 scripts/build_addon.py --sync` to keep the copies identical.
