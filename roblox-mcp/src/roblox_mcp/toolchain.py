"""The CLIs roblox-mcp shells out to: pinned versions, finding them, running them."""

from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Versions verified with this release. init_project writes them into the game's
# rokit.toml; scripts/install_toolchain.py installs them on Linux (CI, cloud sessions).
PINS = {
    "rojo": "rojo-rbx/rojo@7.7.0",
    "luau-lsp": "JohnnyMorganz/luau-lsp@1.70.1",
    "stylua": "JohnnyMorganz/StyLua@2.5.2",
    "lune": "lune-org/lune@0.10.5",
}

DATA = Path(__file__).resolve().parent / "data"
# Roblox type definitions for luau-lsp 1.70.1 at the lowest script security level, so
# plugin-only APIs are errors in game code. From the luau-lsp repo, scripts/.
DEFINITIONS = DATA / "globalTypes.None.d.luau.gz"
BIN_DIR_ENV = "ROBLOX_MCP_BIN_DIR"


def find(name: str) -> str | None:
    """A tool from ROBLOX_MCP_BIN_DIR first, then PATH (and rokit's shims on PATH)."""
    bin_dir = os.environ.get(BIN_DIR_ENV)
    if bin_dir:
        for candidate in (name, name + ".exe"):
            path = Path(bin_dir) / candidate
            if path.is_file():
                return str(path)
    return shutil.which(name)


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str


class Missing(Exception):
    def __init__(self, name: str):
        super().__init__(
            f"'{name}' isn't installed or not on PATH. Install the pinned toolchain with "
            f"rokit (`rokit install` in the game project) or put the binaries in "
            f"${BIN_DIR_ENV}."
        )


def run(name: str, args: list[str], cwd: Path, timeout: float = 120) -> Result:
    exe = find(name)
    if exe is None:
        raise Missing(name)
    out = subprocess.run(
        [exe, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )
    return Result(out.returncode, out.stdout, out.stderr)


def definitions_path() -> Path:
    """luau-lsp needs a plain file: unpack the bundled definitions once per content."""
    data = gzip.decompress(DEFINITIONS.read_bytes())
    path = (
        Path(tempfile.gettempdir())
        / "roblox-mcp"
        / (f"globalTypes.None-{hashlib.sha256(data).hexdigest()[:12]}.d.luau")
    )
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path
