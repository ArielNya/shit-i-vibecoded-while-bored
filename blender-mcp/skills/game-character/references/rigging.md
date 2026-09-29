# Rigging, skinning, testing and export

The same for every character route (low poly, high → low, subdivision cage). The mesh
should already pass the standards in `../SKILL.md`: scale and
transforms applied, feet on z = 0, facing -Y, left on +X, a neutral pose.

## 1. Skeleton

### Humanoids: `create_humanoid_rig`

Measure landmarks **on the mesh** (or the reference sheet), in metres, for the
character's **left** side (x > 0). The right side is mirrored.

```
create_humanoid_rig(height=H, landmarks={
  "hips": [0, 0, crotch_z + 0.04], "chest": [0, 0, …], "neck": [0, 0, torso_top_z],
  "head": [0, 0, chin_z], "head_top": [0, 0, H],
  "shoulder": [x, y, z], "elbow": […], "wrist": […], "hand_tip": […],
  "hip_joint": […], "knee": […], "ankle": […], "ball": […], "toe": […]})
```

This gives 22 bones: `root` (non-deforming, at the origin), `hips`, `spine`, `chest`,
`neck`, `head`, and per side `shoulder`, `upper_arm`, `forearm`, `hand`, `thigh`,
`shin`, `foot`, `toe` with `.L`/`.R`. Landmarks you leave out use average
proportions of `height`.

**Where joints go:**

- **Inside the mesh at the pivot**, not on the surface: the elbow in the middle of the
  arm's thickness, slightly towards the back; the knee slightly towards the front; the
  hip joint about a third of the way in from the side of the pelvis.
- Take the depth (y) from the side view: knees and elbows get their small bend from
  the rest pose.
- `shoulder` is the arm's pivot. The rig adds a clavicle bone from the chest to it.
- Check the result with `get_armature_info(armature="Rig")` (world head and tail of
  every bone) and one `render_preview(view="front", ortho=true, xray=true, size=384)`.

**Rotation axes** (`pose_bone(rotation=[x, y, z])`, degrees, measured on this rig):

