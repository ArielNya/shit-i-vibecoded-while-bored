"""Offline Engine API reference (pinned creator-docs, see scripts/build_api_index.py) and
the skill's guides."""

from __future__ import annotations

import gzip
import json
import re
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

PACKAGE = Path(__file__).resolve().parent.parent
INDEX = PACKAGE / "data" / "engine_api.json.gz"
SKILL = PACKAGE / "skills" / "roblox-studio"
UNLISTED = {"Hidden", "NotScriptable"}  # not usable from scripts


@cache
def api() -> dict[str, Any]:
    data = json.loads(gzip.decompress(INDEX.read_bytes()))
    # Enums are looked up as Enum.X: some share a name with a class (Platform, Status, Font).
    data["enums"] = {i["name"].lower(): i for i in data["items"] if i["kind"] == "enum"}
    data["named"] = {i["name"].lower(): i for i in data["items"] if i["kind"] != "enum"}
    return data


def by_name(name: str, enum: bool = False) -> dict | None:
    data = api()
    return data["enums" if enum else "named"].get(name.lower())


def deprecated(x: dict) -> bool:
    return "deprecated" in x or "Deprecated" in x.get("tags", [])


def listed(m: dict) -> bool:
    return not UNLISTED & set(m.get("tags", []))


def ancestors(item: dict) -> list[dict]:
    """The item's superclasses, nearest first."""
    out, queue = [], list(item.get("inherits", []))
    while queue:
        parent = by_name(queue.pop(0))
        if parent and parent not in out:
            out.append(parent)
            queue.extend(parent.get("inherits", []))
    return out


def one_line(text: str) -> str:
    return " ".join(text.split())


def _tags(x: dict) -> str:
    tags = [t for t in x.get("tags", []) if t != "Deprecated"]
    return f" [{', '.join(tags)}]" if tags else ""


def render_item(item: dict) -> str:
    kind = item["kind"]
    out = [f"# {item['name']} ({kind}){_tags(item)}"]
    if parents := ancestors(item):
        out.append("Inherits: " + " > ".join(p["name"] for p in parents))
    if deprecated(item):
        out.append(f"**Deprecated.** {item.get('deprecated', '')}")
    out += ["", item["description"] or item["summary"]]
    members = [m for m in item["members"] if listed(m)]
    current = [m for m in members if not deprecated(m)]
    for group in dict.fromkeys(m["group"] for m in current):
        out += ["", f"## {group.capitalize()}s" if group != "property" else "## Properties"]
        for m in (m for m in current if m["group"] == group):
            out.append(f"- `{m['sig']}`: {one_line(m['summary'])}{_tags(m)}")
    if old := [m["name"] for m in members if deprecated(m)]:
        out += ["", "Deprecated (don't use): " + ", ".join(old)]
    for parent in ancestors(item):
        names = [m["name"] for m in parent["members"] if listed(m) and not deprecated(m)]
        if names:
            out += ["", f"Inherited from {parent['name']}: " + ", ".join(names)]
    return "\n".join(out)


def render_member(item: dict, m: dict) -> str:
    sep = ":" if m["group"] == "method" else "."
    owner = "" if item["kind"] == "global" else item["name"] + sep
    out = [f"# {owner}{m['name']} ({m['group']} of {item['name']}){_tags(m)}", f"`{m['sig']}`"]
    if deprecated(m):
        out.append(f"**Deprecated.** {m.get('deprecated', '')}")
    out += ["", m["description"] or m["summary"]]
    if m.get("params"):
        out += ["", "Parameters:"]
        out += [f"- `{p['name']}: {p['type']}`: {one_line(p['summary'])}" for p in m["params"]]
    if m.get("returns"):
        out += ["", f"Returns: {one_line(m['returns'])}"]
    extra = [f"{k.replace('_', ' ')}: {m[k]}" for k in ("security", "thread_safety") if m.get(k)]
    if extra:
        out += ["", "; ".join(extra)]
    return "\n".join(out)


def find_member(item: dict, name: str) -> tuple[dict, dict] | None:
    lower = name.lower()
    for owner in [item, *ancestors(item)]:
        for exact in (True, False):
            for m in owner["members"]:
                if m["name"] == name if exact else m["name"].lower() == lower:
                    return owner, m
    return None


def lookup(name: str) -> str:
    query = name.strip().removesuffix("()").strip()
    is_enum = query.startswith("Enum.")
    query = query.removeprefix("Enum.")
    item = by_name(query, is_enum) or (None if is_enum else by_name(query, True))
    if item:
        return render_item(item)
    head, sep, tail = query.rpartition(":") if ":" in query else query.rpartition(".")
    owner = by_name(head, is_enum) if sep else None
    if owner:
        if found := find_member(owner, tail):
            return render_member(*found)
        return f"{owner['name']} has no member '{tail}'.\n\n" + render_item(owner)
    for item in api()["items"]:  # bare global function: "wait", "print"
        if item["kind"] == "global" and (found := find_member(item, query)):
            return render_member(*found)
    hits = search(query, 5)
    suggestions = "\n".join(f"- {h}" for h in hits) if hits else "(nothing close)"
    return f"'{name}' isn't in the Engine API reference. Closest matches:\n{suggestions}"


