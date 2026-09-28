import importlib.util
import re
from pathlib import Path

from roblox_mcp.tools.docs import SKILL, api, guide_topics, lookup, read_guide_text, search

ROOT = Path(__file__).resolve().parents[2]


def build_script():
    spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build_api_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_index_is_pinned_to_a_studio_version():
    meta = api()["meta"]
    assert meta["studio_version"].startswith("0.740.")
    assert re.fullmatch(r"[0-9a-f]{40}", meta["commit"])
    assert len(api()["items"]) > 1000


def test_members_are_found_through_inheritance():
    assert lookup("Workspace:Raycast").startswith("# WorldRoot:Raycast (method of WorldRoot)")
    assert lookup("Part.Anchored").startswith("# BasePart.Anchored (property of BasePart)")
    part = lookup("part")  # case-insensitive
    assert "Inherits: FormFactorPart > BasePart" in part
    assert "Inherited from Instance:" in part and "FindFirstChild" in part


def test_names_shared_by_classes_and_enums():
    assert lookup("Platform").startswith("# Platform (class)")
    assert lookup("Enum.Platform").startswith("# Platform (enum)")
    assert lookup("Enum.Platform.Windows").startswith("# Platform.Windows (item of Platform)")
    assert lookup("Font").startswith("# Font (datatype)")
    assert lookup("Enum.Font").startswith("# Font (enum)")
    assert lookup("Instance.new").startswith("# Instance.new (constructor of Instance)")


def test_globals_libraries_and_callbacks():
    assert lookup("task.wait").startswith("# task.wait (function of task)")
    old = lookup("wait")
    assert old.startswith("# wait (function of Roblox globals)")
    assert "**Deprecated.**" in old and "task.wait()" in old
    assert lookup("RemoteFunction.OnServerInvoke").startswith("# RemoteFunction.OnServerInvoke")


def test_unknown_names_get_suggestions():
    assert "Closest matches" in lookup("Raycastt")
    assert "has no member 'Nope'" in lookup("Part.Nope")


def test_search():
    assert search("raycast")[0].startswith("WorldRoot:Raycast (method)")
    assert not any(h.startswith("wait ") for h in search("wait", 50))
    assert any(h.startswith("wait (function, deprecated)") for h in search("wait", 50, True))
    assert search("   ") == []


def test_guides():
    assert guide_topics() == ["skill", "deprecated", "networking", "project-layout"]
    assert read_guide_text("skill").startswith("---\nname: roblox-studio\n")
    assert read_guide_text("../SKILL").startswith("Unknown topic")


def test_skill_references_exist_and_frontmatter_is_valid():
    text = (SKILL / "SKILL.md").read_text()
    front = text.split("---")[1]
    assert "name: roblox-studio" in front and "description: " in front
    for ref in re.findall(r"`references/([\w-]+\.md)`", text):
        assert (SKILL / "references" / ref).is_file(), ref


def test_deprecated_reference_matches_the_index():
    text = read_guide_text("deprecated")
    assert f"`{api()['meta']['commit'][:7]}`" in text
    assert "| `wait` | This method has been superseded by `task.wait()`" in text
    assert "../" not in text  # docs-relative links were made absolute


def test_link_rewriting():
    unlink = build_script().unlink
    assert unlink("`Class.Part.Anchored|Anchored`") == "`Anchored`"
    assert unlink("`Class.Part`, `Enum.Material.Plastic`") == "`Part`, `Enum.Material.Plastic`"
    assert unlink("[notes](../../../physics/movers.md#legacy)") == (
        "[notes](https://create.roblox.com/docs/physics/movers#legacy)"
    )
    assert unlink("[types](/luau/types.md)") == "[types](https://create.roblox.com/docs/luau/types)"
    assert (
        unlink("[wiki](https://en.wikipedia.org/wiki/X)")
        == "[wiki](https://en.wikipedia.org/wiki/X)"
    )
