"""M2: scene files, node structure, properties, signals, groups, branches, undo/redo."""

import pytest

pytestmark = pytest.mark.anyio


async def paths(call, **kw):
    return [n["path"] for n in (await call("get_scene_tree", **kw))["nodes"]]


async def test_new_open_save_close(call, call_error, project_dir):
    made = await call("new_scene", path="res://levels/arena.tscn", root_type="Node3D")
    assert made["scene"] == "res://levels/arena.tscn"
    assert made["root"] == "Arena" and made["root_type"] == "Node3D"
    assert (project_dir / "levels" / "arena.tscn").is_file()
    assert "already exists" in await call_error("new_scene", path="res://levels/arena.tscn")
    assert "unknown node type" in await call_error(
        "new_scene", path="res://x.tscn", root_type="Node3D2"
    )

    await call("add_node", type="Camera3D")
    info = await call("get_project_info")
    assert info["editor"]["edited_scene"] == "res://levels/arena.tscn"
    assert "unsaved changes" in await call_error("close_scene")
    saved = await call("save_scene")
    assert saved["saved"] == "res://levels/arena.tscn" and saved["unsaved"] is False
    assert 'type="Camera3D"' in (project_dir / "levels" / "arena.tscn").read_text()

    copy = await call("save_scene", path="res://levels/arena_copy.tscn")
    assert copy["saved"] == "res://levels/arena_copy.tscn"
    closed = await call("close_scene")
    assert closed["closed"] == "res://levels/arena_copy.tscn"

    opened = await call("open_scene", path="res://scenes/main.tscn")
    assert opened["root"] == "Main" and opened["node_count"] == 5


async def test_new_scene_errors(call_error):
    assert "not a Node type" in await call_error(
        "new_scene", path="res://bad.tscn", root_type="Resource"
    )
    assert "unknown node type" in await call_error(
        "new_scene", path="res://bad.tscn", root_type="KinematicBody2D"
    )
    assert "must end in .tscn" in await call_error("new_scene", path="res://bad.txt")


async def test_add_nodes_types_instances_and_properties(call, call_error):
    await call("new_scene", path="res://t/nodes.tscn", root_type="Node2D")
    sprite = await call(
        "add_node",
        type="Sprite2D",
        name="Hero",
        properties={"position": [10, 20], "texture": "res://icon.svg", "modulate": "#ff0000"},
    )
    assert sprite == {"path": "Hero", "type": "Sprite2D"}
    clash = await call("add_node", type="Node2D", name="Hero")
    assert clash["path"] != "Hero" and "note" in clash
    child = await call("add_node", parent="Hero", type="Label")
    assert child["path"] == "Hero/Label"
    player = await call("add_node", instance="res://scenes/player.tscn")
    assert player["type"] == "Player"
    project_class = await call("add_node", type="Player", name="Scripted")
    assert project_class["type"] == "Player"

    props = {
        p["name"]: p["value"]
        for p in (await call("get_node_properties", node="Hero"))["properties"]
    }
    assert props["position"] == "Vector2(10, 20)"
    assert props["modulate"] == "Color(1, 0, 0, 1)"
    assert props["texture"]["path"] == "res://icon.svg"

    tree = await paths(call)
    assert tree[:2] == [".", "Hero"] and "Hero/Label" in tree
    internal = await paths(call, include_internal=True)
    assert "Player/CollisionShape2D" in internal  # instance kept its own nodes

    assert "not a Node type" in await call_error("add_node", type="Texture2D")
    assert "has no property 'colour'" in await call_error(
        "add_node", type="Sprite2D", properties={"colour": 1}
    )
    assert "No node 'Nope'" in await call_error("add_node", parent="Nope", type="Node")
    assert "itself" in await call_error("add_node", instance="res://t/nodes.tscn")
    await call("save_scene")