| Bone | +X | +Y (twist along the bone) | +Z |
|---|---|---|---|
| `spine`, `chest`, `neck`, `head` | bend forward / nod | **turn** to the character's left (−Y: to its right) | **tilt/lean** to the character's right |
| `upper_arm`, `forearm`, `hand` .L | fold forward | roll the arm (palm up/down) | **raise** (−Z lowers: from a T-pose, `[0,0,-60]` = arms down) |
| same, .R | fold forward | roll | **lower** (−Z raises) |
| `thigh` .L | swing back (−X lifts the leg forward) | twist | inward (−Z spreads the leg out) |
| `thigh` .R | swing back | twist | outward |
| `shin` | bend the knee (backward) | – | – (a knee doesn't bend sideways) |
| `foot`, `toe` | point/curl the toes down | – | – |

With `mirror=true`, give the .L values: the .R bone gets the mirrored pose. **Extra
bones** (tails, ears, fingers) depend on their direction and `roll`. Measure them
once: `pose_bone(bone=…, rotation=[20,0,0])` returns `tail_world`; compare it with the
rest value (`get_armature_info`), then `reset_pose`. For reference, a tail bone pointing
back with roll 0 lifts on +X and swings to the character's right on +Z; an ear bone
pointing up folds forward on +X (−X lays the ear back) and tilts right on +Z.

### Extra bones (`extra_bones`, same format as `create_armature`)

Parent every extra bone to an existing bone. Give paired bones `.L`/`.R`, and list
parents before children.

| Need | Bones (left side; mirror x for .R) | Parent |
|---|---|---|
| Fingers | per finger `index_01.L`→`_02`→`_03` (connected), same for `middle`, `ring`, `pinky`, `thumb`; heads at the knuckles, the last tail at the fingertip | `hand.L` |
| Jaw | `jaw`: head just under the ear, tail at the chin | `head` |
| Eyes | `eye.L`: head at the eyeball centre, tail 0.05 in front (−Y) | `head` |
| Tail | `tail_01`…`tail_05` chain, connected | `hips` |
| Ponytail / braid / cape | a chain of 3–6, connected | `head` / `chest` |
| Weapon / prop socket | `weapon.R`: head in the palm, tail along the grip | `hand.R` |
| Breathing / belly | `belly` (deform), small | `spine` |

Keep chains short: each bone costs animation work and engine time. Fingers and face
only when the budget allows (see `game-character` §6).

### Non-humanoids: `create_armature`

Quadrupeds, birds, robots and snakes: list the bones yourself (same conventions:
faces -Y, `.L` on +X). Set `roll` so each bone's +X rotation is its main bend. Put a
non-deforming `root` at the origin (`deform: false`) as the parent of everything; engines
use it for root motion.

## 2. Skinning

```
bind_to_armature(armature="Rig", meshes=["Body"], method="automatic", max_influences=4)
```

- **automatic** (heat weights) gives smooth results on a closed, connected body. Any
  vertices it misses are filled from the nearest bones.
- **nearest** is for rigid parts (armour plates, robots, props) and very blocky
  meshes where heat weights bleed across the crotch or armpits.
- **`max_influences=4`** keeps the 4 strongest bones per vertex and normalises the
  weights, which is what game engines expect. `0` leaves Blender's weights as they are
  (fine for film).
- Read the summary: `unweighted_vertices` must be 0. `bones_without_vertices` should
  only list control bones (`root`) and sockets.

**Separate parts**: bind them in the same call (`meshes=["Body", "Eyes", "Hair"]`),
then make rigid parts follow one bone:

```
set_vertex_weights(mesh="Eyes", group="head", select={"all": true}, weight=1)
```

**Typical fixes** (all on vertex positions, bounded on both ends):

| Symptom in the pose test | Fix |
|---|---|
| The chest caves in when an arm goes down | `set_vertex_weights(group="chest", select=<torso side verts below the armpit>, weight=1)` |
| The inner thighs stick together or follow the wrong leg | weights for `thigh.L` on x > 0.01 only, `thigh.R` on x < −0.01 |
| The head squashes on a head turn | everything above the chin 100% `head` |
| Hands are mushy | the whole hand 100% `hand.L` (low poly without fingers) |
| An elbow collapses to a crease | make sure there are 3 loops at the elbow (topology, not weights); then blend `forearm.L` 0.5 on the middle loop |
| Ears, fins or a tail tip drag the head/body along (or the reverse) | small extra bones get little heat weight. Give the part's vertices 100 % to its bone (`set_vertex_weights(group="ear.L", select=<bounded box around the ear above its base>, weight=1)`), then 0.5 on the ring at its base |
| A tail bends in one lump | a loop at every tail bone joint (topology), then each segment's vertices 100 % to its `tail_0N` bone with 0.5 on the joint rings |

After fixes, run `check_game_ready(name="Body", expect_rig=true)` again: no
unweighted vertices, and influences within the limit.

## 3. Pose tests (always, before calling it done)

Hide references first (`set_visibility(names=[…], viewport=false, render=false)`).

| Test | Calls | Pass when |
|---|---|---|
| Arms down (T-pose models) / arms up (A-pose) | `pose_bone(bone="upper_arm.L", rotation=[0,0,-60], mirror=true)` | the shoulder keeps volume; the armpit doesn't tear |
| Elbows | `pose_bone(bone="forearm.L", rotation=[90,0,0], mirror=true)` | the outer elbow stays round, the inner one folds |
| Leg lift | `pose_bone(bone="thigh.L", rotation=[-70,0,0])` | the crotch and buttock follow smoothly |
| Knee | `pose_bone(bone="shin.L", rotation=[90,0,0])` | it bends **backward**; the knee cap keeps its shape |
| Squat | thighs −90, shins 120, `mirror=true` | nothing interpenetrates badly |
| Head | `pose_bone(bone="head", rotation=[0,40,0])` (turn), then `[15,0,20]` (nod + tilt) | the neck twists; the shoulders stay put |
| Torso | `pose_bone(bone="spine", rotation=[30,0,0])` then `[0,40,0]` | a smooth bend, then a twist |
| Fingers (if rigged) | each `_01` bone `[80,0,0]` | a fist without fingers passing through each other |

Render the worst ones at `size=384`, `view="iso"`, then `reset_pose`. Fix topology
first (missing loops), weights second.

## 4. Animation

Keyframe with `pose_bone(..., frame=N)`, then check with `list_keyframes(object="Rig")`
and `set_frame_range(current=…)` + `render_preview`.

- **Idle** (48 frames): `spine` X 0 → 3 → 0; `upper_arm` Z ±2; `head` X 0 → −2 → 0.
- **Walk** (24 frames at 24 fps): thighs ±30 on frames 1, 13 and 25 (left and right
  opposite); shins 40 at the passing frames (7, 19) and 5 at contact; arms swing
  opposite to the legs; hips Z ±5.
- Loops: the last key equals the first.
- Keep actions on the armature. Each engine imports them as named clips.

## 5. Export

```
reset_pose(armature="Rig")
save_blend(path="character.blend")
export_file(path="character.glb", objects=["Rig"])   # children (skinned meshes) come along
```

| Target | Format | Notes |
|---|---|---|
| Godot 4, three.js, Babylon, web | `.glb` | native. Godot: set a `SkeletonProfileHumanoid` bone map on import to retarget |
| Unity | `.fbx` (or `.glb` with glTFast) | set Rig → Humanoid and check the Avatar mapping (hips, spine, chest, neck, head, arms, legs; toes optional) |
| Unreal Engine 5 | `.fbx` (or `.glb`) | the `root` bone at the origin is expected; retarget to the Mannequin with IK Retargeter |
| Mixamo auto-rig | `.fbx`/`.obj` of the **mesh only** (no rig), in T-pose | Mixamo builds its own skeleton; skip `create_humanoid_rig` |
| Blender / film | `.blend` | keep SUBSURF live (see `character-highpoly`) |

- glTF takes at most 4 influences per vertex (hence `max_influences=4`), and Y-up is
  converted automatically.
- Don't export reference planes, high-poly bake sources or helper objects. Pass the
  objects explicitly.
- **Verify** by re-importing into an empty scene: `import_file` → one ARMATURE, skinned
  meshes with an Armature modifier, the actions present.
- **LODs**: bind each LOD to the same `Rig` (decimated duplicates keep their weights)
  and export them together; name them `Body_LOD0`, `Body_LOD1`… for engines that
  auto-detect LOD groups (Unity, Unreal).
