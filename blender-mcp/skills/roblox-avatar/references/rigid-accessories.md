# Rigid accessories

A single mesh welded to one attachment point on the character. It doesn't deform.
Source: creator-docs `avatar/rigid-accessories/specifications.md`, `export.md`,
`art/accessories/creating-rigid/*`.

## Templates

Roblox's mannequins and rig template are in the creator-docs repository (Git LFS).
Download them into the blender-mcp workspace with your own tools, or ask the user to:

- Mannequin (Normal):
  `https://media.githubusercontent.com/media/Roblox/creator-docs/main/content/en-us/assets/art/reference-files/RthroMannequin.fbx`.
  The same folder has `RthroSlenderMannequin.fbx` and `ClassicMannequin.fbx`.
- Rig with every `_Att` attachment:
  `https://media.githubusercontent.com/media/Roblox/creator-docs/main/content/en-us/assets/modeling/meshes/reference-files/Rig_and_Attachments_Templates.zip`.
  Unzip it and `import_file` the `.fbx`.

Both import in the same space (1 unit = 1 stud, feet at z ≈ -3.38). Read an
attachment's position with `get_object_info("Hat_Att")`: its bounds centre is the
point.

## Attachment and size limits

Pick the type. Its attachment is where the item hangs, and the size limit is
measured from that point, not from the mesh's centre. `check_roblox_asset` knows
every row. Pass `accessory_type` and the `attachment` position.

| Type (`accessory_type`) | Roblox attachment | Normal W × H × D (studs) | Slender | Classic |
| --- | --- | --- | --- | --- |
| `hat` | HatAttachment | 1.87 × 2.5 × 1.87 | 1.78 × 2.5 × 1.78 | 3 × 4 × 3 |
| `hair` | HairAttachment | 1.87 × 3.12 (1.25 up, 1.875 down) × 2.18 (0.94 front, 1.25 behind) | 1.78 × 3.12 × 2.08 | 3 × 5 × 3.5 |
| `face` (glasses, masks) | FaceFrontAttachment / FaceCenterAttachment | 1.87 × 1.25 × 1.25 | 1.78 × 1.25 × 1.18 | 3 × 2 × 2 |
| `neck` | NeckAttachment | 2.95 × 3.68 × 2.16 | 2.59 × 3.39 × 1.92 | 3 × 3 × 2 |
| `shoulder_neck` (capes on the neck) | NeckAttachment | 6.90 × 3.68 × 3.24 | 6.05 × 3.39 × 2.88 | 7 × 3 × 3 |
| `shoulder_collar` | Left/RightCollarAttachment | 2.95 × 3.68 × 3.24 | 2.59 × 3.39 × 2.88 | 3 × 3 × 3 |
| `shoulder` (shoulder pets) | Left/RightShoulderAttachment | 2.67 × 4.40 × 3.09 | 2.37 × 3.96 × 2.75 | 3 × 3 × 3 |
| `front` | BodyFrontAttachment | 2.95 × 3.68 × 3.24 | 2.59 × 3.39 × 2.88 | 3 × 3 × 3 |
| `back` (wings, backpacks) | BodyBackAttachment | 9.86 × 8.59 × 4.87 (1.62 front, 3.25 behind) | 8.64 × 7.91 × 4.32 | 10 × 7 × 4.5 |
| `waist` (belts, tails) | WaistFront/Center/BackAttachment | 3.94 × 4.29 (1.84 up, 2.46 down) × 7.57 | 3.76 × 3.29 × 6.73 | 4 × 3.5 × 7 |

W is Blender X, H is Blender Z and D is Blender Y. A hat may reach 1.25 studs above
`Hat_Att` (z ≈ 3.71), which is room for ears or a tall crown, and 0.935 to each side.
The "Normal" row is for the Rthro mannequin. Classic bodies allow more, but design for
Normal unless told otherwise.

## Other rules

- One mesh, ≤ 4,000 triangles, watertight, quads or tris.
- Textures up to 2048² (Marketplace). A hat reads well at 512–1024. The
  SurfaceAppearance extra maps (normal, roughness, metalness) can be at most 256² for
  rigid accessories. `bake_texture` makes the colour map only; that's all most items
  need.
- You can't import attachments with a rigid accessory. Studio adds the attachment
  (the Accessory Fitting Tool, or the script in `studio.md`).
- The mesh must not cover the face if it's a hat. Keep the brim above the eyes
  (z ≳ 2.2 on Normal).

## Hat recipe

1. Import `RthroMannequin.fbx` and the rig template. Note `Hat_Att` (≈ (0, -0.02, 2.46))
   and the head bounds (x ±0.42, y -0.45..0.42, top z 2.89). Hide the rig and the
   `_Att` meshes (`set_visibility`) so the previews are clean.
2. **Read the design first.** List the 3–4 features that make the character
   recognisable, with their shape, proportion and colour. For example: "ears as long
   as the head is tall, broad leaf shapes; a yellow band across each ear; a yellow ring
   on the forehead". Build those. A generic hat with spikes isn't the character.
3. **Cap:** a UV sphere, r ≈ 0.47, scaled (1, 1.05, 0.8) and centred at z ≈ 2.55. Cut
   it with `bisect(keep="above", fill=true)` at about z 2.3 so the eyes stay visible
   and the mesh stays closed.
4. **Big shapes from few faces:** ears, horns and crests are a cone or cube with 6–12
   segments. Shape them with `transform_elements` on vertex groups: flatten in Y for
   a leaf ear, widen the middle, taper the tip. Don't use thin spikes. Sink each part a
   little into the cap so no seam shows, and mirror in X.
5. **Markings are faces, not extra objects.** Add edge loops where a band goes
   (`loop_cut`), then find the faces with `select_elements` (by position) and colour
   them with `assign_material(faces=[...])`. The bake turns them into texture at no
   triangle cost. Separate rings or decals floating on the surface look stuck on,
   and they eat the budget.
6. `shade(smooth=true, auto_smooth_angle=40)` for rounded parts: Roblox keeps the
   normals. A hat should land at 500–2,000 triangles. Near 4,000 means too many
   segments.
7. Review against the design: `render_preview` front, side and 3/4 with the mannequin.
   Fix the proportions before joining.
8. Join, merge by distance, bake, check (`accessory_type="hat"`, `attachment` = the
   `Hat_Att` point), and export `hat.fbx` with `roblox=true`.
