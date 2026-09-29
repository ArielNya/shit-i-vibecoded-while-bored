"""Guides, skills, prompts and resources (M7), execute_gdscript's result mapping, and
install-addon."""

import json

import pytest
from mcp import Client

from godot_mcp.bridge import BridgeConfig, GodotBridge
from godot_mcp.install import enable_plugin, install
from godot_mcp.server import create_server, main
from godot_mcp.tools.guides import PROMPTS, all_guides

from .fakes import FakeGodot

pytestmark = pytest.mark.anyio

SKILLS = {"godot-2d-platformer", "godot-3d-third-person", "godot-ui-menu"}
GUIDES = {"pitfalls", "values", "movement", "physics", "scenes", "ui", "testing", "export"}


def test_guides_and_skills_load():
    guides = all_guides()
    assert set(guides) == GUIDES | SKILLS
    for name in SKILLS:
        skill = guides[name]
        assert skill.uri == f"godot://skills/{name}" and len(skill.description) > 50
        assert not skill.text.startswith("---")  # frontmatter stripped
        assert skill.description.startswith("Build")  # a trigger-style description
    assert guides["pitfalls"].uri == "godot://docs/pitfalls"


@pytest.fixture
async def client():
    handlers = {
        "get_project_info": lambda p: {"name": "Demo", "godot_version": "4.7.2"},
        "execute_gdscript": lambda p: (
            {"ok": True, "result": "Vector2(1, 2)", "output": ["hi"], "errors": []}
            if "ok" in p["code"]
            else {
                "ok": False,
                "stage": "compile",
                "output": [],
                "errors": [{"line": 2, "message": "Parse Error: nope"}],
            }
        ),  # fmt: skip
    }
    async with FakeGodot(handlers) as fake:
        bridge = GodotBridge(BridgeConfig(port=fake.port, timeout=5))
        async with Client(create_server(bridge)) as c:
            yield c
        await bridge.close()


async def test_read_guide(client):
    listed = json.loads((await client.call_tool("read_guide", {})).content[0].text)
    topics = {g["topic"] for g in listed["guides"]}
    assert topics == GUIDES | SKILLS | set(PROMPTS)
    pitfalls = json.loads(
        (await client.call_tool("read_guide", {"topic": "pitfalls"})).content[0].text
    )
    assert "CharacterBody2D" in pitfalls["text"]
    loop = json.loads(
        (await client.call_tool("read_guide", {"topic": "fix_errors_loop"})).content[0].text
    )
    assert "validate_project" in loop["text"]
    missing = await client.call_tool("read_guide", {"topic": "nope"})
    assert missing.is_error and "pitfalls" in missing.content[0].text


async def test_resources_and_prompts(client):
    uris = {str(r.uri) for r in (await client.list_resources()).resources}
    assert {"godot://project", "godot://docs/pitfalls", "godot://skills/godot-ui-menu"} <= uris
    doc = await client.read_resource("godot://docs/values")
    assert "Vector2(100, 200)" in doc.contents[0].text
    project = await client.read_resource("godot://project")
    assert json.loads(project.contents[0].text)["name"] == "Demo"

    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert set(prompts) == set(PROMPTS)
    assert [a.name for a in prompts["make_prototype"].arguments] == ["idea", "dimension"]
    made = await client.get_prompt("make_prototype", {"idea": "a snake game", "dimension": "3d"})
    text = made.messages[0].content.text
    assert "a snake game" in text and "godot-3d-third-person" in text


async def test_resources_exist_with_any_toolset():
    server = create_server(toolsets=["scene"])
    assert "godot://docs/pitfalls" in {str(r.uri) for r in await server.list_resources()}
    assert {t.name for t in await server.list_tools()} == {"get_scene_tree", "get_node_properties"}


async def test_execute_gdscript_results(client):
    ok = await client.call_tool("execute_gdscript", {"code": "print('ok')"})
    assert not ok.is_error
    assert json.loads(ok.content[0].text) == {"result": "Vector2(1, 2)", "output": ["hi"]}
    bad = await client.call_tool("execute_gdscript", {"code": "fail()"})
    assert bad.is_error and "Parse Error: nope" in bad.content[0].text
    assert '"line": 2' in bad.content[0].text


def test_enable_plugin_variants(tmp_path):
    cfg = tmp_path / "project.godot"
    cfg.write_text('config_version=5\n\n[application]\n\nconfig/name="X"\n')
    assert enable_plugin(cfg) and not enable_plugin(cfg)  # added once
    assert 'enabled=PackedStringArray("res://addons/godot_mcp/plugin.cfg")' in cfg.read_text()

    cfg.write_text('[editor_plugins]\n\nenabled=PackedStringArray("res://addons/gut/plugin.cfg")'
                   '\n\n[rendering]\n\nx=1\n')  # fmt: skip
    enable_plugin(cfg)
    text = cfg.read_text()
    assert ('enabled=PackedStringArray("res://addons/gut/plugin.cfg", '
            '"res://addons/godot_mcp/plugin.cfg")') in text  # fmt: skip
    assert text.endswith("[rendering]\n\nx=1\n")

    cfg.write_text("[editor_plugins]\n\n[input]\n")
    enable_plugin(cfg)
    assert cfg.read_text().startswith(
        '[editor_plugins]\n\nenabled=PackedStringArray("res://addons/godot_mcp/plugin.cfg")'
    )


def test_install_addon(tmp_path, capsys):
    project = tmp_path / "my game"
    project.mkdir()
    (project / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="G"\n')
    first = install(project)
    assert first[0].startswith("Installed the plugin 0.1.0")
    plugin = project / "addons" / "godot_mcp"
    assert (plugin / "plugin.cfg").is_file() and (plugin / "headless" / "runner.gd").is_file()
    (plugin / "stale.gd").write_text("")
    assert install(project)[0] == "Updated the plugin 0.1.0 -> 0.1.0"
    assert not (plugin / "stale.gd").exists()  # replaced, not merged

    main(["install-addon", str(project)])
    assert "claude mcp add godot" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="No project.godot"):
        main(["install-addon", str(tmp_path)])
