#!/bin/bash
# SessionStart hook for Claude Code on the web: installs each project's dependencies
# so tests and linters work. Monorepo-aware: syncs every top-level project with a uv.lock.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

for lock in */uv.lock; do
  [ -e "$lock" ] || continue
  project="$(dirname "$lock")"
  echo "session-start: uv sync in $project" >&2
  (cd "$project" && uv sync --quiet)
done

# blender-mcp integration tests need Blender; the bpy wheel is a pip-installable
# build of Blender 4.2 that works headless. Installed once, outside the repo.
if [ -d blender-mcp ]; then
  BPY_ENV="$HOME/.cache/blender-mcp/bpyenv"
  if ! "$BPY_ENV/bin/python" -c "import bpy" >/dev/null 2>&1; then
    echo "session-start: installing bpy into $BPY_ENV" >&2
    uv venv --quiet --allow-existing -p 3.11 "$BPY_ENV"
    uv pip install --quiet -p "$BPY_ENV/bin/python" "bpy>=4.2,<4.3"
  fi
  if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export BLENDER_PYTHON=\"$BPY_ENV/bin/python\"" >> "$CLAUDE_ENV_FILE"
  fi
fi
