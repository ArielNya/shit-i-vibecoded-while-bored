"""Install the pinned toolchain (roblox_mcp.toolchain.PINS) for Linux x86_64 into a folder.

    uv run python scripts/install_toolchain.py ~/.cache/roblox-mcp/bin

For CI and cloud sessions. Downloads release assets directly instead of using rokit,
which needs the GitHub API (blocked in some sandboxes). Skips tools already at the
pinned version. On a dev machine, use rokit with the game's rokit.toml instead."""

import io
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from roblox_mcp.toolchain import PINS

# tool -> (release tag, Linux x86_64 asset), both formatted with the version
LINUX = {
    "rojo": ("v{v}", "rojo-{v}-linux-x86_64.zip"),
    "luau-lsp": ("{v}", "luau-lsp-linux-x86_64.zip"),
    "stylua": ("v{v}", "stylua-linux-x86_64.zip"),
    "lune": ("v{v}", "lune-{v}-linux-x86_64.zip"),
}


def installed_version(exe: Path) -> str:
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
    except OSError:
        return ""


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1]).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    for name, pin in PINS.items():
        repo, version = pin.split("@")
        exe = dest / name
        if version in installed_version(exe):
            continue
        tag, asset = (s.format(v=version) for s in LINUX[name])
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
        print(f"install_toolchain: {name} {version}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=120) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        exe.write_bytes(archive.read(name))
        exe.chmod(0o755)
    return 0


if __name__ == "__main__":
    sys.exit(main())
