"""M0/M1: connection, project overview, files, search, settings, input map."""

import pytest

pytestmark = pytest.mark.anyio


async def test_ping_reports_versions_and_lsp(call, editor):
    info = await call("ping")
    assert info["connected"] and info["pong"]
    assert info["godot_version"].startswith("4.")
    assert info["editor_ready"] is True
    assert info["lsp"]["port"] == editor["lsp_port"]
    assert info["project_path"].rstrip("/").endswith("demo project")
    assert info["headless"] is True


async def test_project_info(call):
    info = await call("get_project_info")
    assert info["name"] == "MCP Demo"
    assert info["main_scene"] == "res://scenes/main.tscn"
    assert info["autoloads"] == {"GameState": "res://scripts/game_state.gd"}
    assert info["uses_csharp"] is False
    assert info["file_counts"]["scene"] == 3
    assert info["window"]["viewport_size"] == "640x360"
    assert info["editor"]["edited_scene"] == "res://scenes/main.tscn"
    assert info["editor"]["edited_scene_root_type"] == "Node2D"
    assert "res://addons/godot_mcp/plugin.cfg" in info["enabled_plugins"]


async def test_list_files_by_kind_and_class(call):
    scenes = await call("list_files", type="scene")
    assert sorted(f["path"] for f in scenes["files"]) == [
        "res://scenes/level.tscn",
        "res://scenes/main.tscn",
        "res://scenes/player.tscn",
    ]
    scripts = await call("list_files", path="res://scripts", type="script")
    by_path = {f["path"]: f for f in scripts["files"]}
    assert by_path["res://scripts/player.gd"]["class_name"] == "Player"
    textures = await call("list_files", type="Texture2D")
    assert [f["path"] for f in textures["files"]] == ["res://icon.svg"]


async def test_list_files_skips_gdignore_and_paginates(call):
    everything = await call("list_files", limit=1000)
    assert not any(f["path"].startswith("res://ignored") for f in everything["files"])
    first = await call("list_files", limit=2)
    assert len(first["files"]) == 2 and first["next_offset"] == 2
    second = await call("list_files", limit=2, offset=2)
    assert second["files"][0] == everything["files"][2]
    top = await call("list_files", recursive=False)
    assert "res://scenes" in top["folders"]
    assert all(f["path"].count("/") == 2 for f in top["files"])  # res://<file>


async def test_list_files_rejects_escaping_paths(call_error):
    assert "not an allowed project path" in await call_error("list_files", path="res://../etc")
    assert "No folder" in await call_error("list_files", path="res://nope")


async def test_search_files(call):
    found = await call("search_files", query="magic_search_marker")
    assert [(m["path"], m["line"]) for m in found["matches"]] == [
        ("res://scripts/game_state.gd", 2)
    ]  # the copy under ignored/ (.gdignore) is not searched
    regex = await call("search_files", query=r"func \w+\(\) -> void", regex=True)
    assert {m["path"] for m in regex["matches"]} >= {"res://scripts/player.gd"}
    only_scenes = await call("search_files", query="Player", extensions=["tscn"])
    assert all(m["path"].endswith(".tscn") for m in only_scenes["matches"])
    exact_case = await call("search_files", query="magic_search_marker", case_sensitive=True)
    assert exact_case["matches"] == []


async def test_get_project_settings(call):
    changed = await call("get_project_settings")
    names = {s["name"]: s for s in changed["settings"]}
    assert names["application/config/name"]["value"] == "MCP Demo"
    assert "physics/2d/default_gravity" not in names  # untouched default
    section = await call("get_project_settings", prefix="display/window/size/", changed_only=False)
    by_name = {s["name"]: s for s in section["settings"]}
    assert by_name["display/window/size/viewport_width"] == {
        "name": "display/window/size/viewport_width",
        "type": "int",
        "value": 640,
    }
    assert "display/window/size/mode" in by_name


async def test_set_project_setting_types_and_saving(call, project_dir):
    res = await call("set_project_setting", name="display/window/size/viewport_width", value="800")
    assert res == {"name": "display/window/size/viewport_width", "value": 800, "previous": 640}
    assert "window/size/viewport_width=800" in (project_dir / "project.godot").read_text()

    # A number given for a text setting stays text.
    res = await call("set_project_setting", name="application/config/version", value="123")
    assert res["value"] == "123"

    color = await call(
        "set_project_setting",
        name="rendering/environment/defaults/default_clear_color",
        value="#336699",
    )
    assert color["value"].startswith("Color(0.2, 0.4, 0.6")

    reset = await call(
        "set_project_setting", name="display/window/size/viewport_width", value="null"
    )
    assert reset["value"] == 1152  # engine default


async def test_set_project_setting_refuses_protected_and_bad_values(call_error):
    assert "can't be changed" in await call_error(
        "set_project_setting", name="editor_plugins/enabled", value="[]"
    )
    assert "can't convert" in await call_error(
        "set_project_setting", name="display/window/size/viewport_width", value="Vector2(1, 2)"
    )
    # Literals are parsed only as the setting's own type, never as objects.
    message = await call_error(
        "set_project_setting", name="physics/2d/default_gravity_vector", value="Object(Node)"
    )
    assert "Vector2" in message


async def test_autoloads(call):
    await call("set_project_setting", name="autoload/Extra", value="res://scripts/game_state.gd")
    info = await call("get_project_info")
    assert info["autoloads"]["Extra"] == "res://scripts/game_state.gd"
    removed = await call("set_project_setting", name="autoload/Extra", value="")
    assert removed["removed"] is True
    assert "Extra" not in (await call("get_project_info"))["autoloads"]


async def test_input_map_roundtrip(call, project_dir):
    created = await call(
        "edit_input_map",
        action="jump",
        add_events=[{"type": "key", "key": "Space"}, {"type": "joypad_button", "button": "a"}],
    )
    assert created["created"] is True
    assert [e["type"] for e in created["events"]] == ["key", "joypad_button"]
    assert created["events"][0]["key"] == "Space"
    assert "jump={" in (project_dir / "project.godot").read_text()

    # Adding the same event twice is a no-op; modifiers are kept.
    changed = await call(
        "edit_input_map",
        action="jump",
        add_events=[{"type": "key", "key": "Space"}, {"type": "key", "key": "W", "ctrl": True}],
        remove_events=[{"type": "joypad_button", "button": "a"}],
        deadzone=0.5,
    )
    assert changed["deadzone"] == 0.5
    assert [(e["key"], e.get("ctrl", False)) for e in changed["events"]] == [
        ("Space", False),
        ("W", True),
    ]

    listed = await call("get_input_map")
    assert set(listed["actions"]) == {"jump"}
    assert "ui_accept" in (await call("get_input_map", include_builtin=True))["actions"]

    assert (await call("get_project_info"))["input_actions"] == ["jump"]
    await call("edit_input_map", action="jump", remove_action=True)
    assert (await call("get_input_map"))["actions"] == {}


async def test_input_map_errors(call_error):
    assert "unknown key" in await call_error(
        "edit_input_map", action="x", add_events=[{"type": "key", "key": "NotAKey"}]
    )
    assert "unknown event type" in await call_error(
        "edit_input_map", action="x", add_events=[{"type": "gesture"}]
    )
    assert "can't be removed" in await call_error(
        "edit_input_map", action="ui_accept", remove_action=True
    )
