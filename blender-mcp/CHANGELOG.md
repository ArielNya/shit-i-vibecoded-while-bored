# Changelog

## Unreleased

- Roblox avatar items: `bake_texture` bakes every material's colour into one PNG on a
  fresh UV map, leaving one material and one UV map. `check_roblox_asset` checks rigid
  accessories, layered clothing and character bodies against Roblox's specifications
  (triangle budgets, watertight, size around the attachment, cages, R15 bones, 4
  influences, `_Att` attachments). `export_file(roblox=true)` uses Roblox's FBX
  settings: embedded textures, FBX Unit Scale, no leaf bones.
- New skill `skills/roblox-avatar`: hats, clothing and bodies from Blender to a worn
  Roblox accessory, with reference pages for each kind and for the Studio side.
- Game-ready tools (toolset `gameready`): `mark_seams`, `uv_unwrap` (smart / seams /
  cube, with island and coverage report), `get_uv_info`, `bake_maps` (Cycles high→low
  normal, AO, colour and roughness bakes, saved to the workspace and wired into the
  material), and `check_game_ready` (one-call validation of transforms, placement,
  topology, triangle budget, UVs, materials and skin weights).
- `bind_to_armature` limits each vertex to `max_influences` bones (default 4) and
  normalises the weights, and puts its Armature modifier first in the stack.
- Skill suite in `skills/` (replaces `lowpoly-character`): `blender-mcp` (token- and
  polygon-efficient use), `game-character` (rig-ready characters, low and high poly, rigging and export per
  engine) and `img2model` (models from images). Generated from the reference notes,
  which the server also serves (`efficiency`, `game-character`, `character`,
  `character-highpoly`, `rigging`, `img2model`), plus the `model_character` and
  `image_to_model` prompts.

## 0.8.0

- Rigging: `create_humanoid_rig` builds a 22-bone humanoid skeleton from landmarks
  measured on a reference sheet, with rolls chosen so +X rotation is the natural bend.
  Also `create_armature` (any skeleton), `bind_to_armature` (automatic or nearest
  weights, with a weight report), `set_vertex_weights`, `pose_bone` (with `mirror`
  and keyframes), `reset_pose` and `get_armature_info`.
- Reference sheets: `add_reference_image` places front/side/back images at true scale
  from pixel landmarks; `set_visibility` hides references or rigs.
- `render_preview` gains `ortho`, `textures` and `xray` for comparing against
  references. `transform_elements` gains absolute `size`/`center` fitting and reports
  the new bounds.
- `list_keyframes` reads pose-bone channels.
- New skill `skills/lowpoly-character` (also `blender://docs/character` and the
  `model_character` prompt): a low-poly character from a front + side sheet, modelled,
  rigged, skinned, pose-tested, animated and exported. (Superseded by
  `game-character`, see Unreleased.)
- Fix: a tool parameter named `method` (as in `bind_to_armature`) clashed with the
  internal call helper.

## 0.7.0

- Animation: `set_keyframe`, `list_keyframes`, `clear_animation`, `set_frame_range`.
- Sculpt-style helpers: `remesh` (voxel), `smooth_vertices`, `add_noise` (fractal
  displacement for rocks, terrain, clay).
- Geometry Nodes: `build_geometry_nodes` from a node/link description,
  `get_geometry_nodes`, `find_node_types`.
- Several Blenders at once: the add-on takes the next free port when its port is
  busy; `list_blender_instances` and `use_blender` pick which one the tools use.
- Progress notifications while long operations run (renders, file I/O, booleans,
  remesh, `execute_python`, …).
- Fix: on Windows the add-on's port could be shared with another process
  (`SO_REUSEADDR`); it now binds exclusively.

## 0.6.0

- Automatic authentication through a per-user token file; 10 s handshake deadline.
- Imports refuse or remove references to files outside the allowed folders.
- CI workflow; verified with the Claude Code and Codex CLIs.

## 0.5.x

- Reference docs as MCP resources, `model_object` / `review_scene` prompts,
  `BLENDER_MCP_TOOLSETS`, opt-in `execute_python`.

## 0.1–0.4 (M0–M4)

- Bridge and add-on, scene inspection, screenshots and renders, object and mesh
  modelling with undo, materials, lighting, and path-restricted file I/O.