async def test_set_node_properties(call, call_error, project_dir):
    await call("new_scene", path="res://t/props.tscn", root_type="Node2D")
    await call("add_node", type="CharacterBody2D", name="Body")
    await call("add_node", parent="Body", type="CollisionShape2D", name="Shape")
    res = await call(
        "set_node_properties",
        node="Body",
        properties={"motion_mode": "Floating", "position": "Vector2(5, 6)", "velocity": [1, 2]},
    )
    assert res["values"] == {
        "motion_mode": 1,
        "position": "Vector2(5, 6)",
        "velocity": "Vector2(1, 2)",
    }
    shape = await call(
        "set_node_properties",
        node="Body/Shape",
        properties={
            "shape": {
                "_type": "Resource",
                "class": "RectangleShape2D",
                "properties": {"size": "Vector2(32, 48)"},
            }
        },
    )
    assert shape["values"]["shape"] == {
        "_type": "Resource",
        "class": "RectangleShape2D",
        "embedded": True,
    }
    # All-or-nothing: one bad value means nothing changes.
    message = await call_error(
        "set_node_properties",
        node="Body",
        properties={"position": "Vector2(9, 9)", "motion_mode": "Sideways"},
    )
    assert "Nothing was changed" in message and "Sideways" in message
    now = {
        p["name"]: p["value"]
        for p in (await call("get_node_properties", node="Body"))["properties"]
    }
    assert now["position"] == "Vector2(5, 6)"
    assert "needs a Shape2D" in await call_error(
        "set_node_properties", node="Body/Shape", properties={"shape": "res://icon.svg"}
    )
    assert "rename_node" in await call_error(
        "set_node_properties", node="Body", properties={"name": "X"}
    )
    # Literals are parsed only as the property's own type, never as objects.
    assert "expected a Vector2 literal" in await call_error(
        "set_node_properties", node="Body", properties={"position": "Object(Node, 1)"}
    )
    await call("save_scene")
    text = (project_dir / "t" / "props.tscn").read_text()
    assert "RectangleShape2D" in text and "size = Vector2(32, 48)" in text
    assert "motion_mode = 1" in text


async def test_remove_rename_move_duplicate_and_undo(call, call_error):
    await call("new_scene", path="res://t/struct.tscn", root_type="Node2D")
    await call("add_node", type="Node2D", name="A")
    await call("add_node", type="Node2D", name="B")
    await call("add_node", parent="A", type="Sprite2D", name="Child")
    assert await paths(call) == [".", "A", "A/Child", "B"]

    renamed = await call("rename_node", node="A", new_name="Alpha")
    assert renamed["path"] == "Alpha"
    assert "already has a child" in await call_error("rename_node", node="Alpha", new_name="B")

    moved = await call("move_node", node="Alpha/Child", new_parent="B")
    assert moved["path"] == "B/Child"
    await call("move_node", node="B", index=0)
    assert await paths(call) == [".", "B", "B/Child", "Alpha"]
    assert "into itself" in await call_error("move_node", node="B", new_parent="B/Child")

    dup = await call("duplicate_node", node="B", name="B2")
    assert dup["path"] == "B2"
    assert await paths(call) == [".", "B", "B/Child", "B2", "B2/Child", "Alpha"]

    removed = await call("remove_node", node="B")
    assert removed == {"removed": "B"}
    assert await paths(call) == [".", "B2", "B2/Child", "Alpha"]
    assert "can't be removed" in await call_error("remove_node", node=".")

    # Undo goes back through remove, duplicate, move(order), move(parent), rename.
    undone = await call("undo", steps=2)
    assert undone["undone"] == ["MCP: remove_node", "MCP: duplicate_node"]
    assert await paths(call) == [".", "B", "B/Child", "Alpha"]
    await call("undo", steps=3)
    assert await paths(call) == [".", "A", "A/Child", "B"]
    redone = await call("redo")
    assert redone["redone"] == ["MCP: rename_node"]
    assert await paths(call) == [".", "Alpha", "Alpha/Child", "B"]
    # Undone nodes keep their scene ownership: saving writes them.
    await call("undo", steps=1)
    await call("save_scene")
    saved = await call("get_scene_tree", scene="res://t/struct.tscn")
    assert saved["source"] == "editor"


