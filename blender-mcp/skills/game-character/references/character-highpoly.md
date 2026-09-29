# High-poly characters: subdivision cages and high → low baking

There are two routes, and both start from the same clean quad **cage**:

- **Film / animation**: the cage is the rigged mesh, and a SUBSURF modifier smooths it
  at render time. The rig deforms the light cage, so animation stays fast.
- **Games (high → low)**: a detailed high mesh exists only to bake maps. The game
  gets a light mesh (the cage, or a reduced version of it) with a normal map that fakes
  the detail.

Read `../SKILL.md` for the standards (pose, topology, budgets). This
note is only about what differs from low poly.

What these tools can and can't do: they model with extrusions, loop cuts, modifiers,
remeshing and procedural noise. There are **no sculpt brushes**, so organic surface
detail (wrinkles, pores, cloth folds) is limited to noise, smoothing and modelled
forms. Say so if the brief expects a sculpt; the pipeline still produces clean, bakeable
geometry and deforming rigs.

## 1. Build the cage

Model it like the low-poly walkthrough (`character.md`): box-model from a
reference sheet, with edge loops at every joint. Then add the density that subdivision
needs:

- **All quads.** Triangles and n-gons make pinches and ripples under SUBSURF.
- **Joint loops in full**: 3 at elbows and knees, a full shoulder set, knuckles (see
  the table in `game-character`).
- **More sides on limbs**: 8 around arms, legs, neck and fingers before subdivision.
  Low poly used 4–6.
- **Support loops** where the surface must stay sharp after subdividing (armour
  rims, boot soles, collar edges, nails): a `loop_cut` close to the edge, or
  `bevel(width=small, segments=2)` on the edge. Without them, SUBSURF rounds everything
  off like soap.
- **Budget**: 3k–15k quads for a game high-poly cage, 10k–50k for film.

Preview the result non-destructively:

```
add_modifier(object="Body", type="SUBSURF", params={"levels": 1, "render_levels": 2})
shade(name="Body", smooth=true)
render_preview(view="iso", size=384)
check_game_ready(name="Body")      # warns about the live SUBSURF; that's intended here
```

Look for pinching around poles, ripples along long loops and soft edges that should be
hard. Fix the cage, never the subdivided result.

## 2a. Film route: rig the cage

1. Keep SUBSURF live. Don't apply it.
2. Rig and bind as in `rigging.md` (`create_humanoid_rig`,
   `bind_to_armature`). Binding computes weights on the cage.
3. `bind_to_armature` puts its Armature modifier **first** in the stack, so the cage
   deforms and then smooths. Keep it that way if you add modifiers later
   (`move_modifier(..., index=0)`).
4. Pose-test with SUBSURF on. Joints should stay round, not faceted.
5. Export: `.blend` for Blender pipelines. For `.fbx`/`.glb` to other packages, export
   the cage (`export_file(apply_modifiers=false)`) and let the target subdivide it.
   Applying SUBSURF bakes millions of vertices into the file.

## 2b. Game route: high → low bake

```
# 1. The high mesh: a subdivided, detailed copy (never exported)
duplicate_object(name="Body", new_name="Body_high")
add_modifier(object="Body_high", type="SUBSURF", params={"levels": 2})
apply_modifier(object="Body_high", modifier="Subsurf")
# optional surface detail on the high only (cloth grain, stone, scales):
add_noise(name="Body_high", strength=0.003, scale=40, select=<region>)
smooth_vertices(name="Body_high", select=<region>, factor=0.5, iterations=3)

# 2. The low mesh: the cage itself, or a lighter copy for a tight budget
#    (DECIMATE with use_symmetry, see blender://docs/efficiency)

# 3. UVs on the low mesh only
mark_seams(name="Body", select=<hidden edges>)
uv_unwrap(name="Body", method="seams")          # coverage 0.6-0.8, nothing outside 0-1

# 4. Bake
bake_maps(low="Body", high=["Body_high"], maps=["normal", "ao"], size=2048,
          cage_extrusion=0.02)
render_preview(view="iso", engine="eevee", size=512)   # does the detail read?

# 5. Clean up: hide or delete the high before rigging and export
delete_objects(names=["Body_high"])
```

**Getting clean bakes:**

- The low mesh must **enclose or closely follow** the high mesh. `cage_extrusion` is
  how far rays start outside the low surface. Set it to about the largest gap between
  the two (1–3 % of the character's height is typical). Holes or black patches mean
  it's too small. Detail from the wrong place (an arm baked onto the chest) means it's
  too big: separate the parts or pose the arms further from the body.
- Hard edges on the low mesh need a **UV seam** along them, or the normal map shows a
  gradient smear.
- **No overlapping UVs** (except deliberately mirrored halves, which bake identical
  detail on both sides).
- Bake before rigging. The bake uses the rest pose.
- `ao` is saved but not linked (engines take it as its own map). `normal`, `color`
  and `roughness` are hooked into the low mesh's material automatically.
- Bakes take a few seconds at 1024 and scale with size². Use 512 while iterating and
  the final size once.

**Texture sizes**: 1024 for secondary characters, 2048 for heroes, 4096 only for AAA
close-ups. The folder is `bakes/` in the workspace; the file names are
`<low>_<map>.png`.

## 3. Organic high-poly without a cage (creatures, rocks, statues)

When there's no rig and the shape is lumpy rather than structured:

```
create_primitive(type="ico_sphere", subdivisions=4, …)     # or a blockout of joined parts
remesh(name=…, voxel_size=0.01)                            # even, dense topology
add_noise(name=…, strength=…, scale=…)                     # large forms first, then small
smooth_vertices(name=…, iterations=5)
```

That mesh is **not rig-ready** (voxel topology has no joint loops). To animate it,
treat it as the *high* mesh: build a clean low cage over it, bake, and rig the cage.

## 4. Checks

- The cage passes `check_game_ready` (a live SUBSURF gives a warning and nothing else).
- The pose tests in `rigging.md` look smooth with SUBSURF on.
- In the game route, the baked normal map has no black holes, seams or smears in
  `render_preview(engine="eevee")`, and the high mesh isn't in the export.
