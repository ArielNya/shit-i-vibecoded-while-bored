# shit-i-vibecoded-while-bored

A monorepo of side projects. Each project lives in its own top-level folder and
is fully self-contained: its own README, dependencies, tooling and tests. Nothing
at the root is shared unless it's genuinely repo-wide (this README, the license,
`.gitignore`).

## Projects

| Folder | What it is | Status |
| --- | --- | --- |
| [`blender-mcp/`](blender-mcp/) | MCP server that lets Claude / Codex inspect and model inside Blender, plus skills for low-poly characters and Roblox avatar items (hats, clothing, bodies) | M7 done (all milestones) — releases tagged `blender-mcp-v*` — see [`PLAN.md`](blender-mcp/PLAN.md) |
| [`godot-mcp/`](godot-mcp/) | MCP server that lets agents in any major harness edit, run and debug Godot 4.7+ projects | M5 done (edit, run & play-test, assets & tile levels; stdio + HTTP; smoke-tested with Claude Code, Gemini CLI, opencode) — see [`PLAN.md`](godot-mcp/PLAN.md) |
| [`roblox-mcp/`](roblox-mcp/) | Companion MCP server + agent skill for building Roblox games alongside Studio's built-in MCP server | M7 done, M6 mostly done (single-server `--wrap-studio` mode, Rojo projects + live sync, type checking and formatting, tests, asset uploads, cloud Luau runs, data stores, opt-in publishing, skill with tested recipes, evals; Open Cloud parts and Studio untested yet; offline Engine API docs for Studio 0.740, agent skill v0; stdio + HTTP) — see [`PLAN.md`](roblox-mcp/PLAN.md) |
| [`vencord-mobile/`](vencord-mobile/) | Mobile-UX theme + plugin for Vencord on Android via VendroidEnhanced | M0 done, M1 code-complete, M2 in progress — see [`PLAN.md`](vencord-mobile/PLAN.md) |

## Conventions

- **One folder per project**, named in `kebab-case`.
- Each project has a `README.md` (what + how to run) and may have a `PLAN.md`
  (design notes, roadmap).
- Projects pick their own language/tooling. Lockfiles live inside the project
  folder, never at the root.
- No CI: each project's README lists the checks to run locally before pushing.
- Milestone work happens on a branch named after the milestone (`M3`, `M4`, …),
  created from the previous milestone's branch.
- Commit messages are prefixed with the project folder, e.g.
  `blender-mcp: add scene inspection tools`.
