#!/usr/bin/env bash
# Builds Vencord's standalone web bundle (the browser.js/browser.css Vendroid injects)
# with the MobileUX userplugin, following docs.vencord.dev "Installing Vencord" +
# "Installing custom plugins". Extra args go to `pnpm buildWebStandalone` (e.g. --dev).
set -euo pipefail

VENCORD_REPO=https://github.com/Vendicated/Vencord.git
VENCORD_REF=7f0c10cc29fd789f2f4828ae3dc947623e837920

root=$(cd "$(dirname "$0")/.." && pwd)
src="$root/.cache/Vencord"

if [ ! -d "$src/.git" ]; then
    git clone --filter=blob:none "$VENCORD_REPO" "$src"
fi
git -C "$src" fetch --quiet origin "$VENCORD_REF"
git -C "$src" checkout --quiet --detach "$VENCORD_REF"

rm -rf "$src/src/userplugins"
mkdir -p "$src/src/userplugins"
cp -r "$root/plugin/." "$src/src/userplugins/"

(cd "$src" && pnpm install --frozen-lockfile && pnpm buildWebStandalone "$@")

mkdir -p "$root/dist"
cp "$src/dist/browser.js" "$src/dist/browser.css" "$root/dist/"

grep -q '"MobileUX"' "$root/dist/browser.js" || { echo "MobileUX missing from browser.js" >&2; exit 1; }
echo "Built $root/dist/browser.js and browser.css (Vencord $VENCORD_REF + MobileUX)"
