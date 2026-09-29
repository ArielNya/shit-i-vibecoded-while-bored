# Working efficiently with blender-mcp

How to get good models out of these tools with few calls, few tokens and few polygons.
Read this once per session. The other notes (`blender://docs`) go deeper on each area.

## The loop

1. **Look once.** Start with `get_scene_info`, then `list_objects` only if you need
   more. Don't assume the default cube, camera or light still exist.
2. **Plan on paper.** Before the first edit, write a short table of the parts, their
   sizes in metres, and the triangle budget. A plan costs a few hundred tokens and saves
   dozens of trial-and-error calls.
3. **Build big to small.** Silhouette first, then secondary forms, then detail. Stop
   adding detail when the budget or the brief says so.
4. **Verify with numbers, confirm with pictures.** After every step, read the numbers
   the tool returned. Take a picture only at stage ends (see below).
5. **Finish with `check_game_ready`.** It runs every topology, transform, UV and weight
   check in one call and lists only what's wrong.

Mistakes are one `undo` away. Every tool call is one undo step, so undoing is cheaper
than repairing by hand.

## Token budget

**Images are the most expensive thing you can ask for.** An image costs roughly
`width × height / 750` tokens:

| `size` | ≈ tokens | Use for |
|---|---|---|
| 256 | 90 | "did anything happen at all" |
| 384 | 200 | routine stage checks (default choice) |
| 512 | 350 | comparing proportions against a reference |
| 768 (default) | 790 | final look, or details you can't see at 512 |
| 1024+ | 1,400+ | only when the user wants the render itself |

- Pass `size=384` to `get_viewport_screenshot` and `render_preview` unless you need
  more.
- One `view="iso"` shot often replaces front + side + top. For proportions, use
  `view="front"`/`"right"` with `ortho=true`.
- Frame just the subject (`object=...`) so its pixels aren't spent on empty space.
- Don't take a screenshot after every edit. Batch 3–6 edits, then look.

**Numbers are cheap.** Prefer these over pictures and raw dumps:

| Need | Call | Cost |
|---|---|---|
| Size / position | `get_object_info` → `dimensions`, `location` | small |
| Topology health | `check_game_ready` (or `get_object_info` → `mesh`) | small |
| Which faces a spec hits | `select_elements` → `count`, `centers` | small |
| Where a selection ended up | the `bounds` in `transform_elements`' result | free |
| UV quality | `get_uv_info` | small |
| Skinning | `bind_to_armature` / `get_armature_info` summary | small |
| Raw vertices | `get_mesh_data` | **large**: only for small meshes, paginated |

**Chain the results tools already return.** `extrude` returns the new cap faces, so
feed `new_faces` into the next `extrude` instead of selecting again.
`create_primitive` returns the real name (Blender renames on clashes).

**Do more per call:**

- Select both sides at once (bound on x), then extrude with `mode="individual"`.
- Use `pose_bone(mirror=true)` to pose both limbs in one call.
- Use `transform_elements(size=…, center=…)` to hit exact dimensions in one call
  instead of nudging with `scale`.
- Model one half and add a MIRROR modifier. Every edit then lands on both sides.
- `execute_python`, when the user has enabled it, can do a long repetitive loop (for
  example 40 identical bolts) in one call. It's off by default. Don't ask for it for
  things the tools already do.

**Trim the tool list.** Tool definitions are sent with every request. All toolsets
together are about 26k tokens. For a character session,
`BLENDER_MCP_TOOLSETS=inspect,view,edit,mesh,rig,gameready,look,files,animate` drops
`sculpt`, `nodes`, `python` and `instances` (about 3k tokens). For a pure blockout,
`inspect,view,edit,mesh,look` is about 16k. This is the user's setting, so suggest it
and don't insist.

## Selections without surprises

Most wasted calls come from a selection that matched more than intended.

- **Bound every range on both ends** (`min` *and* `max`) once the mesh has limbs. An
  unbounded `{"normal": [1,0,0]}` matches every side face of the body, arms and legs.
- **Check `count` first** with `select_elements` when you're unsure. It's a cheap call;
  a wrong extrude costs an undo plus a re-check.
- `max_angle: 5` on blocky meshes. The default 30° also grabs bevelled neighbours.
- Indices go stale after any topology change. Use returned indices or select again.
- Use `type="verts"` in `transform_elements` to move exactly those vertices.

See `blender://docs/selection` for the full spec.

## Polygon budget

**Count triangles, not faces.** Engines draw triangles: a quad is 2, an n-gon is n−2.
`check_game_ready` and `get_object_info` → `mesh.triangles` report them.

Typical budgets (triangles):

| Target | Hero character | NPC / secondary | Prop (hand-held) | Prop (large) |
|---|---|---|---|---|
| Stylised "PS1" / tiny low poly | 300–1,000 | 200–600 | 20–150 | 100–500 |
| Mobile / stylised low poly | 1,500–5,000 | 800–3,000 | 100–800 | 500–2,000 |
| Indie PC / console | 10k–30k | 5k–15k | 500–3k | 2k–10k |
| AAA current gen | 50k–150k | 20k–60k | 2k–15k | 10k–50k |
| Film / animation (subdivision cage) | 10k–50k quads, subdivided at render | | | |

If the brief doesn't say, ask once or pick the mobile/stylised row and say so.

**Where polygons go:**

1. **Silhouette** first. Edges that change the outline are worth the most.
2. **Deformation** second. Joints need loops (elbows and knees 3, shoulders and hips
   2–3, wrists and ankles 1–2) or they can't bend.
3. **Close-up focus** third: face and hands on a character, the business end of a
   weapon.
4. **Flat and hidden areas get nothing.** A flat panel is one quad. Delete faces nobody
   will see (inside joined parts, under tight clothing, bottoms of props on the
   ground).

**Cheap tricks that look expensive:**

- Cylinders: 6–8 sides for limbs, handles and cables in low poly; 12–16 in mid poly;
  more only on large, close-up round shapes.
- Bake detail instead of modelling it: build a high version, then `bake_maps` a
  normal map onto the light version. See `blender://docs/character-highpoly`.
- Flat colours or a small palette texture instead of more geometry for colour changes.
  A colour change only needs an edge where it happens.
- Many materials cost many draw calls. `bake_texture` merges all of an object's
  material colours into one texture and one material.
- `shade(smooth=true, auto_smooth_angle=40)` makes a low-poly round shape read as
  round while keeping hard edges hard.

**LODs** (levels of detail) for anything seen at a distance:

```
duplicate_object(name="Body", new_name="Body_LOD1")
add_modifier(object="Body_LOD1", type="DECIMATE",
             params={"ratio": 0.5, "use_symmetry": true, "symmetry_axis": "X"})
move_modifier(object="Body_LOD1", modifier="Decimate", index=0)   # before the Armature
apply_modifier(object="Body_LOD1", modifier="Decimate")
check_game_ready(name="Body_LOD1")
```

Typical ratios are LOD1 0.5, LOD2 0.25 and LOD3 0.1. Always pass `use_symmetry`,
because decimation is otherwise lopsided. A duplicate of a skinned mesh keeps its
vertex groups and Armature modifier, so LODs stay rigged.

## Other notes

- `blender://docs/workflow`: the general modelling loop
- `blender://docs/selection`: selection specs
- `blender://docs/modifiers`: modifier names, settings and stack order
- `blender://docs/materials`: materials, lights, cameras, render engines
- `blender://docs/troubleshooting`: symptoms and fixes
- `blender://docs/game-character`: rig-ready characters (low and high poly)
- `blender://docs/img2model`: models from images
