"""M2: writing scripts, attaching them, and navigating code via the language server."""

import pytest

pytestmark = pytest.mark.anyio

ENEMY = """class_name Enemy
extends CharacterBody2D

signal defeated

@export var speed := 80.0
var health := 3


func take_damage(amount: int) -> void:
\thealth -= amount
\tif health <= 0:
\t\tdefeated.emit()
"""


async def test_write_and_edit_script(call, call_error, project_dir):
    written = await call("write_script", path="res://enemies/enemy.gd", content=ENEMY)
    assert written["created"] is True and written["errors"] == []
    assert (project_dir / "enemies" / "enemy.gd").read_text() == ENEMY

    # The new class_name is registered: it shows up as a project class right away.
    docs = await call("get_class_docs", class_name="Enemy")
    assert "take_damage(amount: int) -> void" in docs["methods"]

    edited = await call(
        "edit_script",
        path="res://enemies/enemy.gd",
        old_text="\thealth -= amount\n",
        new_text="\thealth -= amount * 2\n",
    )
    assert edited["replacements"] == 1 and edited["errors"] == []
    assert "health -= amount * 2" in (project_dir / "enemies" / "enemy.gd").read_text()

    broken = await call(
        "edit_script",
        path="res://enemies/enemy.gd",
        old_text="defeated.emit()",
        new_text="defeated.emit(undefined_thing)",
    )
    assert any("undefined_thing" in e for e in broken["errors"])  # fresh diagnostics

    assert "not found" in await call_error(
        "edit_script", path="res://enemies/enemy.gd", old_text="no such text", new_text="x"
    )
    assert "indentation" in await call_error(
        "edit_script", path="res://enemies/enemy.gd", old_text="    health -= amount", new_text="x"
    )
    assert "occurs 3 times" in await call_error(
        "edit_script", path="res://enemies/enemy.gd", old_text="health", new_text="hp"
    )
    everything = await call(
        "edit_script",
        path="res://enemies/enemy.gd",
        old_text="health",
        new_text="hp",
        replace_all=True,
    )
    assert everything["replacements"] >= 3


async def test_write_guards(call_error):
    assert "only gd, cs" in await call_error(
        "write_script", path="res://scenes/main.tscn", content="x"
    )
    assert "plugin's own files" in await call_error(
        "write_script", path="res://addons/godot_mcp/plugin.gd", content="x"
    )
    assert "not an allowed" in await call_error(
        "write_script", path="res://.godot/evil.gd", content="x"
    )
    assert "No file" in await call_error(
        "edit_script", path="res://nope.gd", old_text="a", new_text="b"
    )


async def test_create_attach_detach(call, call_error, project_dir):
    created = await call(
        "create_script",
        path="res://scripts/mover.gd",
        extends="CharacterBody2D",
        class_name="Mover",
    )
    assert created["errors"] == []
    text = (project_dir / "scripts" / "mover.gd").read_text()
    assert text.startswith("class_name Mover\nextends CharacterBody2D\n")
    assert "func _physics_process(delta: float) -> void:" in text  # physics body template

    assert "already exists" in await call_error(
        "create_script", path="res://scripts/mover.gd", extends="Node"
    )
    assert "already exists" in await call_error(
        "create_script", path="res://scripts/other.gd", class_name="Player"
    )
    assert "Unknown base class" in await call_error(
        "create_script", path="res://scripts/x.gd", extends="KinematicBody2D"
    )

    await call("new_scene", path="res://t/scripted.tscn", root_type="Node2D")
    await call("add_node", type="CharacterBody2D", name="Body")
    await call("add_node", type="Sprite2D", name="Pic")
    attached = await call("attach_script", node="Body", path="res://scripts/mover.gd")
    assert attached == {"node": "Body", "script": "res://scripts/mover.gd"}
    tree = {n["path"]: n for n in (await call("get_scene_tree"))["nodes"]}
    assert tree["Body"]["type"] == "Mover"
    assert "extends CharacterBody2D" in await call_error(
        "attach_script", node="Pic", path="res://scripts/mover.gd"
    )
    # create + attach in one go
    both = await call(
        "create_script", path="res://scripts/pic.gd", extends="Sprite2D", attach_to="Pic"
    )
    assert both["attached_to"] == "Pic"
    detached = await call("detach_script", node="Body")
    assert detached["detached"] == "res://scripts/mover.gd"
    await call("undo")
    assert {n["path"]: n for n in (await call("get_scene_tree"))["nodes"]}["Body"]["type"] == (
        "Mover"
    )
    await call("save_scene")
    assert 'path="res://scripts/mover.gd"' in (project_dir / "t" / "scripted.tscn").read_text()


async def test_navigation(call, call_error):
    await call(
        "write_script",
        path="res://scripts/uses_player.gd",
        content=(
            "extends Node\n\n\nfunc _ready() -> void:\n"
            "\tvar p := Player.new()\n\tp.hurt()\n\tprint(p.lives)\n"
        ),
    )
    found = await call("find_symbol", name="hurt")
    assert {
        "name": "hurt",
        "kind": "method",
        "detail": "func hurt() -> void",
        "path": "res://scripts/player.gd",
        "line": 21,
    } in found["results"]
    signals = await call("find_symbol", name="died", kind="signal")
    assert [r["path"] for r in signals["results"]] == ["res://scripts/player.gd"]

    definition = await call(
        "get_definition", path="res://scripts/uses_player.gd", line=6, symbol="hurt"
    )
    assert definition["definitions"][0]["path"] == "res://scripts/player.gd"
    assert definition["definitions"][0]["line"] == 21
    assert "func hurt()" in definition["definitions"][0]["text"]

    refs = await call("get_references", path="res://scripts/player.gd", line=21, symbol="hurt")
    where = {(r["path"], r["line"]) for r in refs["references"]}
    assert ("res://scripts/uses_player.gd", 6) in where
    assert ("res://scripts/player.gd", 21) in where

    assert "not on line" in await call_error(
        "get_definition", path="res://scripts/uses_player.gd", line=1, symbol="hurt"
    )


async def test_unsaved_editor_buffer_is_protected(call, call_error, bridge, project_dir):
    await call("write_script", path="res://scripts/human.gd", content="extends Node\n")
    state = await bridge.call("_test_make_unsaved", {"path": "res://scripts/human.gd"})
    assert "res://scripts/human.gd" in state["unsaved"]
    message = await call_error(
        "write_script", path="res://scripts/human.gd", content="extends Node2D\n"
    )
    assert "unsaved changes in Godot's script editor" in message
    assert "unsaved changes" in await call_error(
        "edit_script", path="res://scripts/human.gd", old_text="Node", new_text="Node2D"
    )
    assert (project_dir / "scripts" / "human.gd").read_text() == "extends Node\n"
    forced = await call(
        "write_script", path="res://scripts/human.gd", content="extends Node2D\n", force=True
    )
    assert forced["errors"] == []
