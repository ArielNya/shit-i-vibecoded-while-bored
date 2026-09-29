# Selection specs (mesh tools)

Mesh tools (`extrude`, `inset`, `bevel`, `loop_cut`, `delete_elements`,
`transform_elements`, `select_elements`, …) take a `select` object. All given
criteria must match (AND). Use `select_elements` to preview before editing.

| Key | Meaning | Works on |
| --- | --- | --- |
| `all: true` | everything | all |
| `indices: [..]` | explicit indices | all |
| `normal: [x,y,z]` + `max_angle` (deg, default 30) | facing a direction | faces, verts, edges |
| `position: {axis, min, max}` (or a list of them) | element center in a range | all |
| `material: 0` or `"Name"` | faces using that slot | faces |
| `boundary: true/false` | on an open edge (or not) | all |
| `sharp_angle: 30` | edges whose faces meet at ≥ 30° | edges |
| `space: "world"` | interpret normal/position in world space (default local) | all |

The element type is the tool's `type` argument (`faces` default; `edges`, `verts`).

## Examples

- Top face of a box: `{"normal": [0, 0, 1], "max_angle": 5}`
- Everything above the middle: `{"position": {"axis": "z", "min": 0}}`
- Rim edges of a cylinder with top at z = 0.6: `{"sharp_angle": 45, "position": {"axis": "z", "min": 0.55}}`
- Right half: `{"position": {"axis": "x", "min": 0.001}}`
- A band: `{"position": [{"axis": "z", "min": 0.2}, {"axis": "z", "max": 0.4}]}`

## Indices go stale

Indices are only valid until the topology changes (extrude, inset, bevel, cuts,
deletes, joins). Tools return the indices of what they created — use those:

```
inner = inset(select={"normal":[0,0,1],"max_angle":5}, thickness=0.05)
extrude(select={"indices": inner.inner_faces}, distance=-1)   # hollow it
```

Don't reuse `inner.inner_faces` after that extrude; use the extrude's `new_faces`.

## Local vs world

Positions and normals are in the object's local space unless `space: "world"`.
After `apply_transform`, local and world coincide except for location.
