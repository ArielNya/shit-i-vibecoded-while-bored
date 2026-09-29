"""Curated Godot 4.7 guides and workflow skills, for grounding the model.

They're served three ways, because clients differ: MCP resources (godot://docs/<topic>,
godot://skills/<name>, godot://project), MCP prompts (make_prototype, fix_errors_loop,
playtest), and the read_guide tool — several clients show only tools to the model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot, ToolError

HERE = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Guide:
    name: str
    title: str
    description: str
    text: str
    uri: str


def _skills_dir() -> Path:
    """Bundled in the wheel as godot_mcp/skills; the repo's skills/ folder in dev."""
    bundled = HERE / "skills"
    return bundled if bundled.is_dir() else HERE.parents[1] / "skills"


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, text[match.end() :]


@cache
def all_guides() -> dict[str, Guide]:
    guides: dict[str, Guide] = {}
    for path in sorted((HERE / "guides").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        first_para = text.split("\n\n")[1].replace("\n", " ").strip()
        guides[path.stem] = Guide(path.stem, title, first_para[:200], text,
                                  f"godot://docs/{path.stem}")  # fmt: skip
    for path in sorted(_skills_dir().glob("*/SKILL.md")):
        meta, body = _frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name", path.parent.name)
        title = body.strip().splitlines()[0].lstrip("# ").strip()
        guides[name] = Guide(name, title, meta.get("description", ""), body.strip() + "\n",
                             f"godot://skills/{name}")  # fmt: skip
    return guides


# --- prompts (also readable as guides) ----------------------------------------------------


def make_prototype(idea: str, dimension: str = "2d") -> str:
    skill = {"3d": "godot-3d-third-person"}.get(dimension.lower(), "godot-2d-platformer")
    return f"""Build a small playable Godot prototype: {idea}

Work through the godot-mcp tools, in small verified steps:
1. get_project_info and list_files to see what exists; read_guide "pitfalls" once so
   the code is Godot 4.7, not Godot 3.
2. Plan the scenes (player, level, UI) and input actions before creating them. The
   "{skill}" guide (read_guide) is a worked example of this kind of game.
3. Build each scene with new_scene / add_node / set_node_properties, write scripts with
   write_script, and run get_diagnostics after every script; fix errors before going on.
4. save_scene, set the main scene, then validate_project.
5. Play-test: run_project, get_runtime_errors, send_input + wait_for +
   get_live_properties to check the core mechanic actually works, get_game_screenshot
   to look at it. Fix what's wrong and play-test again.
Finish with a short summary of what exists and how to play it."""


def fix_errors_loop(scope: str = "the whole project") -> str:
    return f"""Find and fix the errors in {scope}, until none are left:
1. validate_project (and get_diagnostics for warnings) to list compile and load errors
   with file:line.
2. For each error: read_script around the line, check the API with get_class_docs /
   search_docs if it's an engine call (Godot 3 names are the most common cause), then
   fix it with edit_script. get_diagnostics after each fix.
3. run_project and get_runtime_errors for errors that only happen while playing; fix
   those the same way (the backtrace names the file:line).
4. Repeat until validate_project is clean and a run shows no runtime errors; run_tests
   too if the project has tests. Report what was wrong and what changed."""


def playtest(goal: str = "the core mechanic works") -> str:
    return f"""Play-test the game to check that {goal}.
1. run_project (display=window if you want screenshots) and get_runtime_errors.
2. get_live_tree to find the player and the nodes involved.
3. Drive it like a player: send_input with the project's input actions (get_input_map
   lists them), wait_for conditions instead of fixed sleeps, and get_live_properties
   to measure positions, velocities, scores.
4. get_game_screenshot to see it.
5. stop_project. Report what worked, what didn't (with numbers), and suggest fixes."""


PROMPTS = {"make_prototype": make_prototype, "fix_errors_loop": fix_errors_loop,
           "playtest": playtest}  # fmt: skip


def read_topic(topic: str) -> str:
    guides = all_guides()
    if topic in guides:
        return guides[topic].text
    if topic in PROMPTS:
        return PROMPTS[topic]()
    raise ToolError(f"No guide '{topic}'. Topics: {', '.join([*guides, *PROMPTS])}.")


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def read_guide(
        topic: Annotated[
            str, Field(description="Guide name; empty lists the guides and workflows")
        ] = "",
    ) -> dict[str, Any]:
        """Curated Godot 4.7 guides (Godot 3 pitfalls, movement, physics, UI, scenes,
        testing, exporting, the tool value format) and step-by-step workflows (2D
        platformer, 3D third-person, menus, fix-errors loop, play-testing)."""
        if not topic:
            guides = [{"topic": g.name, "title": g.title, "about": g.description}
                      for g in all_guides().values()]  # fmt: skip
            workflows = [{"topic": name, "title": name.replace("_", " ")} for name in PROMPTS]
            return {"guides": guides + workflows}
        return {"topic": topic, "text": read_topic(topic)}


def register_content(mcp: MCPServer, godot: Godot) -> None:
    """Resources and prompts: registered whatever toolsets are selected (they cost no
    tool slots)."""

    def text_of(guide: Guide):
        def reader() -> str:
            return guide.text

        return reader

    for guide in all_guides().values():
        reader = text_of(guide)
        mcp.resource(guide.uri, name=guide.name, title=guide.title,
                     description=guide.description or guide.title,
                     mime_type="text/markdown")(reader)  # fmt: skip

    @mcp.resource(
        "godot://project",
        name="project",
        title="Current project",
        description="Live summary of the project open in the Godot editor",
        mime_type="application/json",
    )
    async def project_summary() -> str:
        return json.dumps(await godot.call("get_project_info"), indent=1)

    mcp.prompt(title="Make a prototype", description="Build a small playable game from "
               "an idea, verifying each step")(make_prototype)  # fmt: skip
    mcp.prompt(title="Fix errors", description="Find and fix compile and runtime errors "
               "until the project is clean")(fix_errors_loop)  # fmt: skip
    mcp.prompt(title="Play-test", description="Drive the running game with input and "
               "measure whether something works")(playtest)  # fmt: skip
