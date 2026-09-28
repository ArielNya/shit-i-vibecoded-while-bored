---
name: lowpoly-character
description: Model a game-ready low-poly humanoid or character in Blender (via the blender-mcp tools) from a front and a side view reference sheet, then rig, skin, pose-test, animate and export it. Use when asked to build, rig or animate a low-poly person, creature or mascot from reference images.
---

# Low-poly character from a reference sheet

Build a game-ready low-poly humanoid (or humanoid-ish creature) from a **front** and a
**side** view reference sheet, then rig it, skin it, test the deformation, give it a
little animation and export it. Each stage ends with a visual check against the sheet.
Don't skip them: they catch most mistakes while they're still cheap to undo.

Toolsets used: `inspect`, `view`, `edit`, `mesh`, `rig`, `animate`, `look`, `files`
(all enabled by default).

## Conventions (the rig tools rely on them)

- 1 unit = 1 m, **Z up**, feet on **z = 0**, the body centred on **x = 0**.
- The character **faces -Y**, which is Blender's front view. Its **left** side is **+X**.
- Left bones end in `.L` (on +X), right bones in `.R`.
- Model in a **T-pose or A-pose**, with arms straight and legs straight, whichever the
  sheet shows.
- Keep the model as **one object** (`Body`) where possible. Separate rigid parts
  (hat, sword, eyes) are fine too; see Skin below.

## 0. Read the sheet

Look at the images before touching Blender. Use `list_files` to find them in the
workspace. If front and side are two halves of one image, crop them into two files
first, or ask the user for separate files.

Measure these in **pixels from the image's top-left corner**, on the front image:

| Measure | Where |
|---|---|
| `pixel_top` | row of the top of the head (the skull, not hair spikes or a hat) |
| `pixel_bottom` | row of the soles of the feet |
| `pixel_center` | column of the body's centre line |

On the side image, measure the same two rows (they should match the front view) and
the column of the ankle. Note which way the side view faces (`left` or `right`).

Pick the real height `H`. If the sheet gives none, use 1.6–1.8 for an adult, 1.0–1.3
for a chibi or child, and scale everything else from it. Then:

```
metres_per_pixel = H / (pixel_bottom - pixel_top)
z(row)  = (pixel_bottom - row) * metres_per_pixel
x(col)  = (col - pixel_center) * metres_per_pixel       # front view; + is the image's right = character's LEFT
y(col)  = ±(col - ankle_col) * metres_per_pixel          # side view; toes are -Y
```

Write down a **landmark table** in metres before modelling. You'll reuse it for the
mesh and for the rig:

| Landmark | Typical adult (fraction of H) | Read from |
|---|---|---|
| head_top | 1.00 | front |
| chin / neck top | 0.87 | front |
| shoulder (joint) | 0.82 z, ±0.11 x | front |
| chest top / armpit | 0.75 | front |
| waist | 0.60 | front |
| hips / crotch | 0.47 | front |
| elbow (T-pose) | ±0.25 x | front |
| wrist (T-pose) | ±0.38 x | front |
| fingertips | ±0.47 x | front |
| knee | 0.27 | front/side |
| ankle | 0.05 | side |
| toe tip | y ≈ −0.10·H | side |

Stylised characters break these ratios on purpose (big head, short legs). **Trust the
sheet**, and use the table only to sanity-check your reading of it.

## 1. Set up the references

```
delete_objects(["Cube", "Light"])        # whatever get_scene_info shows as default clutter
add_reference_image(path="ref_front.png", view="front", character_height=H,
                    pixel_top=…, pixel_bottom=…, pixel_center=…)
add_reference_image(path="ref_side.png",  view="side",  character_height=H,
                    pixel_top=…, pixel_bottom=…, pixel_center=<ankle col>, facing="left")
render_preview(view="front", ortho=true, textures=true)
render_preview(view="right", ortho=true, textures=true)
```

The planes sit behind the model, cannot be selected, and live in a `References`
collection. **Check alignment now**: feet on the ground line, head at `H`, and the
side view's toes pointing to -Y (left in the `right` view). If the side view is
mirrored, re-add it with the other `facing`.

## 2. Block out the torso

