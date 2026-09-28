# Changelog

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
