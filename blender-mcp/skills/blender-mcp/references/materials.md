# Materials, lighting and rendering

## Material recipes (`create_material`)

| Look | Settings |
| --- | --- |
| Plastic | `base_color` any, `roughness` 0.3–0.5, `metallic` 0 |
| Rubber | dark `base_color`, `roughness` 0.8–0.9 |
| Polished metal | `metallic` 1, `roughness` 0.1–0.25, `base_color` = metal tint (gold ≈ [1, 0.77, 0.34]) |
| Brushed metal | `metallic` 1, `roughness` 0.4–0.5 |
| Glass | `transmission` 1, `roughness` 0–0.05, `ior` 1.45–1.5 |
| Ceramic / glaze | `roughness` 0.2–0.3 |
| Wood (flat) | brown `base_color` ≈ [0.4, 0.26, 0.13], `roughness` 0.6 |
| Glow | `emission_color` + `emission_strength` 2–20 |
| See-through | `alpha` < 1 |

Colors are linear RGB 0–1. Very saturated colors look more intense in renders than
the numbers suggest; 0.8 is "bright".

Per-face materials: `assign_material(faces=[...])` adds a slot and assigns only
those faces (pick faces with `select_elements`).

Textures: `generated_texture` `CHECKER`/`COLOR_GRID` needs no files and is great
for checking UVs; `base_color_texture` loads an image from the workspace. All
primitives have UVs; meshes from `create_mesh_from_data` don't.

## Lighting

- `set_world(color, strength)` is ambient light. Strength 0.3–1 for a neutral base.
- Key light: `create_primitive(type="light", light_type="AREA", energy=500–2000)`
  a few meters away, then `look_at` the subject; `set_data_params` → `size` for
  softer shadows.
- Outdoor: `light_type="SUN"`, `energy` 2–5 (sun strength is not in watts).

## Cameras and renders

- `render_preview(view="camera")` uses the scene camera; other views auto-frame.
- Place a camera with `transform_object(location=...)` + `look_at`.
  `set_data_params` → `lens` (35 wide, 50 normal, 85 portrait).
- `engine`: `workbench` for quick shape checks (seconds), `eevee` for materials,
  `cycles` for accurate light (use `samples` 16–64 for previews).
- Workbench shows each material's viewport color, which `create_material` keeps
  in sync with the base color.
