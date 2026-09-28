import shutil
from pathlib import Path

from roblox_mcp.tools.project import TOOLCHAIN, project_info

SAMPLE = Path(__file__).parent.parent / "fixtures" / "sample_game"


def test_rojo_project_is_summarized():
    info = project_info(SAMPLE)
    assert info["mode"] == "rojo" and info["name"] == "sample_game"
    assert info["tree"] == {
        "ReplicatedStorage": {"children": {"Shared": {"path": "src/shared"}}},
        "ServerScriptService": {"children": {"Server": {"path": "src/server"}}},
    }
    assert set(info["toolchain"]) == set(TOOLCHAIN)


def test_studio_mode_without_project_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBLOX_API_KEY", "secret")
    info = project_info(tmp_path)
    assert info["mode"] == "studio" and "tree" not in info
    assert info["open_cloud"]["api_key"] is True
    assert "secret" not in str(info)  # the key itself is never returned


def test_broken_project_file_is_reported(tmp_path):
    shutil.copy(SAMPLE / "default.project.json", tmp_path / "game.project.json")
    (tmp_path / "game.project.json").write_text("{nope")
    info = project_info(tmp_path)
    assert info["mode"] == "rojo" and "can't read game.project.json" in info["project_error"]
