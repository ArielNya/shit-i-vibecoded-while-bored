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

# Headless rendering (Workbench/EEVEE) needs OpenGL; Mesa provides it in software.
if [ -d blender-mcp ] && ! ldconfig -p | grep -q "libEGL.so.1"; then
  echo "session-start: installing Mesa for headless rendering" >&2
  if command -v apt-get >/dev/null 2>&1; then
    apt-get install -y -q libegl1 libgl1-mesa-dri libgles2 >/dev/null 2>&1 \
      || { apt-get update -q >/dev/null 2>&1 && apt-get install -y -q libegl1 libgl1-mesa-dri libgles2 >/dev/null 2>&1; } \
      || echo "session-start: Mesa install failed; render tests will fail" >&2
  fi
fi

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

# godot-mcp integration tests need a Godot editor binary. Installed once, outside the repo.
if [ -d godot-mcp ]; then
  GODOT_VERSION="4.7.2-stable"
  GODOT_DIR="$HOME/.cache/godot-mcp/godot-$GODOT_VERSION"
  GODOT_BIN="$GODOT_DIR/Godot_v${GODOT_VERSION}_linux.x86_64"
  if [ ! -x "$GODOT_BIN" ]; then
    echo "session-start: downloading Godot $GODOT_VERSION" >&2
    mkdir -p "$GODOT_DIR"
    curl -sSL -o "$GODOT_DIR/godot.zip" \
      "https://github.com/godotengine/godot-builds/releases/download/$GODOT_VERSION/Godot_v${GODOT_VERSION}_linux.x86_64.zip" \
      && unzip -oq "$GODOT_DIR/godot.zip" -d "$GODOT_DIR" && rm -f "$GODOT_DIR/godot.zip" \
      || echo "session-start: Godot download failed; godot-mcp integration tests will skip" >&2
  fi
  if [ -x "$GODOT_BIN" ] && [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export GODOT_BIN=\"$GODOT_BIN\"" >> "$CLAUDE_ENV_FILE"
  fi
fi

# ponytail Claude Code plugin (github.com/DietrichGebert/ponytail), installed at user scope.
if command -v claude >/dev/null 2>&1 && ! claude plugin list 2>/dev/null | grep -q "ponytail@ponytail"; then
  echo "session-start: installing ponytail plugin" >&2
  claude plugin marketplace add DietrichGebert/ponytail >/dev/null 2>&1 || true
  claude plugin install ponytail@ponytail --scope user >/dev/null 2>&1 \
    || echo "session-start: ponytail plugin install failed" >&2
fi