async def test_undo_is_scoped_to_the_current_scene(call, call_error):
    await call("new_scene", path="res://t/undo_a.tscn", root_type="Node2D")
    await call("add_node", type="Node2D", name="InA")
    await call("new_scene", path="res://t/undo_b.tscn", root_type="Node2D")
    await call("add_node", type="Node2D", name="InB")
    # Back in A, undo reverts A's change even though B's is newer.
    await call("open_scene", path="res://t/undo_a.tscn")
    assert (await call("undo"))["undone"] == ["MCP: add_node"]
    assert await paths(call) == ["."]
    assert "no MCP changes in res://t/undo_a.tscn left" in await call_error("undo")
    assert (await call("redo"))["redone"] == ["MCP: add_node"]
    assert "Nothing to redo" in await call_error("redo")
    await call("open_scene", path="res://t/undo_b.tscn")
    assert await paths(call) == [".", "InB"]
    await call("undo")
    assert await paths(call) == ["."]


async def test_signals_and_groups(call, call_error, project_dir):
    await call("new_scene", path="res://t/signals.tscn", root_type="Node2D")
    await call("add_node", type="Button", name="Start")
    await call("add_node", type="Timer", name="Clock")
    listed = await call("list_signals", node="Start", filter="press")
    assert any(s.startswith("pressed()") for s in listed["signals"])

    connected = await call(
        "connect_signal", node="Start", signal="pressed", target="Clock", method="start"
    )
    assert connected["connected"] == "Start.pressed -> Clock.start"
    assert "warning" not in connected  # Timer.start exists
    missing = await call(
        "connect_signal", node="Clock", signal="timeout", target=".", method="_on_clock_timeout"
    )
    assert "no method '_on_clock_timeout'" in missing["warning"]
    assert "Already connected" in await call_error(
        "connect_signal", node="Start", signal="pressed", target="Clock", method="start"
    )
    assert "no signal 'clicked'" in await call_error(
        "connect_signal", node="Start", signal="clicked", target="Clock", method="start"
    )
    conns = (await call("list_signals", node="Start"))["connections"]
    assert conns == [{"signal": "pressed", "method": "start", "target": "Clock", "source": "Start"}]
    incoming = (await call("list_signals", node="Clock"))["incoming_connections"]
    assert incoming[0]["source"] == "Start"

    await call("disconnect_signal", node="Start", signal="pressed", target="Clock", method="start")
    assert (await call("list_signals", node="Start"))["connections"] == []

    groups = await call("set_groups", node="Clock", add=["timers", "hud"])
    assert sorted(groups["groups"]) == ["hud", "timers"]
    groups = await call("set_groups", node="Clock", remove=["hud"])
    assert groups["groups"] == ["timers"]

    await call("save_scene")
    text = (project_dir / "t" / "signals.tscn").read_text()
    assert '[connection signal="timeout" from="Clock" to="." method="_on_clock_timeout"]' in text
    assert 'groups=["timers"]' in text


async def test_save_branch_as_scene(call, call_error, project_dir):
    await call("new_scene", path="res://t/branch.tscn", root_type="Node2D")
    await call("add_node", type="Area2D", name="Coin", properties={"position": [50, 60]})
    await call("add_node", parent="Coin", type="Sprite2D", properties={"texture": "res://icon.svg"})
    await call("add_node", parent="Coin", type="CollisionShape2D")
    res = await call("save_branch_as_scene", node="Coin", path="res://t/coin.tscn")
    assert res == {"saved": "res://t/coin.tscn", "instance": "Coin"}
    nodes = {n["path"]: n for n in (await call("get_scene_tree"))["nodes"]}
    assert nodes["Coin"]["instance_of"] == "res://t/coin.tscn"
    assert list(nodes) == [".", "Coin"]  # children now live in coin.tscn
    coin = await call("get_scene_tree", scene="res://t/coin.tscn")
    assert [n["path"] for n in coin["nodes"]] == [".", "Sprite2D", "CollisionShape2D"]
    assert "already exists" in await call_error(
        "save_branch_as_scene", node="Coin", path="res://t/coin.tscn"
    )
    await call("undo")
    assert "Coin/Sprite2D" in await paths(call)