A box with 3 columns × 3 rows gives exactly the faces you need to grow the limbs:

```
create_primitive(type="cube", name="Body", location=[0, 0, torso_mid_z])
transform_object(name="Body", dimensions=[chest_width, chest_depth, torso_height])
apply_transform(name="Body", location=true)     # scale is baked; mesh edits need it
loop_cut(...)  on a horizontal front edge, cuts=2   → 3 columns (centre = neck/crotch)
loop_cut(...)  on a vertical side edge,   cuts=2   → 3 rows   (top row = arm sockets)
```

Then place the cuts with **absolute** vertex moves, not guesses:

- top row → shoulder height: `transform_elements(type="verts", select=<the row's verts
  by z range>, center=[null, null, arm_bottom_z])`;
- column lines → the inner edges of the legs (`center=[±gap/2, null, null]`).

The top row's side faces become the arms, the bottom outer faces the legs, and the
top centre face the neck.

## 3. Selection discipline (the most common failure)

Every mesh tool takes a stateless `select`. **Bound every range on both ends** and
**check the count before you act**:

```
select_elements(name="Body", select={"normal": [1,0,0], "max_angle": 5,
                "position": {"axis": "z", "min": 1.02, "max": 1.21}})
→ expect count == 1 per side. If it's 3, you're about to extrude the head into arms.
```

Unbounded `normal: [1,0,0]` also matches every leg, arm and head side face once
those exist, and `normal: [0,0,1]` matches the tops of the arms. Add a `position`
range for the height, and one on x for centre faces.

- Use `normal` + `max_angle` ≈ 5 on blocky meshes; the default of 30 also matches
  bevelled neighbours.
- Indices go stale after any topology change (extrude, loop cut, delete). Use the
  indices a tool **returns** (`new_faces`) for the next step, or select again.
- Pass `type="verts"` to `transform_elements` when you mean "these vertices", so
  that a face selection doesn't drag shared vertices of neighbouring faces.

## 4. Legs

