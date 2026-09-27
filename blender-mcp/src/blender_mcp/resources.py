"""MCP resources (live scene data, reference docs) and prompts."""

from __future__ import annotations

from importlib import resources as importlib_resources
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError

from .tools._common import Blender

DOCS = {
    "workflow": "A modelling loop that works well with these tools",
    "selection": "Selection specs for mesh tools, and why indices go stale",
    "modifiers": "Common modifier types, their setting names, and stack order",
    "materials": "Material recipes, lighting setups, cameras and render engines",
    "troubleshooting": "Symptoms and fixes for common problems",
}


def read_doc(topic: str) -> str:
    if topic not in DOCS:
        raise ResourceError(f"unknown topic {topic!r}; topics: {', '.join(DOCS)}")
    return importlib_resources.files("blender_mcp.docs").joinpath(f"{topic}.md").read_text()


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.resource(
        "blender://scene",
        name="scene",
        description="Live summary of the current Blender scene (same as get_scene_info)",
        mime_type="application/json",
    )
    async def scene() -> dict[str, Any]:
        return await blender.call("get_scene_info")

    @mcp.resource(
        "blender://objects/{name}",
        name="object",
        description="Live details of one object (same as get_object_info)",
        mime_type="application/json",
    )
    async def object_info(name: str) -> dict[str, Any]:
        return await blender.call("get_object_info", name=name)

    @mcp.resource(
        "blender://docs",
        name="docs-index",
        description="Index of the reference notes for using these tools",
        mime_type="text/markdown",
    )
    async def docs_index() -> str:
        lines = ["# blender-mcp reference notes", ""]
        lines += [f"- `blender://docs/{topic}` — {summary}" for topic, summary in DOCS.items()]
        return "\n".join(lines) + "\n"

    @mcp.resource(
        "blender://docs/{topic}",
        name="docs",
        description="Reference notes: " + ", ".join(DOCS),
        mime_type="text/markdown",
    )
    async def docs(topic: str) -> str:
        return read_doc(topic)

    @mcp.prompt(
        description="Step-by-step workflow for modelling something in Blender, with "
        "visual checks after each stage"
    )
    def model_object(subject: str, details: str = "", style: str = "clean, simple") -> str:
        extra = f"\nDetails / reference: {details}" if details else ""
        return f"""Model this in Blender: {subject}{extra}
Style: {style}

Work in stages and look at the result after each one (get_viewport_screenshot with
view "front", "top" or "iso"; render_preview when materials matter):

1. Inspect: get_scene_info and list_objects. Decide what to keep or delete.
2. Plan the parts and their real-world sizes in metres; say the plan briefly.
3. Block out each part with create_primitive (use the names it returns), placed and
   scaled roughly right. Screenshot from two angles and fix proportions.
4. Refine: apply_transform on scaled parts, then extrude/inset/bevel/loop_cut/
   transform_elements for shape detail; modifiers (BEVEL, SUBSURF, MIRROR,
   SOLIDIFY) for non-destructive detail. Check get_object_info for is_manifold.
5. Organise: name parts clearly, parent them or put them in a collection.
6. Materials and light: create_material + assign_material, set_world, an AREA key
   light aimed with look_at, and a camera framing the subject.
7. Final render_preview (eevee or cycles) and a short summary of what was built.

Reference notes: blender://docs/workflow, blender://docs/selection,
blender://docs/modifiers, blender://docs/materials."""

    @mcp.prompt(description="Review the current scene for modelling problems and suggest fixes")
    def review_scene() -> str:
        return """Review the current Blender scene for problems. Use get_scene_info,
list_objects and get_object_info on each mesh, and look at it with
get_viewport_screenshot from a few angles.

Check for: non-manifold or open meshes where they should be solid, flipped normals,
unapplied scale on objects with bevels/booleans, n-gons on surfaces that get
subdivided, overlapping or floating parts, objects without materials, missing or
badly placed camera/lights, and confusing names.

Report findings as a short list (object, problem, suggested fix). Don't change
anything until asked."""
