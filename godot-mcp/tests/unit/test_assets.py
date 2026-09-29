"""import_asset only reads files inside the allowed asset folders."""

import os

import pytest

from godot_mcp.tools._common import ToolError
from godot_mcp.tools.assets import asset_dirs, read_asset


@pytest.fixture
def allowed(tmp_path, monkeypatch):
    folder = tmp_path / "assets"
    folder.mkdir()
    (folder / "hero.png").write_bytes(b"png")
    monkeypatch.setenv("GODOT_MCP_ASSET_DIRS", str(folder))
    return folder


def test_reads_inside_the_allowed_folder(allowed):
    assert read_asset(str(allowed / "hero.png")) == b"png"
    assert read_asset("hero.png") == b"png"  # relative to the first allowed folder


def test_refuses_everything_else(allowed, tmp_path):
    (tmp_path / "secret.txt").write_text("nope")
    for bad in (str(tmp_path / "secret.txt"), "../secret.txt", "/etc/passwd"):
        with pytest.raises(ToolError, match="outside the folders"):
            read_asset(bad)
    (allowed / "link.png").symlink_to(tmp_path / "secret.txt")
    with pytest.raises(ToolError, match="outside the folders"):
        read_asset("link.png")  # a symlink out of the folder
    with pytest.raises(ToolError, match="No file"):
        read_asset("missing.png")


def test_default_is_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("GODOT_MCP_ASSET_DIRS", raising=False)
    monkeypatch.chdir(tmp_path)
    assert asset_dirs() == [tmp_path.resolve()]
    monkeypatch.setenv("GODOT_MCP_ASSET_DIRS", os.pathsep.join(["/a", "/b"]))
    assert [str(d) for d in asset_dirs()] == ["/a", "/b"]
