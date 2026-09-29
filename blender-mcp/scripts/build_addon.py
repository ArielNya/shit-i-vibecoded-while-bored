"""Sync the vendored protocol module into the add-on and zip it for installation.

python scripts/build_addon.py            # sync + write dist/blender_mcp_addon-<version>.zip
python scripts/build_addon.py --sync     # only sync protocol.py and the skill files
"""

from __future__ import annotations

import argparse
import os
import re
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
SKILLS_DIR = ROOT / "skills"

# Agent skills are generated from the reference notes the server also serves, so the two
# never drift apart: skills/<name>/SKILL.md = front matter + docs/<body>.md, and
# skills/<name>/references/<topic>.md = docs/<topic>.md. Links to notes bundled with
# the skill become relative paths; other notes stay blender://docs/<topic> resources.
SKILLS = {
    "blender-mcp": {
        "body": "efficiency",
        "references": ["workflow", "selection", "modifiers", "materials", "troubleshooting"],
        "description": (
            "Work efficiently in Blender through the blender-mcp tools: the build/verify "
            "loop, token-cheap checks (numbers before pictures, small renders), "
            "selection rules that avoid wasted edits, polygon budgets and LODs. Use for "
            "any modelling, scene, material, render or export task with the blender-mcp "
            "server, and load it before the first Blender tool call of a session."
        ),
    },
    "game-character": {
        "body": "game-character",
        "references": ["character", "character-highpoly", "rigging"],
        "description": (
            "Model rig-ready characters for games and animation with the blender-mcp "
            "tools: low poly (box-modelled from a front/side reference sheet) or high "
            "poly (subdivision cage, high-to-low normal map baking), with correct bind "
            "pose, deforming topology, UVs and budgets; then rig, skin, pose-test, "
            "animate, add LODs and export for Unity, Unreal, Godot, Mixamo or film. Use "
            "for any character, creature, mascot or avatar request, and for questions "
            "about T/A-pose, edge loops, weights, bakes or character export."
        ),
    },
    "img2model": {
        "body": "img2model",
        "references": [],
        "description": (
            "Turn images (concept art, orthographic turnaround sheets, product photos, "
            "screenshots) into efficient 3D models in Blender with the blender-mcp "
            "tools: classify the input, write a shape inventory once, match reference "
            "planes or a camera, block out, compare silhouettes, refine to a polygon "
            "budget, colour, validate and export. Use whenever the user supplies an image "
            "and wants it modelled, whether it's a prop, vehicle, building or character."
        ),
    },
}
DOC_LINK = re.compile(r"blender://docs/([a-z0-9][a-z0-9-]*)")


def _linked(text: str, here: str, name: str) -> str:
    """Point blender://docs/<topic> at the bundled file when this skill carries it."""
    skill = SKILLS[name]
    bundled = {skill["body"]: "SKILL.md", **{t: f"references/{t}.md" for t in skill["references"]}}

    def repl(match: re.Match[str]) -> str:
        topic = match.group(1)
        if topic not in bundled:
            return match.group(0)
        target = bundled[topic]
        return os.path.relpath(target, os.path.dirname(here) or ".")

    return DOC_LINK.sub(repl, text)


def skill_files(name: str) -> dict[str, str]:
    skill = SKILLS[name]
    body = (DOCS / f"{skill['body']}.md").read_text()
    footer = (
        "\n---\n\nLinks like `blender://docs/<topic>` are resources of the blender-mcp "
        "server (read them with your MCP resource tool). The same notes ship as skills: "
        + ", ".join(
            f"`{other}` ({', '.join([s['body'], *s['references']])})"
            for other, s in SKILLS.items()
            if other != name
        )
        + ".\n"
    )
    files = {
        "SKILL.md": f"---\nname: {name}\ndescription: {skill['description']}\n---\n\n"
        + _linked(body, "SKILL.md", name)
        + footer
    }
    for topic in skill["references"]:
        path = f"references/{topic}.md"
        files[path] = _linked((DOCS / f"{topic}.md").read_text(), path, name)
    return files


# Generated skills that were renamed or merged away; sync deletes these. Every other
# folder in skills/ (e.g. the hand-written roblox-avatar) is left alone.
RETIRED_SKILLS = {"lowpoly-character"}


def sync_skills() -> None:
    for old in RETIRED_SKILLS:
        if (SKILLS_DIR / old).is_dir():
            shutil.rmtree(SKILLS_DIR / old)
            print(f"removed {(SKILLS_DIR / old).relative_to(ROOT)}")
    for name in SKILLS:
        folder = SKILLS_DIR / name
        if folder.exists():
            shutil.rmtree(folder)
        for rel, text in skill_files(name).items():
            out = folder / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
        print(f"synced {folder.relative_to(ROOT)}")


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
