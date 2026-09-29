---
name: img2model
description: Turn images (concept art, orthographic turnaround sheets, product photos, screenshots) into efficient 3D models in Blender with the blender-mcp tools: classify the input, write a shape inventory once, match reference planes or a camera, block out, compare silhouettes, refine to a polygon budget, colour, validate and export. Use whenever the user supplies an image and wants it modelled, whether it's a prop, vehicle, building or character.
---

# Image to model

Turn one or more images (a concept sketch, a turnaround sheet, a product photo, a
screenshot) into a clean, efficient 3D model. This works for props, vehicles,
buildings and characters. For characters, this note gets you from the image to
measurements, and `blender://docs/game-character` takes over from there.

## 0. Classify the input (it decides the method)

| Input | Method | Accuracy you can promise |
|---|---|---|
| **Orthographic sheet** (front + side, maybe top/back, same scale) | trace: reference planes behind the model at true scale | close match (a few %) |
| **One orthographic view** (a front or side only) | trace that view, infer the depth from typical proportions | matches that view; the other axis is a guess |
| **Perspective image** (3/4 concept art, photo, render) | estimate: proportions from known sizes, match the silhouette from a similar camera | proportions and silhouette, not measurements |
| **Several photos from different sides** | estimate each view; cross-check dimensions between them | good proportions |
| **A drawing with callouts or dimensions** | use the numbers; the drawing only shows the shape | as accurate as the numbers |

Files must be in the workspace (`list_files`). If front and side views are two halves
of one image, ask for them as separate files (or crop them if you have a way to).

## 1. Read the image once and write it down

Look at the image once, carefully (with your own image viewing if you have it, or
`add_reference_image` + `render_preview(textures=true, size=512)`). Then **write a
shape inventory** and work from the text. It's far cheaper than looking at the image
again for every step:

```
Subject: wooden treasure chest, stylised, ~0.8 m wide (scale from: it sits next to a 1.7 m character)
Symmetry: mirror across X; lid hinged at the back
Parts (big → small):
  body      box 0.80 × 0.50 × 0.45, bottom at z 0
  lid       half-cylinder, radius 0.25 (spans the depth), length 0.80, on top of the body
  bands     3 metal straps 0.05 wide, 0.01 proud, wrap the body and lid
  lock      box 0.10 × 0.04 × 0.12, front centre, z 0.40
Colours: wood #8a5a2b, metal #3c3c44, lock #c9a23a
Budget: 300 tris (mobile prop)
Unknown (assumed): back side plain, bottom plain
```

**Scale**: pick one thing of known size in the image: a person (1.6–1.8 m), a door
(2.0 m), a chair seat (0.45 m), a hand (0.18 m), a car wheel (0.65 m), a mug (0.1 m),
or the stated size. Everything else is measured as a ratio against it (for example
"the lid is 0.3 of the body's width").

**Characters**: measure in head heights. Adults are 7–7.5 heads tall, heroic
figures 8, chibi styles 2–4. Write down where the chin, shoulders, chest, waist,
crotch, knees and ankles fall, in heads, then convert to metres. That table becomes the
landmark table of `blender://docs/character`.

**Hidden sides**: make the plainest plausible assumption (symmetric, flat back,
continued pattern), list it under "Unknown", and mention it in the summary.

## 2. Set up the comparison

**Orthographic sheet**: reference planes at true scale (details in
`blender://docs/character` step 1):

```
add_reference_image(path="front.png", view="front", character_height=H,
                    pixel_top=…, pixel_bottom=…, pixel_center=…)
add_reference_image(path="side.png", view="side", …, facing="left")
```

For props, `character_height` is simply the object's height, with `pixel_top` and
`pixel_bottom` at its top and bottom rows.

**Perspective image**: a matching camera instead of planes. Estimate the view (eye
level or above? rotated how far from front-on?) and the lens (phone photos are about 26
mm full-frame equivalent, so use `lens` 26–35; concept art is usually 35–50):

```
create_primitive(type="camera", name="MatchCam", location=[…])
look_at(name="MatchCam", target=[0, 0, height/2])
set_data_params(name="MatchCam", params={"lens": 35})
set_active_camera(name="MatchCam")
```

Compare `render_preview(size=384)` from the scene camera with the image: silhouette,
proportions, the angle of receding edges. Adjust the camera once or twice, then leave
it and adjust the model.

## 3. Block out, then compare silhouettes

- One primitive per inventory part, named after the part, at the inventory's sizes:
  `create_primitive` + `transform_object(dimensions=…)`. `dimensions` act along the
  object's **own** axes. For a rotated part (a lying cylinder), apply the rotation
  first (`apply_transform(rotation=true)`), then set the dimensions.
- Parts that touch leave hidden faces inside when joined (a lid resting on a box).
  Delete them (`delete_elements`) or accept the non-manifold warning on props. Symmetric parts: build one
  and use MIRROR, or `duplicate_object` + mirrored location.
- **Silhouette check** at stage end: `render_preview(engine="workbench", size=384)`
  from the matching view. A flat silhouette shows proportion errors best. Fix ratios
  now. Everything after this is harder to move.
- Two or three rounds of "compare → fix the biggest error" is normal. Stop when the
  silhouette matches within about 5 % from every view you have.

## 4. Refine to the budget

- Merge the blockout into the final topology. For organic and one-piece objects,
  box-model from the main part (extrude, loop cut). For hard-surface objects made of
  separate pieces, keep separate objects and `join_objects` at the end.
- Detail in order of **silhouette → big shading breaks → small details**. Check the
  triangle count (`check_game_ready(max_triangles=…)`) before adding each level of
  detail. Stop when the budget is reached, even if the image has more.
- Small details that don't change the silhouette (screws, seams, engravings) belong
  in a texture or normal map (`blender://docs/character-highpoly` §2b), not in the
  mesh.
- Bevel only edges that catch light at the viewing distance:
  `bevel(select={"sharp_angle": 60}, width=…, segments=1)`, then
  `shade(smooth=true, auto_smooth_angle=40)`.

## 5. Colour and material

- Take colours from the inventory (read them off the image as hex or RGB 0–1).
  **One material per colour region, merged where possible**: 1–3 per prop.
- Metals: `metallic=1` with roughness 0.2–0.5; wood, cloth and stone: roughness
  0.6–0.9.
- UVs for anything that will get a texture: `uv_unwrap(method="smart")` for props,
  seams for characters.
- Final look: `render_preview(engine="eevee", size=512)` with a simple light setup
  (`blender://docs/materials`).

## 6. Deliver

- `check_game_ready(name=…, kind="prop")` for props, `kind="character"` for
  characters (then continue with `blender://docs/game-character`).
- One final comparison render from the image's view, side by side in your head with the
  image. Mention anything you assumed.
- `save_blend`, and `export_file` if a format was asked for (`.glb` by default).

## Token and effort guide

- Look at the input image **once** and write the inventory. Every later check is a
  render of the model, at `size=384`.
- A prop from a single image typically takes 20–40 tool calls and 3–5 pictures. If you're
  past 10 pictures, the inventory is probably wrong: re-read the image once and fix
  the ratios instead of nudging.
- Don't chase details the budget can't afford. Say what you left out.

---

Links like `blender://docs/<topic>` are resources of the blender-mcp server (read them with your MCP resource tool). The same notes ship as skills: `blender-mcp` (efficiency, workflow, selection, modifiers, materials, troubleshooting), `game-character` (game-character, character, character-highpoly, rigging).
