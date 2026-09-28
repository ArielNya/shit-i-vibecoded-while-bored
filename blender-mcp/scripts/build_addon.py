"""Sync the vendored protocol module into the add-on and zip it for installation.

python scripts/build_addon.py            # sync + write dist/blender_mcp_addon-<version>.zip
python scripts/build_addon.py --sync     # only sync protocol.py and the skill files
"""

from __future__ import annotations

import argparse
import shutil
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_SRC = ROOT / "src" / "blender_mcp" / "protocol.py"
ADDON_DIR = ROOT / "addon" / "blender_mcp_addon"
PROTOCOL_DST = ADDON_DIR / "protocol.py"
DIST = ROOT / "dist"
DOCS = ROOT / "src" / "blender_mcp" / "docs"
SKILLS = ROOT / "skills"

# Agent skills are generated from the reference notes the server also serves, so the
# two never drift apart: skills/<name>/SKILL.md = front matter + docs/<topic>.md.
SKILL_SOURCES = {
    "lowpoly-character": (
        "character",
        "Model a game-ready low-poly humanoid or character in Blender (via the "
        "blender-mcp tools) from a front and a side view reference sheet, then rig, "
        "skin, pose-test, animate and export it. Use when asked to build, rig or "
        "animate a low-poly person, creature or mascot from reference images.",
    ),
}


def skill_text(name: str) -> str:
    topic, description = SKILL_SOURCES[name]
    body = (DOCS / f"{topic}.md").read_text()
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}"


def sync_skills() -> None:
    for name in SKILL_SOURCES:
        out = SKILLS / name / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(skill_text(name))
        print(f"synced {out.relative_to(ROOT)}")


def sync_protocol() -> None:
    shutil.copyfile(PROTOCOL_SRC, PROTOCOL_DST)
    print(f"synced {PROTOCOL_DST.relative_to(ROOT)}")


def build_zip() -> Path:
    manifest = tomllib.loads((ADDON_DIR / "blender_manifest.toml").read_text())
    DIST.mkdir(exist_ok=True)
    out = DIST / f"blender_mcp_addon-{manifest['version']}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                # Manifest at the zip root, as Blender's "Install from Disk" expects.
                zf.write(path, path.relative_to(ADDON_DIR))
    print(f"wrote {out.relative_to(ROOT)}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="only sync generated files")
    args = parser.parse_args()
    sync_protocol()
    sync_skills()
    if not args.sync:
        build_zip()


if __name__ == "__main__":
    main()
