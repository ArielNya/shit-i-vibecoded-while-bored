"""Resources, prompts and toolset selection, against a fake Blender."""

import pytest
from mcp import Client

from blender_mcp import tools
from blender_mcp.bridge import BlenderBridge, BridgeConfig
from blender_mcp.resources import DOCS
from blender_mcp.server import _toolsets, create_server

pytestmark = pytest.mark.anyio

SCENE = {"scene": "Scene", "object_count": 3}


@pytest.fixture
def bridge(fake_blender):
    fb = fake_blender(
        {
            "get_scene_info": lambda params: SCENE,
            "get_object_info": lambda params: {"name": params["name"], "type": "MESH"},
        }
    )
    return BlenderBridge(BridgeConfig(port=fb.listener.port, timeout=5))


async def test_scene_and_object_resources(bridge):
    async with Client(create_server(bridge)) as client:
        uris = {str(r.uri) for r in (await client.list_resources()).resources}
        assert {"blender://scene", "blender://docs"} <= uris
        templates = {
            t.uri_template for t in (await client.list_resource_templates()).resource_templates
        }
        assert {"blender://objects/{name}", "blender://docs/{topic}"} <= templates

        scene = await client.read_resource("blender://scene")
        assert '"object_count": 3' in scene.contents[0].text
        obj = await client.read_resource("blender://objects/Cube")
        assert '"name": "Cube"' in obj.contents[0].text
    await bridge.close()


async def test_docs_resources(bridge):
    async with Client(create_server(bridge)) as client:
        index = (await client.read_resource("blender://docs")).contents[0].text
        for topic in DOCS:
            assert f"blender://docs/{topic}" in index
            doc = (await client.read_resource(f"blender://docs/{topic}")).contents[0]
            assert doc.mime_type == "text/markdown"
            assert doc.text.startswith("# ")
        with pytest.raises(Exception, match="unknown topic"):
            await client.read_resource("blender://docs/nope")
    await bridge.close()


async def test_prompts(bridge):
    async with Client(create_server(bridge)) as client:
        names = {p.name for p in (await client.list_prompts()).prompts}
        assert {"model_object", "review_scene", "model_character"} <= names
        prompt = await client.get_prompt("model_object", {"subject": "a wooden chair"})
        text = prompt.messages[0].content.text
        assert "a wooden chair" in text and "get_viewport_screenshot" in text
    await bridge.close()


async def test_toolsets_limit_exposed_tools(bridge):
    async with Client(create_server(bridge, toolsets=["inspect", "view"])) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert "get_scene_info" in names and "render_preview" in names
    assert "create_primitive" not in names and "export_file" not in names
    await bridge.close()


def test_toolsets_env_parsing():
    assert _toolsets(None) == list(tools.TOOLSETS)
    assert _toolsets(" inspect , mesh ") == ["inspect", "mesh"]
    with pytest.raises(SystemExit, match="unknown toolset"):
        _toolsets("inspect,bogus")


def test_every_doc_topic_has_a_file():
    from importlib import resources

    files = {p.name for p in resources.files("blender_mcp.docs").iterdir()}
    assert {f"{t}.md" for t in DOCS} <= files


async def test_character_prompt(bridge):
    async with Client(create_server(bridge)) as client:
        prompt = await client.get_prompt(
            "model_character", {"front": "front.png", "side": "side.png", "height": "1.6"}
        )
        text = prompt.messages[0].content.text
        assert "front.png" in text and "1.6 m tall" in text
        assert "blender://docs/character" in text
    await bridge.close()


def test_skills_are_generated_from_the_docs():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "build_addon", root / "scripts" / "build_addon.py"
    )
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    for name in build.SKILL_SOURCES:
        skill = root / "skills" / name / "SKILL.md"
        assert skill.read_text() == build.skill_text(name), (
            f"{skill} is stale; run: python scripts/build_addon.py --sync"
        )
