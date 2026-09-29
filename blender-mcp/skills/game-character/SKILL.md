---
name: game-character
description: Model rig-ready characters for games and animation with the blender-mcp tools: low poly (box-modelled from a front/side reference sheet) or high poly (subdivision cage, high-to-low normal map baking), with correct bind pose, deforming topology, UVs and budgets; then rig, skin, pose-test, animate, add LODs and export for Unity, Unreal, Godot, Mixamo or film. Use for any character, creature, mascot or avatar request, and for questions about T/A-pose, edge loops, weights, bakes or character export.
---

# Rig-ready characters for games and animation

The standards a character model must meet before anyone rigs or animates it, and how
to meet them with these tools, for both low-poly and high-poly characters. "Rig-ready"
means that an automatic rig (`create_humanoid_rig`, Mixamo, Unity Humanoid, Unreal
retargeting, Rigify) works first time, and that joints bend without collapsing.

Pick the route, then follow its walkthrough:

| Brief | Route | Walkthrough |
|---|---|---|
| Stylised / mobile / "low poly", flat colours or small textures | **Low poly**: box-model the final mesh directly | `references/character.md` |
| PC/console game, realistic or detailed | **High → low**: detailed high mesh, light game mesh, baked maps | `references/character-highpoly.md` |
| Film, cinematics, offline animation | **Subdivision**: clean quad cage + SUBSURF at render time | `references/character-highpoly.md` (cage section) |
| Only an image, no turnaround sheet | Read `blender://docs/img2model` first, then one of the above | |
| A Roblox avatar body, accessory or layered clothing | the `roblox-avatar` skill (R15 bones, cages, Roblox budgets), after the standards below | |

Rigging, skinning, testing and export are the same for every route:
`references/rigging.md`.

## 1. Non-negotiables (every route)

These are what break rigs and engine imports. `check_game_ready` verifies most of
them.