Extrude both bottom outer faces **together** (region mode keeps one leg per face as
long as they don't touch; the centre face stays as the crotch):

```
cap = legs_bottom_faces
for each segment (crotch → knee → ankle → sole):
    cap = extrude(select={"indices": cap}, distance=<segment length>)["new_faces"]
```

Each extrude leaves an **edge loop** at a joint. Hips, knees and ankles *need* one,
or they can't bend. Then fit each leg to the sheet:

```
transform_elements(type="verts", select=<z below crotch, x > 0>,
                   size=[leg_width, leg_depth, null], center=[leg_x, 0, null])
```

and repeat for x < 0. Taper the ankle loop the same way.

**Feet:** select the front faces of the lowest segment (`normal [0,-1,0]`, z bounded
to the foot) and extrude them `foot_length − leg_depth` towards -Y. Lower or raise the
top of the toe with `center`. A foot is 0.14–0.16 × H long.

## 5. Arms

Take the side faces of the top torso row, **one per side (count == 2 in total)**, and
extrude with `mode="individual"` so each grows along its own normal:

```
cap = extrude(select={"indices": arms}, distance=0.02, mode="individual")["new_faces"]
transform_elements(type="verts", select=<x beyond the torso, per side>,
                   size=[null, arm_thickness, arm_thickness], center=[null, 0, arm_z])
for each segment (shoulder → elbow → wrist → fingertips):
    cap = extrude(select={"indices": cap}, distance=<length>, mode="individual")["new_faces"]
```

Low-poly hands are a single block (a mitten). For a thumb, `extrude` a front face of
the hand segment towards -Y. For fingers, `loop_cut` the hand lengthwise 2–3 times,
then extrude the tip faces individually. Check the A-pose angle on the sheet: if the
arms slope down, rotate the arm verts about the shoulder with `transform_elements(rotation=…,
pivot=[shoulder_x, 0, shoulder_z])`, one side at a time.

## 6. Neck and head

```
cap = extrude(top_centre_face, distance=neck_length)["new_faces"]
transform_elements(select={"indices": cap}, size=[neck_w, neck_d, null])
cap = extrude(cap, distance=0.001)["new_faces"]              # a lip for the jaw line
transform_elements(select={"indices": cap}, size=[head_w, head_d, null])
cap = extrude(cap, distance=head_top - current_top)["new_faces"]
```

Shape it with `loop_cut` (eye line, mouth line) and `transform_elements` on vertex
rows: pull the chin forward, narrow the top, and push the nose out with a small
`extrude` of a front face. Hair, ears and hats can be extruded from the head or made
as separate objects and joined (`join_objects`) or rigidly skinned (see Skin).

## 7. Check proportions against both views

```
render_preview(view="front", ortho=true, textures=true, xray=true)
render_preview(view="right", ortho=true, textures=true, xray=true)
get_object_info(name="Body")  → dimensions ≈ [arm span, depth, H]; mesh.is_manifold true; ngons 0
```

With x-ray the sheet shows through the model. Fix any mismatch with `size`/`center` on
the offending vertex rows, and repeat until both views overlap. For symmetric fixes,
select both sides at once (bound on |x|), or use a MIRROR modifier. The MIRROR route
is: `bisect(keep="above", normal=[1,0,0])` → add MIRROR (clipping on) → model the +X
half → `apply_modifier` before rigging.

**Polygon budget:** 100–300 faces is PS1/"tiny" style, 300–1,500 is typical mobile or
indie low poly, and 1,500–5,000 is "mid poly". Spend faces on the silhouette and
the joints, not on flat areas.

**Topology for deformation:** at least one edge loop at every joint (shoulder, elbow,
wrist, hip, knee, ankle, neck). Two or three loops around elbows and knees make them
fold instead of pinch. Keep quads, and avoid long thin triangles across joints.

## 8. Colours and materials

Low-poly style is usually **flat colours per region**:

```
shade(name="Body", smooth=false)                 # faceted look; smooth for soft toys
create_material(name="Skin", base_color=[…], roughness=0.8)   # sample colours from the sheet
assign_material(object="Body", material="Shirt")               # base
assign_material(object="Body", material="Skin", faces=select_elements(<head z range>)["indices"])
…pants, boots, hair…
render_preview(view="front", ortho=true, textures=true, xray=true)
```

Colour boundaries follow edge loops. If a sleeve or boot edge falls mid-face, add a
`loop_cut` there first. Eyes and mouths: `inset` a front face of the head and give it
its own material, or `inset` with a small negative `depth` for a recessed look.

## 9. Rig

Reuse the landmark table (left side, x > 0):

```
create_humanoid_rig(height=H, landmarks={
  "hips": [0, 0, crotch_z + ~0.05], "chest": [0, 0, ~mid-torso], "neck": [0, 0, torso_top],
  "head": [0, 0, chin_z], "head_top": [0, 0, H],
  "shoulder": [shoulder_x, 0, arm_z], "elbow": […], "wrist": […], "hand_tip": […],
  "hip_joint": [leg_x, 0, crotch_z], "knee": [leg_x, knee_y, knee_z],
  "ankle": [leg_x, 0, ankle_z], "ball": [leg_x, -ball_y, ~0.03], "toe": [leg_x, -toe_y, ~0.03]})
```

- Put joints **inside the mesh at the pivot**, not on the surface. Read knee and ankle
  depth from the side view (knees slightly forward, elbows slightly back).
- `shoulder` is the arm's pivot, just inside the torso's side. The rig adds a clavicle
  (`shoulder.L`) from the chest to it.
- Tails, ears, ponytails, capes and weapons go in `extra_bones` (parent to `head`,
  `hips`, `hand.L`…). Name them with `.L`/`.R` when paired.
- `get_armature_info(armature="Rig")` lists every bone's world head and tail. Check
  them against the mesh with `render_preview(view="front", ortho=true, xray=true)`.

## 10. Skin

```
bind_to_armature(armature="Rig", meshes=["Body"], method="automatic")
```

Read the summary: `unweighted_vertices` must be 0, and `bones_without_vertices`
should list only `root` (and any control bones). Automatic (heat) weights are smooth
and work on connected, closed meshes. Use `method="nearest"` for:

- separate rigid parts (helmet, sword, glasses): bind them on their own to get
  nearest-bone weights, or paint them fully with `set_vertex_weights(weight=1)` to one
  bone;
- very blocky meshes where heat weighting bleeds across the crotch or armpits.

Fix bad regions directly:

```
set_vertex_weights(mesh="Body", group="head", select=<z above the chin>, weight=1)
set_vertex_weights(mesh="Body", group="thigh.L", select=<left leg, z 0.6–0.7>, weight=0.5, mode="ADD")
```

## 11. Test the deformation (always)

Pose, look, reset. Every pose below should look like a person, not a paper cut-out:

| Test | Calls | Look for |
|---|---|---|
| Arms down | `pose_bone("upper_arm.L", rotation=[0,0,-60], mirror=true)` (A-pose sheets: less) | armpit collapsing, torso dragged down |
| Elbow bend | `pose_bone("forearm.L", rotation=[60,0,0], mirror=true)` | the elbow keeps volume |
| Leg lift | `pose_bone("thigh.L", rotation=[-45,0,0])` | hip/crotch vertices following the wrong leg |
| Knee bend | `pose_bone("shin.L", rotation=[70,0,0])` | the knee bends **backward** (correct), not forward |
| Head turn | `pose_bone("head", rotation=[0,0,30])` | the neck twisting, the shoulders staying put |
| Bend over | `pose_bone("spine", rotation=[20,0,0])` | a smooth torso fold |

Check each with `render_preview(view="iso")` and `view="front"`, hiding the sheets
first (`set_visibility(names=["Ref front","Ref side"], viewport=false, render=false)`).
Then `reset_pose`. On the humanoid rig, **+X rotation is always the natural bend**.
`mirror=true` poses the other side symmetrically in one call.

## 12. Animate (optional, but proves the rig works)

A 24-frame walk loop:

```
set_frame_range(start=1, end=24, fps=24)
for frame, s in [(1, 30), (13, -30), (24, 30)]:
    pose_bone("thigh.L",     rotation=[-s, 0, 0],   frame=frame)
    pose_bone("thigh.R",     rotation=[ s, 0, 0],   frame=frame)
    pose_bone("upper_arm.L", rotation=[ s, 0, -60], frame=frame)   # arms swing opposite to legs
    pose_bone("upper_arm.R", rotation=[-s, 0,  60], frame=frame)
# knees: shin.L/R rotation [40,0,0] at the passing frames (7, 19), [5,0,0] at the contacts
set_frame_range(current=7);  render_preview(view="right")
list_keyframes(object="Rig")
```

An idle is simpler: `spine` rotation [3,0,0] ↔ [0,0,0] and `upper_arm` Z ±3° over 48
frames.

## 13. Export

```
reset_pose(armature="Rig")
save_blend(path="character.blend")
export_file(path="character.glb", objects=["Rig"])      # children (the skinned mesh) come along
```

glTF keeps the skeleton, skin weights, materials and actions (engines take up to 4
bone influences per vertex; the exporter keeps the strongest). To verify, re-import
into an empty scene with `import_file` and check that there's an ARMATURE and that the
mesh has an Armature modifier. FBX (`.fbx`) works too for Unity and Unreal. Use
`.glb` for Godot, three.js and Babylon.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Extrude grew limbs out of the head too | the selection matched more faces than intended | bound both ends of every range; check `count` first; `undo` |
| Limb extrudes are skewed or fused | region extrude on touching faces | `mode="individual"` for arms; separate faces for legs |
| Mesh doesn't line up with the sheet | wrong `pixel_*` values | re-measure; re-add the reference with the same name (it replaces it) |
| Side view mirrored | `facing` wrong | re-add with the other `facing` |
| Knee or elbow bends the wrong way | custom `create_armature` rolls | use `create_humanoid_rig`, or set `roll` so +X bends naturally |
| Parts of the torso follow an arm | heat weights bled across | `set_vertex_weights` to `chest`/`spine` with weight 1 |
| Some vertices don't move | unweighted vertices | `get_armature_info` → `unweighted_vertices`; `set_vertex_weights` or rebind with `nearest` |
| The model shrinks or explodes when bound | unapplied object scale | `apply_transform` on the mesh, then bind again |
| Export has no animation | action wasn't on the rig | keyframe via `pose_bone(frame=…)` on the armature; check `list_keyframes(object="Rig")` |
