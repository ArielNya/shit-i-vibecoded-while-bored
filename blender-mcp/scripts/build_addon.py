"""Sync the vendored protocol module into the add-on and zip it for installation.

python scripts/build_addon.py            # sync + write dist/blender_mcp_addon-<version>.zip
python scripts/build_addon.py --sync     # only copy protocol.py into the add-on
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
    parser.add_argument("--sync", action="store_true", help="only sync protocol.py")
    args = parser.parse_args()
    sync_protocol()
    if not args.sync:
        build_zip()


if __name__ == "__main__":
    main()
