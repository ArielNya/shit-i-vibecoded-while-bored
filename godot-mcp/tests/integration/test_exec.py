"""M7: execute_gdscript in the editor and in the running game (the editor is started with
--mcp-allow-execute; token auth is on as always in the tests)."""

import pytest

pytestmark = pytest.mark.anyio

EDITOR_OPTIONS = {"user_args": ["--mcp-allow-execute"]}


async def test_editor_snippets(call, call_error):
    out = await call("execute_gdscript", code="print('hello')\nreturn scene.name")
    assert out == {"result": "Main", "output": ["hello"]}
    # editor helpers, await, loops with spaces
    out = await call(
        "execute_gdscript",
        code="var names := []\nfor n in scene.get_children():\n    names.append(String(n.name))\n"
        "await tree.process_frame\n"
        "return [names.size() > 0, editor.get_edited_scene_root() == scene]",
    )
    assert out["result"] == [True, True]
    # engine types come back as literals
    assert (await call("execute_gdscript", code="return Vector2(3, 4)"))[
        "result"
    ] == "Vector2(3, 4)"


async def test_editor_errors_point_at_snippet_lines(call_error):
    text = await call_error("execute_gdscript", code="var ok := 1\nvar x: int = 'a'\nreturn x")
    assert '"stage": "compile"' in text and '"line": 2' in text and "Parse Error" in text
    text = await call_error("execute_gdscript", code="print('before')\nvar a := []\nreturn a[3]")
    assert '"stage": "run"' in text and '"line": 3' in text and "before" in text


async def test_game_snippets(call, call_error):
    run = await call("run_project")
    assert run["running"]
    try:
        out = await call(
            "execute_gdscript",
            target="game",
            code="print('in game')\nawait tree.physics_frame\n"
            "return [scene.name, Engine.is_editor_hint(), tree.root.has_node('McpRuntime')]",
        )
        assert out == {"result": ["Main", False, True], "output": ["in game"]}
        text = await call_error("execute_gdscript", target="game", code="return nope")
        assert '"line": 1' in text and "nope" in text
    finally:
        await call("stop_project")
    assert "not running" in await call_error("execute_gdscript", target="game", code="return 1")
