"""Parsing and path logic of the toolchain tools, without the tools."""

import json
from pathlib import Path

import pytest

from roblox_mcp import toolchain
from roblox_mcp.tools import code, project

SAMPLE = Path(__file__).parent.parent / "fixtures" / "sample_game"


def test_luau_lsp_plain_lines():
    type_error = ("/abs/game/src/server/A.luau [game/ServerScriptService/Server/A]:3:19-25: "
                  "(W0) TypeError: Expected this to be 'number', but got 'string'")  # fmt: skip
    lint = "src/server/A.luau:4:1-4: (W0) DeprecatedApi: Function 'wait' is deprecated"
    m = code.PLAIN.match(type_error)
    assert (m["path"], m["line"], m["col"], m["code"]) == (
        "/abs/game/src/server/A.luau",
        "3",
        "19",
        "TypeError",
    )
    m = code.PLAIN.match(lint)
    assert (m["path"], m["code"]) == ("src/server/A.luau", "DeprecatedApi")


def test_default_targets_are_the_synced_folders():
    assert code.targets(SAMPLE, "") == ["src/shared", "src/server"]
    assert code.targets(SAMPLE, "src/server, src/shared/Damage.luau") == [
        "src/server",
        "src/shared/Damage.luau",
    ]
    with pytest.raises(ValueError, match="outside the project"):
        code.targets(SAMPLE, "../../..")


def test_rojo_reply_parsing():
    reply = (b"\x8a\xa9sessionId\xd9\x24" + b"8" * 36 + b"\xadserverVersion\xa57.7.0"
             b"\xabprojectName\xabsample_game")  # fmt: skip
    assert project.msgpack_str(reply, "serverVersion") == "7.7.0"
    assert project.msgpack_str(reply, "projectName") == "sample_game"
    assert project.msgpack_str(reply, "sessionId") == "8" * 36
    assert project.msgpack_str(reply, "placeId") is None


def test_template_follows_the_recommended_structure(tmp_path):
    result = project.create_project(tmp_path, "")
    assert "default.project.json" in result["created"] and result["kept_existing"] == []
    spec = json.loads((tmp_path / "default.project.json").read_text())
    assert spec["name"] == tmp_path.name and spec["emitLegacyScripts"] is False
    assert spec["tree"]["ReplicatedStorage"]["Client"] == {"$path": "src/client"}
    assert "Workspace" not in spec["tree"]  # the world stays in the place
    rokit = (tmp_path / "rokit.toml").read_text()
    assert all(f'{tool} = "{pin}"' in rokit for tool, pin in toolchain.PINS.items())
    # never overwrites
    (tmp_path / ".luaurc").write_text("mine")
    again = project.create_project(tmp_path, "other")
    assert again["created"] == [] and (tmp_path / ".luaurc").read_text() == "mine"


def test_existing_project_file_is_kept(tmp_path):
    (tmp_path / "game.project.json").write_text("{}")
    result = project.create_project(tmp_path, "")
    assert "game.project.json" in result["kept_existing"]
    assert not (tmp_path / "default.project.json").exists()


def test_missing_tool_says_how_to_install(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv(toolchain.BIN_DIR_ENV, str(tmp_path))
    with pytest.raises(toolchain.Missing, match="rokit install"):
        toolchain.run("rojo", ["--version"], tmp_path)
    (tmp_path / "rojo").write_text("#!/bin/sh\necho Rojo 9\n")
    (tmp_path / "rojo").chmod(0o755)
    assert toolchain.run("rojo", [], tmp_path).stdout == "Rojo 9\n"


def test_definitions_are_unpacked_once():
    path = toolchain.definitions_path()
    assert path.read_text().startswith("--#METADATA#") and toolchain.definitions_path() == path


def test_build_refuses_bad_outputs(tmp_path):
    project.create_project(tmp_path, "")
    with pytest.raises(ValueError, match="outside"):
        project.build(tmp_path, "../x.rbxl")
    with pytest.raises(ValueError, match="must end in"):
        project.build(tmp_path, "build/x.zip")
