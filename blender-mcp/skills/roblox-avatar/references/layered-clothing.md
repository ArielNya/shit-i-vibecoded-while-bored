# Layered clothing

Clothing that stretches over any body and over other clothes. It has three parts:

1. The **mesh**.
2. An **inner cage**, the surface the clothing sits on (the body).
3. An **outer cage**, the surface the next layer sits on.

Studio wraps the inner cage onto the wearer's outer cage.

Sources in creator-docs: `avatar/layered-accessories/specifications.md`, `export.md` and
`caging-best-practices.md`; `art/accessories/creating/*` (the long-sleeve tutorial);
`avatar/automatic-skinning-transfer.md`.

## Templates (start from these, always)

Download `Clothing_Cage_Templates.zip` into the workspace:
`https://media.githubusercontent.com/media/Roblox/creator-docs/main/content/en-us/assets/modeling/meshes/reference-files/Clothing_Cage_Templates.zip`.
Unzip it and `import_file` the `.fbx`. It holds an empty `Clothing Cages` with
`YourClothingName_InnerCage` and `YourClothingName_OuterCage`: 2,690 triangles each,
identical, feet at z ≈ -2.99 and head top ≈ 2.50.

- The inner cage **is** the mannequin. Model the clothing on it, as the tutorial does.
- **Never delete cage vertices or faces or change their UVs.** Studio matches cages by
  vertex and UV. Only move vertices.
- Rename both cages to `<ClothingMesh>_InnerCage` / `<ClothingMesh>_OuterCage` with
  `rename_object`. Example: mesh `Hoodie`, cages `Hoodie_InnerCage` and
  `Hoodie_OuterCage`.

## Mesh rules

- One mesh, ≤ 4,000 triangles, watertight, fits 8 × 8 × 8 studs; one texture ≤ 2048².
- Close every opening: neck, wrists, waist, hem. The tutorial extrudes the edge loop a
  little inward and merges it at the centre. Keep a thickness if you like (extrude the
  whole shell, then bridge), but the result must be closed.
- The clothing wraps the inner cage everywhere it covers, never inside it. Leave a
  small gap (≈ 0.01–0.03 studs).
- Attachment by type: tops (Shirt, TShirt, Sweater, Jacket) use `BodyFrontAttachment`;
  bottoms (Pants, Shorts, DressSkirt) use `WaistCenterAttachment`. The Accessory Fitting
  Tool adds it.

## Outer cage

Move the outer cage's vertices out so it hugs the clothing's outside. Where the
clothing doesn't cover (legs on a shirt), it stays identical to the inner cage.

- Tutorial way: Sculpt mode, Inflate with X symmetry, then fix vertices by hand.
- blender-mcp way: `add_modifier` a **Shrinkwrap** on the outer cage. Set target = the
  clothing mesh, `wrap_method` = `NEAREST_SURFACEPOINT`, `wrap_mode` = `OUTSIDE` (only
  vertices inside the clothing move) and `offset` ≈ 0.02. Then `apply_modifier` it and
  `smooth_vertices` lightly where it creases.
- Check it in wireframe, `render_preview(xray=true)`. The outer cage should cover the
  whole mesh and stay as close as possible. `check_roblox_asset(kind="layered")` warns
  when it doesn't enclose the clothing's bounds.
- Keep the cage faces evenly sized. Avoid folding vertices over each other at the
  armpits and crotch (see caging best practices).

## Skinning (optional since Automatic Skinning Transfer)

- **Simplest:** don't skin. In Studio, set the `WrapLayer.AutoSkin` to
  `EnabledOverride`; the AFT has a toggle. Roblox computes weights from the wearer's
  cages. The game needs `StarterPlayer.LoadCharacterLayeredClothing` on.
- **Manual:**
  1. Import `Rig_and_Attachments_Template.fbx` (link in `rigid-accessories.md`).
  2. Align its armature with the cage template (move/scale so the joints sit in the
     cage's joints, then `apply_transform`).
  3. `bind_to_armature(method="automatic")` the clothing to it.
  4. Pose-test with `pose_bone` (arms up, legs forward) and `render_preview`.
  - Rules: at most **4 bone influences per vertex**, R15 bone names, nothing on `Root`.
    `check_roblox_asset` counts all three.

## Export

The hierarchy the docs expect:

- the armature (if skinned), with the clothing mesh under it;
- an empty (`Clothing Cages`), with `<Mesh>_InnerCage` and `<Mesh>_OuterCage`.

Use `export_file(path="hoodie.fbx", objects=[mesh, "Clothing Cages", armature],
roblox=true)`. Shoes: left and right can share one file, each with its own two cages.

## Studio

Import with the 3D Importer. It recognises the cages and makes a `MeshPart` with
`WrapLayer`s. Then run the AFT: asset type **Clothing** and the right clothing type.
Test on several bodies and other clothes, adjust the cages in the AFT's cage editor
if needed, and **Generate MeshPart Accessory**. See `studio.md`.
