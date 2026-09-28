# Modelling workflow

A loop that works well with these tools:

1. **Look first.** `get_scene_info`, then `list_objects`. Don't assume the default
   cube/camera/light exist — the user may have changed the scene.
2. **Block out** with `create_primitive`. Use real-world units (1 unit = 1 m by
   default). Always use the `name` returned by a create call: Blender renames on
   clashes (`Cube.001`).
3. **Check visually** after every few changes: `get_viewport_screenshot` (fast,
   `view` = front/top/iso to see from angles) or `render_preview` (materials and
   lighting). Compare against what was asked.
4. **Refine shape**: `apply_transform` before bevels or mesh edits on scaled
   objects (otherwise bevel widths get stretched). Then `extrude` / `inset` /
   `bevel` / `loop_cut` / `transform_elements` for mesh-level detail.
5. **Non-destructive first**: prefer modifiers (`SUBSURF`, `BEVEL`, `MIRROR`,
   `SOLIDIFY`, `ARRAY`) over applying changes; apply only when needed (e.g. before
   exporting to formats that ignore modifiers, or before mesh edits that depend on
   the result).
6. **Materials and light**: `create_material` + `assign_material`, `set_world` for
   ambient light, an AREA or SUN light, `look_at` to aim camera and lights.
7. **Verify geometry**: `get_object_info` → `mesh.is_manifold`,
   `non_manifold_edges`, `ngons`. Watertight meshes matter for booleans, 3D
   printing and clean subdivision.
8. **Save/export**: `save_blend`, `export_file` (`.glb` keeps materials and
   textures).

Mistakes are cheap: every tool call is one undo step, and `undo` reverts it.

## Beyond basic modelling

- **Organic shapes**: start from an `ico_sphere` (subdivisions 4–5) or `remesh` a
  blockout, then `add_noise` (strength ≈ 10–30 % of the size) and `smooth_vertices`;
  `shade` with an auto-smooth angle around 60.
- **Many copies** (pebbles, grass, bolts): `build_geometry_nodes` with
  DistributePointsOnFaces → InstanceOnPoints; `find_node_types` finds type ids and
  the result lists every socket name to link.
- **Animation**: `set_keyframe` at two or more frames, `set_frame_range`, then check
  with `set_frame_range(current=...)` + `get_viewport_screenshot`.
- **Several Blenders**: `list_blender_instances`, then `use_blender(port)`.

## Size and placement tips

- `dimensions` on `transform_object` sets the final bounding-box size directly.
- Objects sit on the ground when `location.z = height / 2` for primitives created
  at their center (cube, sphere, cylinder).
- `set_parent` keeps world position, so you can parent after placing parts.
- For symmetric models, model one half, then add a `MIRROR` modifier
  (`bisect` with `keep` removes the other half first).
