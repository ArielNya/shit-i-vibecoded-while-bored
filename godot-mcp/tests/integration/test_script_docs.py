"""M1: reading scripts, LSP diagnostics, API docs; screenshots refuse in headless mode."""

import pytest

pytestmark = pytest.mark.anyio


async def test_read_script(call):
    res = await call("read_script", path="res://scripts/player.gd", start_line=1, end_line=2)
    assert res["text"] == "1| class_name Player\n2| extends CharacterBody2D"
    assert res["total_lines"] == 24 and res["class_name"] == "Player"
    tail = await call("read_script", path="scripts/player.gd", start_line=23)
    assert tail["text"].startswith("23| ") and tail["end_line"] == 24
    scene = await call("read_script", path="res://scenes/level.tscn")
    assert "CSGBox3D" in scene["text"]


async def test_read_script_errors(call_error):
    assert "No file" in await call_error("read_script", path="res://scripts/nope.gd")
    assert "not a text file" in await call_error("read_script", path="res://icon.svg")
    assert "not an allowed project path" in await call_error("read_script", path="../../etc/passwd")


async def test_project_diagnostics(call):
    res = await call("get_diagnostics")
    files = {f["path"]: f for f in res["files"]}
    broken = files["res://scripts/broken.gd"]
    assert any("undefined_helper" in e for e in broken["errors"])
    assert any(e.startswith("4:") and "String" in e for e in broken["errors"])
    assert any("UNUSED_VARIABLE" in w for w in files["res://scripts/warns.gd"]["warnings"])
    assert "res://scripts/player.gd" not in files  # clean
    assert not any(p.startswith("res://ignored") for p in files)
    assert res["error_count"] >= 2 and res["warning_count"] >= 1
    assert res["files_checked"] >= 4


async def test_diagnostics_single_file_and_options(call, call_error):
    clean = await call("get_diagnostics", path="res://scripts/player.gd")
    assert clean == {"files_checked": 1, "error_count": 0, "warning_count": 0, "files": []}
    no_warn = await call("get_diagnostics", path="res://scripts/warns.gd", include_warnings=False)
    assert no_warn["files"] == [] and no_warn["warning_count"] == 1
    # Asking twice re-analyses the file rather than returning a stale result.
    again = await call("get_diagnostics", path="res://scripts/broken.gd")
    assert again["error_count"] >= 2
    assert "No GDScript file" in await call_error("get_diagnostics", path="res://scripts/nope.gd")


async def test_class_docs_native(call):
    docs = await call("get_class_docs", class_name="CharacterBody2D")
    assert docs["kind"] == "native"
    assert docs["inherits"][:2] == ["PhysicsBody2D", "CollisionObject2D"]
    assert "move_and_slide() -> bool" in docs["methods"]
    assert "set_velocity" not in " ".join(docs["methods"])  # accessors fold into properties
    assert "velocity: Vector2 = Vector2(0, 0)" in docs["properties"]
    assert "motion_mode: CharacterBody2D.MotionMode = 0" in docs["properties"]
    assert docs["enums"]["MotionMode"] == ["MOTION_MODE_GROUNDED = 0", "MOTION_MODE_FLOATING = 1"]
    assert "character" in docs["description"].lower()

    node = await call("get_class_docs", class_name="Node")
    assert any(v.startswith("_ready()") for v in node["virtual_methods"])
    assert any(s.startswith("tree_entered") for s in node["signals"])


async def test_class_docs_members(call):
    velocity = await call("get_class_docs", class_name="CharacterBody2D", member="velocity")
    assert velocity["declared_in"] == "CharacterBody2D"
    assert "pixels per second" in velocity["description"]
    assert "[member" not in velocity["description"]  # BBCode converted
    inherited = await call("get_class_docs", class_name="CharacterBody2D", member="add_child")
    assert inherited["declared_in"] == "Node"
    assert inherited["signature"].startswith("func Node.add_child(")


async def test_class_docs_project_class(call):
    docs = await call("get_class_docs", class_name="Player")
    assert docs["kind"] == "script" and docs["path"] == "res://scripts/player.gd"
    assert "@export speed: float = 200.0" in docs["properties"]
    assert "hurt() -> void" in docs["methods"]
    assert docs["signals"] == ["died(cause: String)"]
    assert docs["constants"] == {"JUMP_VELOCITY": -400.0}
    assert docs["inherits"][0] == "CharacterBody2D"
    member = await call("get_class_docs", class_name="Player", member="hurt")
    assert member["signatures"] == ["hurt() -> void"]


async def test_class_docs_errors(call_error):
    assert "CharacterBody2D" in await call_error("get_class_docs", class_name="KinematicBody2D")
    assert "Did you mean" in await call_error("get_class_docs", class_name="Sprite2d")
    assert "no member 'fly'" in await call_error(
        "get_class_docs", class_name="CharacterBody2D", member="fly"
    )


async def test_search_docs(call):
    res = await call("search_docs", query="move slide")
    hits = {(r.get("class"), r["name"]) for r in res["results"]}
    assert ("CharacterBody2D", "move_and_slide") in hits
    # Words may name the class too (what Claude tried first in the smoke test).
    scoped = await call("search_docs", query="move slide CharacterBody2D")
    assert (scoped["results"][0]["class"], scoped["results"][0]["name"]) == (
        "CharacterBody2D",
        "move_and_slide",
    )
    classes = await call("search_docs", query="raycast")
    names = [r["name"] for r in classes["results"] if r["kind"] == "class"]
    assert "RayCast2D" in names and "RayCast3D" in names
    project = await call("search_docs", query="player")
    assert {"kind": "class", "name": "Player"} in project["results"]
    empty = await call("search_docs", query="zzzqqq")
    assert empty["results"] == [] and "hint" in empty


async def test_screenshot_needs_a_window(call_error):
    assert "headless" in await call_error("get_editor_screenshot")


async def test_hidden_and_symlinked_files_are_off_limits(call, call_error, project_dir, tmp_path):
    # Godot keeps export keystore passwords in .godot/export_credentials.cfg.
    secret_cfg = project_dir / ".godot" / "export_credentials.cfg"
    secret_cfg.write_text('[preset.0]\npassword="HUNTER2_SECRET"\n')
    assert "not an allowed" in await call_error(
        "read_script", path="res://.godot/export_credentials.cfg"
    )
    assert "not an allowed" in await call_error("search_files", query="x", path="res://.godot")
    # A symlink inside the project must not lead outside it.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.gd").write_text(
        "# HUNTER2_SECRET\nextends Node\nfunc broken(:\n"
    )  # would show up in diagnostics
    (project_dir / "linked").symlink_to(outside, target_is_directory=True)
    try:
        assert "not an allowed" in await call_error("read_script", path="res://linked/leak.gd")
        found = await call("search_files", query="HUNTER2_SECRET")
        assert found["matches"] == []
        diags = await call("get_diagnostics")
        assert not any(f["path"].startswith("res://linked") for f in diags["files"])
    finally:
        (project_dir / "linked").unlink()
