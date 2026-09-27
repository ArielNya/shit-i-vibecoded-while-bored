"""The version lives in several places; they must agree."""

import ast
import tomllib
from pathlib import Path

import blender_mcp

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addon" / "blender_mcp_addon"


def test_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    manifest = tomllib.loads((ADDON / "blender_manifest.toml").read_text())["version"]
    tree = ast.parse((ADDON / "__init__.py").read_text())
    bl_info = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and node.targets[0].id == "bl_info"
    )
    addon = ".".join(str(part) for part in bl_info["version"])
    assert project == blender_mcp.__version__ == manifest == addon
