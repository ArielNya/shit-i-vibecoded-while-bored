# Character bodies

A full avatar body: 15 skinned meshes on the R15 rig, 19 attachments and an outer cage
per part. Roblox splits it into 6 assets on upload. Sources in creator-docs:
`avatar/character-bodies/specifications.md` and `export.md`; `avatar/dynamic-heads/*`.
It's the biggest job in this skill. For a stylised game NPC that nobody wears as an
avatar, blender-mcp's `lowpoly-character` skill is enough. Use this reference only
when it must work as a Roblox avatar body.

## Start from Roblox's files

From
`https://media.githubusercontent.com/media/Roblox/creator-docs/main/content/en-us/assets/`:

- `modeling/meshes/reference-files/Rig_and_Attachments_Templates.zip`: the armature
  with the R15 bones, plus the 19 `_Att` meshes.
- `modeling/meshes/reference-files/Body_Cage_Templates.zip`: `<Part>_OuterCage` for
  all 15 parts.
- `art/reference-files/RthroMannequin.fbx`: a finished Normal body to compare against.

## Requirements

- **15 meshes** named `<Part>_Geo`:
  - `Head`;
  - `UpperTorso`, `LowerTorso`;
  - `LeftUpperArm`, `LeftLowerArm`, `LeftHand` and the same for the right;
  - `LeftUpperLeg`, `LeftLowerLeg`, `LeftFoot` and the same for the right.
- Each part is **capped**, so it's watertight on its own.
- **Triangle budgets per asset:**

  | Asset | Parts | Max triangles |
  | --- | --- | --- |
  | DynamicHead | Head | 4,000 |
  | Torso | UpperTorso + LowerTorso | 1,750 |
  | Each arm | UpperArm + LowerArm + Hand | 1,248 |
  | Each leg | UpperLeg + LowerLeg + Foot | 1,248 |

  The total is 10,742.
- **Size (studs, W × H × D):**

  | Scale | Min | Max |
  | --- | --- | --- |
  | Normal | 1.35 × 3.6 × 0.7 | 8.6 × 9.5 × 2.25 |
  | Slender | 1.35 × 3.6 × 0.7 | 6 × 9.5 × 2 |
  | Classic | 1.35 × 3.6 × 0.7 | 8 × 9.1 × 2 |

  Each part fills ≥ 50% of its bounding box in front, side and back views, and is
  fully opaque.
- **Rig:** `Root` → `HumanoidRootNode` → `LowerTorso` → `UpperTorso` → `Head`, with the
  arm chains under `UpperTorso` and the legs under `LowerTorso`. `Root` and
  `LowerTorso` sit at (0, 0, 0). Pose is I, A or T.
- **Skinning:** ≤ 4 influences per vertex; nothing on `Root`.
- **19 attachments**, each a small mesh named `<Name>_Att`. The template has them all
  in place; move them if your proportions differ:
  - Head: `FaceCenter`, `FaceFront`, `Hat`, `Hair`.
  - UpperTorso: `Neck`, `LeftCollar`, `RightCollar`, `BodyFront`, `BodyBack`.
  - LowerTorso: `Root` at the origin; `WaistFront`, `WaistCenter`, `WaistBack`.
  - Arms, hands and feet: `LeftShoulder`, `RightShoulder`, `LeftGrip`, `RightGrip`
    (perpendicular to the forearm), `LeftFoot`, `RightFoot`.
- **Outer cages:** `<Part>_OuterCage` for each of the 15 parts, from the template. As
  with clothing, never delete vertices or edit UVs; only move them to hug the body.
- **Head:** a Marketplace head is a *dynamic head* with FACS poses (animation on the
  timeline, exported with animation). blender-mcp can pose and keyframe bones, but
  building the full FACS set is a big job of its own. Tell the user and confirm scope
  before starting.
- **Skin tone:** to let players tint the skin, leave skin areas transparent in the
  texture. This is the one place where alpha is wanted.

## Workflow

1. Import the rig and body cage templates. Model each body part as its own object
   over the template proportions, or model one body and `separate_mesh` it at the
   joints and cap each part.
2. Name everything (`rename_object`). Parent the meshes under the armature and the
   cages under one empty.
3. Bake one texture per part, or one atlas shared by all parts.
4. `bind_to_armature` the parts to the template armature, then pose-test.
5. `check_roblox_asset(kind="body", body_scale="normal")` → fix every error.
6. Export with `export_file(..., roblox=true)`, including the armature, meshes,
   `_Att` meshes and cages. For a dynamic head, the docs' FBX settings also need
   **animation on**. `roblox=true` turns baked animation off, so for heads with FACS
   export through `execute_python` with `bake_anim=True` and the timeline covering
   every pose.
7. Studio: the Importer with Rig Type = Rthro (Normal), Rthro Narrow (Slender) or
   Default (Classic). Then test with the docs' avatar test tools.
