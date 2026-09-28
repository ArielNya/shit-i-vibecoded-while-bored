# shit-i-vibecoded-while-bored

A monorepo of side projects. Each project lives in its own top-level folder and
is fully self-contained: its own README, dependencies, tooling and tests. Nothing
at the root is shared unless it's genuinely repo-wide (this README, the license,
`.gitignore`, CI glue).

## Projects

| Folder | What it is | Status |
| --- | --- | --- |
| [`blender-mcp/`](blender-mcp/) | MCP server that lets Claude / Codex inspect and model inside Blender | M7 done (all milestones) — releases tagged `blender-mcp-v*` — see [`PLAN.md`](blender-mcp/PLAN.md) |
| [`godot-mcp/`](godot-mcp/) | MCP server that lets agents in any major harness edit, run and debug Godot 4.7+ projects | M2 done (inspect, edit scenes & scripts, diagnostics, docs, undo) — see [`PLAN.md`](godot-mcp/PLAN.md) |

## Conventions

- **One folder per project**, named in `kebab-case`.
- Each project has a `README.md` (what + how to run) and may have a `PLAN.md`
  (design notes, roadmap).
- Projects pick their own language/tooling. Lockfiles live inside the project
  folder, never at the root.
- CI workflows (when added) go in `.github/workflows/<project>.yml` and use
  `paths:` filters so a project only builds when its folder changes.
- Milestone work happens on a branch named after the milestone (`M3`, `M4`, …),
  created from the previous milestone's branch.
- Commit messages are prefixed with the project folder, e.g.
  `blender-mcp: add scene inspection tools`.
