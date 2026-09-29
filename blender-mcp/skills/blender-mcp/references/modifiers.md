# Common modifiers and their settings

`add_modifier(object, type, params)` takes Blender's property names. Angles are
in degrees; object/collection settings take names. A wrong key returns the list of
valid ones, so it's safe to guess and correct.

| Type | Useful params | Notes |
| --- | --- | --- |
| `SUBSURF` | `levels` (viewport), `render_levels`, `subdivision_type` (`CATMULL_CLARK`/`SIMPLE`) | Smooths; add a `BEVEL` or loop cuts first to keep edges crisp |
| `BEVEL` | `width`, `segments`, `limit_method` (`NONE`/`ANGLE`/`WEIGHT`), `angle_limit`, `profile` | `apply_transform` first on scaled objects |
| `MIRROR` | `use_axis` ([x, y, z] bools), `use_clip`, `use_mirror_merge`, `merge_threshold`, `mirror_object` | Model the +X half; `use_clip` stops verts crossing the seam |
| `SOLIDIFY` | `thickness`, `offset` (-1..1), `use_even_offset` | Gives planes/shells thickness |
| `ARRAY` | `count`, `relative_offset_displace` ([x, y, z]), `use_relative_offset`, `use_constant_offset`, `constant_offset_displace`, `offset_object` | Rows of repeated parts; `offset_object` (an empty) for radial arrays |
| `BOOLEAN` | `operation` (`DIFFERENCE`/`UNION`/`INTERSECT`), `object`, `solver` (`EXACT`/`FAST`) | The `boolean` tool is simpler |
| `REMESH` | `mode` (`VOXEL`/`SMOOTH`/`SHARP`/`BLOCKS`), `voxel_size` | Cleans messy topology; small voxel size = many faces |
| `DECIMATE` | `decimate_type` (`COLLAPSE`/`UNSUBDIV`/`DISSOLVE`), `ratio` | Reduce face count |
| `WELD` | `merge_threshold` | Like merge_by_distance, non-destructive |
| `DISPLACE` | `strength`, `mid_level`, `direction` | Needs a texture for detail |
| `SCREW` | `angle`, `steps`, `screw_offset`, `axis` | Lathe a profile curve/edge around an axis |
| `TRIANGULATE` | `quad_method`, `ngon_method` | Before export to engines that need tris |
| `SIMPLE_DEFORM` | `deform_method` (`TWIST`/`BEND`/`TAPER`/`STRETCH`), `angle`, `factor`, `deform_axis` | Quick twists and bends |

## Order matters

Modifiers run top to bottom. Typical stacks:

- Hard-surface: `MIRROR` → `BEVEL` → `SUBSURF` (optional) → `WELD`
- Shells: `SOLIDIFY` → `BEVEL` → `SUBSURF`

Use `move_modifier` to reorder. `get_object_info` shows the counts with modifiers
applied (`mesh.with_modifiers`).