WORD = re.compile(r"[a-z0-9]+")


@cache
def search_rows() -> list[tuple[str, str, str, frozenset[str], str, bool]]:
    """(display name, kind, lowercase name, summary words, summary, deprecated)."""
    rows = []
    for item in api()["items"]:
        summary = one_line(item["summary"])
        words = frozenset(WORD.findall(summary.lower()))
        rows.append((item["name"], item["kind"], item["name"].lower(), words, summary,
                     deprecated(item)))  # fmt: skip
        for m in item["members"]:
            if not listed(m) or m["group"] in ("item", "operator"):
                continue
            sep = ":" if m["group"] == "method" else "."
            full = m["name"] if item["kind"] == "global" else f"{item['name']}{sep}{m['name']}"
            summary = one_line(m["summary"])
            rows.append((full, m["group"], full.lower(), frozenset(WORD.findall(summary.lower())),
                         summary, deprecated(item) or deprecated(m)))  # fmt: skip
    return rows


def search(query: str, limit: int = 10, include_deprecated: bool = False) -> list[str]:
    tokens = WORD.findall(query.lower())
    if not tokens:
        return []
    scored = []
    for full, kind, lower, words, summary, old in search_rows():
        if old and not include_deprecated:
            continue
        name_parts = set(WORD.findall(lower))
        score, hits = 0, 0
        for t in tokens:
            if t in name_parts:
                score, hits = score + 6, hits + 1
            elif len(t) >= 3 and any(p.startswith(t) for p in name_parts):
                score, hits = score + 3, hits + 1
            elif t in words:
                score, hits = score + 1, hits + 1
        if hits * 2 >= len(tokens) and score > 1:
            # prefer whole-query name matches, then shorter names
            if lower.split(":")[-1].split(".")[-1] == query.lower().strip():
                score += 10
            scored.append((-score, len(full), full, kind, summary, old))
    scored.sort()
    return [
        f"{full} ({kind}{', deprecated' if old else ''}): {summary}"
        for _, _, full, kind, summary, old in scored[:limit]
    ]


def guide_topics() -> list[str]:
    return ["skill", *sorted(p.stem for p in (SKILL / "references").glob("*.md"))]


def read_guide_text(topic: str) -> str:
    topics = guide_topics()
    if topic not in topics:
        return f"Unknown topic '{topic}'. Topics: {', '.join(topics)}"
    path = SKILL / "SKILL.md" if topic == "skill" else SKILL / "references" / f"{topic}.md"
    return path.read_text(encoding="utf-8")


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    def get_api_docs(
        name: Annotated[
            str,
            Field(
                description="Class, datatype, enum, library or global, optionally with a "
                'member: "Part", "BasePart.Anchored", "Workspace:Raycast", "Vector3.new", '
                '"Enum.Material", "task.wait", "print"'
            ),  # fmt: skip
        ],
    ) -> str:
        """Roblox Engine API reference for Studio 0.740, offline: members with signatures,
        inherited members, tags (Yields, NotReplicated, ...), security, deprecation notes and
        replacements. Look APIs up here instead of relying on memory."""
        return lookup(name)

    @mcp.tool()
    def search_api(
        query: Annotated[
            str,
            Field(
                description='Words to look for, e.g. "raycast", '
                '"tween transparency", "save player data"'
            ),
        ],  # fmt: skip
        limit: Annotated[int, Field(description="Maximum results", ge=1, le=50)] = 10,
        include_deprecated: Annotated[bool, Field(description="Also list deprecated APIs")] = False,
    ) -> str:
        """Find Engine API classes and members by name or by what they do. Returns
        names with one-line summaries; follow up with get_api_docs."""
        hits = search(query, limit, include_deprecated)
        return "\n".join(hits) if hits else f"No API matches '{query}'."

    @mcp.tool()
    def read_guide(
        topic: Annotated[
            str,
            Field(
                description='"skill" (the main playbook), a reference name, or "" to list topics'
            ),
        ] = "",  # fmt: skip
    ) -> str:
        """Guides for building Roblox games with Studio's MCP server and this one: the
        roblox-studio skill and its references (project layout, networking, deprecated
        APIs, ...). For clients that don't load agent skills."""
        if not topic:
            return "Topics: " + ", ".join(guide_topics())
        return read_guide_text(topic)
