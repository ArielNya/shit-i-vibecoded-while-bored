# shit-i-vibecoded-while-bored

A monorepo of side projects. Each project lives in its own top-level folder and
is fully self-contained: its own README, dependencies, tooling and tests. Nothing
at the root is shared unless it's genuinely repo-wide (this README, the license,
`.gitignore`, CI glue).

## Projects

| Folder | What it is | Status |
| --- | --- | --- |
| [`blender-mcp/`](blender-mcp/) | MCP server that lets Claude / Codex inspect and model inside Blender | M4 done, M5 in progress (reference docs + prompts added) — see [`PLAN.md`](blender-mcp/PLAN.md) |

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
