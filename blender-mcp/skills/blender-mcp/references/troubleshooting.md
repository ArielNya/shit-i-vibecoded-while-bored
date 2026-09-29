# Troubleshooting

| Symptom | Likely cause → fix |
| --- | --- |
| "Could not connect to Blender" | Blender not running, add-on not started (3D Viewport sidebar → MCP → Start), or port mismatch with `BLENDER_MCP_PORT` |
| "invalid token" | `BLENDER_MCP_TOKEN` differs from the add-on's token |
| "No object named 'X'" | Names are exact and case-sensitive; the error lists existing objects. Creation may have returned `X.001` |
| "the selection matched no faces" | Check with `select_elements`; normals are in local space unless `space: "world"`; widen `max_angle` |
| Stretched bevels | Object is scaled → `apply_transform` first |
| Boolean did nothing / looks wrong | Cutter must overlap the target and both should be manifold; try `solver: "EXACT"`; check `get_object_info` → `is_manifold` |
| Black or dark faces | Flipped normals → `recalc_normals`; or no light: `set_world` / add a light |
| Faceted look on curved surfaces | `shade(smooth=true, auto_smooth_angle=30)` |
| Texture is one flat color | Mesh has no UVs (raw meshes from `create_mesh_from_data`) |
| Render too dark | Raise light `energy` or world `strength`; area lights need hundreds of watts |
| Path "outside the folders this add-on may use" | Use a relative path (goes in the workspace) — see `list_files` for allowed folders |
| Timeout | Blender was busy (long render/boolean). The command may still finish — check the scene before retrying to avoid doing it twice |
| Indices out of range after an edit | Indices change when topology changes; use the indices the last tool returned |