| Rule | Why | How |
|---|---|---|
| **Real scale**: 1 unit = 1 m, true height | physics, animation retargeting, cameras | `transform_object(dimensions=…)`, then `apply_transform` |
| **Transforms applied**: rotation 0, scale 1 | skinning and export multiply unapplied transforms into chaos | `apply_transform(rotation=true, scale=true)` |
| **Feet on z = 0, centred on x = 0, origin at the world origin** | the character's root/pivot is the floor between the feet | build it there; `check_game_ready` flags it |
| **Faces -Y, Z up, left side on +X** | Blender's front view; exporters convert it for each engine | model in front view |
| **Symmetric across X** (unless the design isn't) | mirrored weights, poses and animation | model half + MIRROR, or edit both sides with one selection |
| **Quads in deforming areas**, no n-gons anywhere | n-gons triangulate unpredictably and pinch when bent | `get_object_info` → `mesh.ngons` = 0 |
| **Manifold, no loose or doubled vertices, normals outward** | heat weighting, baking and outlines fail otherwise | `merge_by_distance`, `recalc_normals` |
| **UVs**, no overlaps (unless deliberately mirrored) | textures and bakes | `uv_unwrap`, `get_uv_info` |
| **1–3 materials** per character | each material is a draw call | combine regions into one material + texture where possible |
| **Named parts** | riggers, engines and your own later calls | `Body`, `Head`, `Eyes`, `Hair`, `Rig`; bones `.L`/`.R` |

## 2. The bind pose

Model in a neutral pose that an auto-rigger understands and that leaves room for every
joint to bend both ways:

- **A-pose** (arms 30–45° down from horizontal) is the default for game characters.
  The shoulders deform better because the rest pose is halfway through their range.
  Use a **T-pose** (arms horizontal) when the target asks for it: Mixamo, some VR/VTuber
  pipelines, or a T-pose reference sheet.
- **Arms and legs straight**, or elbows and knees bent 5–10° towards their natural
  bend. The slight bend tells IK solvers which way the joint folds.
- **Palms down** (T-pose) or facing the thighs at 45° (A-pose). **Fingers straight and
  slightly spread**, and the thumb 30–45° forward and down, off the index finger.
- **Feet flat, parallel**, about hip-width apart; toes forward.
- **Head level, looking forward. Mouth closed** (but modelled with separate lips if
  the face will be animated), **eyes open**, and the neck straight.
- **Gaps everywhere parts meet**: arms clear of the torso, legs clear of each other,
  fingers clear of each other. Skinning can't separate surfaces that touch.

## 3. Topology that deforms

The number of loops matters less than **where** they are. Low poly needs at least
the minimum, mid and high poly the full set:

| Joint | Low poly (min) | Mid / high poly | Notes |
|---|---|---|---|
| Elbow, knee | 1 (at the joint) | 3 (joint + one either side) | the outer side stretches, the inner side folds; wedge loops pinch less |
| Shoulder | 1–2 around the arm socket | 3 + a loop that runs from the armpit over the shoulder | the hardest joint; give it the densest area |
| Hip | 1 angled loop at the leg root (crotch to hip bone) | 2–3 | the loop follows the underwear line, not a horizontal ring |
| Wrist, ankle | 1 | 2 | keep the wrist loop perpendicular to the forearm |
| Knuckles | 0 (mitten hands) | 3 per knuckle | fingers: 5–8 sides low/mid, 8 high |
| Neck | 1 | 2–3 | allows turning and nodding |
| Spine | 2–3 horizontal loops (chest, waist, pelvis) | 5+ | lets the torso bend and twist |
| Face (animated) | none | concentric loops around the eyes and mouth; nasolabial loop | required for blend-shape/facial bone rigs |

- **Even spacing** in deforming areas. Dense next to sparse creates creases.
- **Poles** (vertices with 3 or 5+ edges) away from joints: put them on the chest,
  shoulder blade or hip bone, not on the elbow.
- **Triangles** only in areas that never bend (head top, sole of the foot, hard
  armour) on low poly. Keep them out entirely on subdivision cages.
- **Edge flow follows the forms**: muscles for realistic characters, big shapes for
  stylised ones. A loop that crosses a joint diagonally bends badly.

With these tools, loops come from `loop_cut` (across a limb: select one edge along
it) and from each `extrude` (every extrusion leaves a loop). Position them with
`transform_elements(type="verts", center=…)`.

## 4. Parts and separation

- **Body**: one continuous mesh if possible. Heat weighting (`bind_to_armature`
  automatic) needs it closed and connected.
- **Eyes, teeth, tongue**: separate objects, each skinned 100% to `head` (or to
  eye bones for looking around): `set_vertex_weights(mesh="Eyes", group="head",
  select={"all": true}, weight=1)` after `bind_to_armature(method="nearest")`.
- **Hair**: low poly uses a solid shell extruded from the head. Hair cards (planes with
  alpha) are fine in mid and high poly. Long hair, ponytails, capes and tails get their
  own bone chains (`extra_bones`, see `references/rigging.md`).
- **Clothing**: model it as part of the body on low poly. For layered clothing,
  **delete the body faces hidden under tight clothing**. This saves triangles and
  prevents poke-through. Loose skirts and coats need their own bones or physics. Keep
  them 1–2 cm off the body.
- **Accessories and weapons**: separate objects, rigidly weighted to one bone, or
  parented to a socket bone (`weapon.R` under `hand.R`) so they can be swapped.

## 5. UVs and textures

- **Seams where nobody looks**: inside of arms and legs, under the arms, down the back
  of the head under the hair, around the neck line, around hands and feet, and along
  clothing borders. Mark them with `mark_seams`, then run
  `uv_unwrap(method="seams")`.
- Use `method="smart"` for props, accessories and quick results.
- Check with `get_uv_info`. You want coverage 0.6–0.8 and no faces outside 0–1.
  Coverage above 1 means overlap, which is fine only for mirrored halves on purpose.
- **Texel density** consistent across the body. The face may get 1.5–2× (players
  look at it).
- Several flat-colour materials can become **one material with one texture**:
  `bake_texture` bakes every material's colour onto a fresh UV map (one draw call, and
  what Roblox and many mobile pipelines want).
- Texture sizes: 256–1024 for mobile, 2048 for PC characters, 4096 for AAA heroes.
  Flat-colour low poly can use one tiny palette texture, or no textures at all
  (material per region, 1–3 materials).

## 6. Budgets

| Target | Triangles | Bones | Materials | Texture |
|---|---|---|---|---|
| Tiny / PS1 style | 300–1,000 | 15–25 | 1 | 64–256 or none |
| Mobile / stylised | 1,500–5,000 | 20–40 | 1–2 | 512–1024 |
| Indie PC / console | 10k–30k | 40–80 (fingers) | 1–3 | 2048 |
| AAA hero | 50k–150k | 80–200 (face) | 2–5 | 4096 |
| Film cage | 10k–50k quads (subdivided) | any | any | any |

Bones: `create_humanoid_rig` gives 22 (no fingers, no face). Add fingers (3 × 5 × 2 =
30) and face bones only when the budget and brief call for them.

## 7. Definition of done

Run:

```
check_game_ready(name="Body", max_triangles=<budget>, expect_rig=true)
```

It must say `ok: true`. Read every warning and fix it, or say in the summary why it's
fine. Then:

1. Take a front and side `render_preview(ortho=true, size=384)` against the reference.
2. Run every pose test in `references/rigging.md` (arms down, elbows, leg lift, knee,
   head turn, bend) and look at the worst two at `size=512`.
3. Export `.glb` (or `.fbx`), re-import it into an empty scene, and check that the
   armature and skin are present.
4. Summarise triangles, bones, materials, texture sizes, LODs, and anything left for a
   human.

---

Links like `blender://docs/<topic>` are resources of the blender-mcp server (read them with your MCP resource tool). The same notes ship as skills: `blender-mcp` (efficiency, workflow, selection, modifiers, materials, troubleshooting), `img2model` (img2model).
