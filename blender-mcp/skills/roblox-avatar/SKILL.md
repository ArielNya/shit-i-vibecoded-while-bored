---
name: roblox-avatar
description: Make Roblox avatar items in Blender with the blender-mcp tools and bring them into Roblox Studio as wearables - rigid accessories (hats, hair, glasses, backpacks, wings, tails), layered clothing (shirts, jackets, pants, dresses, shoes) and character bodies. Use it for any Blender model meant to be worn in Roblox: it has Roblox's sizes, budgets, naming, cage and rig rules, the export settings and the Studio steps (Accessory Fitting Tool, Accessory by script, Marketplace upload).
---

# Roblox avatar items from Blender

Written for Roblox's avatar specifications as of Sept 2026 (creator-docs:
`avatar/rigid-accessories`, `avatar/layered-accessories`, `avatar/character-bodies`,
`art/accessories`). Roblox validates everything on upload. Anything the checks below
flag will also be rejected there.

## Pick the kind first

| The item | Kind | Read |
| --- | --- | --- |
| Keeps its shape: hat, cap, crown, ears, hair, glasses, mask, necklace, backpack, wings, tail, sword on the back | **rigid accessory** | `references/rigid-accessories.md` |
| Stretches over the body and other clothes: T-shirt, jacket, sweater, pants, shorts, skirt, dress, shoes | **layered clothing** | `references/layered-clothing.md` |
| A whole avatar or its body parts | **character body** | `references/character-bodies.md` |
| A flat 2D shirt/pants image for blocky avatars | classic clothing: an image template, not a Blender job | say so |

Studio side (import, the Accessory Fitting Tool, making an `Accessory` by script,
testing on a character, uploading): `references/studio.md`.

## Rules for every kind

- **1 Blender unit = 1 stud.** Keep scene Unit Scale 1.0 and export with
  `export_file(..., roblox=true)`, which uses FBX Unit Scale. Roblox's Normal (Rthro)
  mannequin is about 6.3 studs tall and its head is about 0.85 wide. A 2 m tall hat is
  wrong.
- **Axes:** Z up, the wearer faces **-Y** (Blender's front view), and their left is
  +X. This is the same as blender-mcp's character convention.
- **Model on the mannequin.** Get Roblox's templates into the workspace before
  modelling (links in the references). If you can't download them, use these numbers
  (Normal body, in the rig template's space: feet at z ≈ -3.38, root at 0):
  - head top z ≈ 2.89;
  - `Hat_Att` / `Hair_Att` at (0, -0.02, 2.46);
  - `FaceFront_Att` at (0, -0.42, 2.05);
  - `Neck_Att` at (0, -0.02, 1.66);
  - `BodyFront_Att` at (0, -0.39, 1.06);
  - `BodyBack_Att` at (0, 0.24, 1.06);
  - `WaistCenter_Att` at (0, 0, 0).
- **One mesh, one material, one UV map, one colour texture.** Model in parts, then
  `join_objects`, `merge_by_distance` (0.001–0.01), and `bake_texture` (default 1024 px;
  never more than 2048 for Marketplace items). Detail comes from the texture, not from
  more materials.
- **Watertight, no n-gons:** every edge between exactly two faces, no holes or
  floating vertices. Primitives joined together are fine; each piece is closed.
  Quads and tris are fine; faces with 5+ sides get flagged.
- **Budgets:** accessories ≤ 4,000 triangles. Aim for 1–2k for a hat. The body
  budgets are in the body reference.
- **Plastic, opaque:** the Marketplace needs Material Plastic, Transparency 0 and
  VertexColor 1,1,1. So no glass, no alpha, and no glow except what's painted in.
- **Apply transforms** (`apply_transform`) before checking and exporting.

## The loop

1. **Reference and scale.** Import the mannequin (`import_file`) or place the numbers
   above. Put the item's attachment point where it belongs: a hat's is `Hat_Att`.
2. **Block out, then detail.** Use `create_primitive`, `extrude`, `bevel`, `loop_cut`,
   `transform_elements` and modifiers such as Mirror and a low Subdivision. Apply
   modifiers before the checks. Colour parts, and patterns as face selections
   (`assign_material(faces=...)`), with as many materials as you like: they're bake
   inputs. Don't add floating objects for markings. Recognisable features come first:
   list them before modelling, and check them in every render.
3. **Look at it** from the front, side and 3/4 with
   `render_preview(textures=true)`, on the mannequin. Fix silhouette problems now.
   Cheap edits end here.
4. **Merge:**
   - `join_objects` the parts;
   - `merge_by_distance`;
   - `recalc_normals`;
   - `apply_transform`;
   - apply or remove the modifiers.
5. **Bake:** `bake_texture(object, path="<name>.png")`. This gives one material, one
   UV map and one PNG. Render again with textures to see the bake.
6. **Check:** `check_roblox_asset(kind=..., object=..., accessory_type=...,
   attachment=[...])`. Fix every error, then read the warnings. It also returns
   `handle_attachment_position`, which is where the attachment goes inside the Studio
   Handle.
7. **Export:** `export_file(path="<name>.fbx", objects=[...], roblox=true)`. This embeds
   the texture and keeps 1 unit = 1 stud. glTF (`.glb`) also imports at the right
   scale and is fine for rigid items. Also `save_blend` the source.
8. **Studio:** `references/studio.md`. Import, generate the Accessory, try it on a
   character in play mode, then upload.

## Stop and ask

- **Other people's IP.** A Pokémon, anime, brand, logo or sports team design can be
  built and tested privately, but **never uploaded or sold**. Marketplace policy bans
  items that use IP you don't own or licence, and it's enforced with takedowns and
  account penalties. Say this when the request names a franchise. Offer an original
  design "inspired by" it for anything meant to be published.
- **Uploading and selling.** It costs Robux (an upload fee plus a publishing advance),
  needs ID verification plus Roblox Plus or Premium to sell, and puts the user's account behind
  it. Only do it when the user explicitly asks, from their Studio.
