"""M1: scene tree and node properties, for the edited scene and scenes on disk."""

import pytest

pytestmark = pytest.mark.anyio


async def test_edited_scene_tree(call):
    tree = await call("get_scene_tree")
    assert tree["scene"] == "res://scenes/main.tscn"
    assert tree["source"] == "editor"
    nodes = {n["path"]: n for n in tree["nodes"]}
    assert list(nodes) == [".", "Player", "Background", "HUD", "HUD/Score"]
    player = nodes["Player"]
    assert player["type"] == "Player"  # class_name wins over the native type
    assert player["native_type"] == "CharacterBody2D"
    assert player["instance_of"] == "res://scenes/player.tscn"
    assert player["script"] == "res://scripts/player.gd"
    assert player["groups"] == ["players"]
    assert nodes["Background"]["visible"] is False
    assert nodes["Background"]["groups"] == ["decor"]


async def test_scene_tree_options(call):
    internal = await call("get_scene_tree", include_internal=True)
    assert "Player/CollisionShape2D" in [n["path"] for n in internal["nodes"]]

    shallow = await call("get_scene_tree", max_depth=0)
    assert shallow["nodes"] == [{"path": ".", "type": "Node2D", "children_not_shown": 3}]

    sub = await call("get_scene_tree", node="HUD")
    assert [n["path"] for n in sub["nodes"]] == ["HUD", "HUD/Score"]

    capped = await call("get_scene_tree", max_nodes=2)
    assert capped["truncated"] is True and len(capped["nodes"]) == 2


async def test_scene_from_disk(call):
    tree = await call("get_scene_tree", scene="scenes/player.tscn")
    assert tree["source"] == "file"
    assert [n["path"] for n in tree["nodes"]] == [".", "Sprite2D", "CollisionShape2D"]
    level = await call("get_scene_tree", scene="res://scenes/level.tscn")
    assert level["root_type"] == "Node3D"


async def test_node_properties(call):
    player = await call("get_node_properties", node="Player")
    props = {p["name"]: p for p in player["properties"]}
    assert props["position"]["value"] == "Vector2(100, 200)"
    assert props["position"]["type"] == "Vector2"
    assert props["speed"]["value"] == 250.0
    assert props["script"]["value"] == {
        "_type": "Resource",
        "class": "GDScript",
        "path": "res://scripts/player.gd",
    }
    assert "floor_max_angle" not in props  # still at its default
    assert player["default_values_hidden"] > 10

    everything = await call("get_node_properties", node="Player", include_defaults=True)
    all_props = {p["name"]: p for p in everything["properties"]}
    assert all_props["up_direction"]["value"] == "Vector2(0, -1)"
    assert all_props["motion_mode"]["options"].startswith("Grounded")

    filtered = await call(
        "get_node_properties", node="Player", filter="floor", include_defaults=True
    )
    assert filtered["properties"] and all("floor" in p["name"] for p in filtered["properties"])


async def test_node_properties_types(call):
    bg = await call("get_node_properties", node="Background")
    props = {p["name"]: p["value"] for p in bg["properties"]}
    assert props["visible"] is False
    assert props["modulate"] == "Color(1, 0, 0, 1)"
    assert props["texture"]["path"] == "res://icon.svg"

    shape = await call("get_node_properties", node="CollisionShape2D", scene="scenes/player.tscn")
    value = {p["name"]: p["value"] for p in shape["properties"]}["shape"]
    assert value == {"_type": "Resource", "class": "RectangleShape2D", "embedded": True}

    root = await call("get_node_properties", node=".")
    assert root["node"] == "." and root["type"] == "Node2D"


async def test_scene_errors(call_error):
    assert "No node 'Nope'" in await call_error("get_node_properties", node="Nope")
    assert "No scene at" in await call_error("get_scene_tree", scene="res://missing.tscn")
    assert "not an allowed project path" in await call_error(
        "get_scene_tree", scene="res://../x.tscn"
    )
    assert "is not a scene" in await call_error("get_scene_tree", scene="res://icon.svg")
