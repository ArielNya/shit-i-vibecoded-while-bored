"""Build the offline Engine API index and the deprecated-API reference from a checkout of
github.com/Roblox/creator-docs.

    uv run python scripts/build_api_index.py /path/to/creator-docs

Writes src/roblox_mcp/data/engine_api.json.gz and
src/roblox_mcp/skills/roblox-studio/references/deprecated.md. Needs only
content/en-us/reference/engine (a sparse checkout is enough)."""

import argparse
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "src/roblox_mcp/data/engine_api.json.gz"
DEPRECATED = ROOT / "src/roblox_mcp/skills/roblox-studio/references/deprecated.md"

KINDS = {
    "classes": "class", "datatypes": "datatype", "enums": "enum",
    "globals": "global", "libraries": "library",
}  # fmt: skip
# YAML list key -> member group, in display order
GROUPS = {
    "constructors": "constructor", "constants": "constant", "properties": "property",
    "methods": "method", "functions": "function", "events": "event", "callbacks": "callback",
    "items": "item", "math_operations": "operator",
}  # fmt: skip
LINK = re.compile(r"`(Class|Datatype|Enum|Global|Library)\.([^`|]+)(?:\|([^`]+))?`")
# Markdown links relative to the docs site (../../../physics/x.md#y, /luau/types)
DOCS_LINK = re.compile(r"\]\((?:\.\./)+|\]\(/(?!/)")
DOCS = "https://create.roblox.com/docs/"


def unlink(text: str | None) -> str:
    """`Class.Part.Anchored|Anchored` -> `Anchored`; `Class.Part` -> `Part`;
    `Enum.Material.Plastic` keeps its Enum prefix (that's how code spells it)."""

    def repl(m: re.Match) -> str:
        kind, target, label = m.groups()
        return f"`{label or (f'Enum.{target}' if kind == 'Enum' else target)}`"

    text = DOCS_LINK.sub("](" + DOCS, LINK.sub(repl, (text or "").strip()))
    return re.sub(r"(\]\(" + re.escape(DOCS) + r"[^)#]*?)\.md\b", r"\1", text)


def short(name: str) -> str:
    """'ChangeHistoryService:TryBeginRecording' -> 'TryBeginRecording'."""
    return re.split(r"[:.]", name)[-1] if not name.startswith("__") else name


def signature(group: str, m: dict) -> str:
    name = short(m["name"])
    if group in ("property", "constant"):
        return f"{name}: {m.get('type')}"
    if group == "item":
        return f"{name} = {m.get('value')}"
    if group == "operator":
        return f"{m.get('type_a')} {m.get('operation')} {m.get('type_b')} -> {m.get('return_type')}"
    params = ", ".join(
        f"{p['name']}: {p.get('type')}"
        + (f" = {p['default']}" if p.get("default") not in (None, "") else "")
        for p in m.get("parameters") or []
    )
    returns = ", ".join(r.get("type") or "()" for r in m.get("returns") or [])
    return f"{name}({params})" + (f" -> {returns}" if returns and returns != "()" else "")


def member(group: str, m: dict) -> dict:
    out = {
        "name": short(m["name"]),
        "group": group,
        "sig": signature(group, m),
        "summary": unlink(m.get("summary")),
        "description": unlink(m.get("description")),
    }
    for key in ("tags", "security", "thread_safety"):
        if m.get(key):
            out[key] = m[key]
    if m.get("deprecation_message"):
        out["deprecated"] = unlink(m["deprecation_message"])
    params = [
        {"name": p["name"], "type": p.get("type"), "summary": unlink(p.get("summary"))}
        for p in m.get("parameters") or []
        if p.get("summary")
    ]
    if params:
        out["params"] = params
    returns = [unlink(r["summary"]) for r in m.get("returns") or [] if r.get("summary")]
    if returns:
        out["returns"] = " ".join(returns)
    return out


def entry(kind: str, d: dict) -> dict:
    out = {
        "name": d["name"],
        "kind": kind,
        "summary": unlink(d.get("summary")),
        "description": unlink(d.get("description")),
        "members": [member(g, m) for key, g in GROUPS.items() for m in d.get(key) or []],
    }
    if d.get("inherits"):
        out["inherits"] = d["inherits"]
    if d.get("tags"):
        out["tags"] = d["tags"]
    if d.get("deprecation_message") or "Deprecated" in (d.get("tags") or []):
        out["deprecated"] = unlink(d.get("deprecation_message")) or "Deprecated."
    return out


def is_deprecated(item: dict) -> bool:
    return "deprecated" in item or "Deprecated" in item.get("tags", [])


def deprecated_md(items: list[dict], meta: dict) -> str:
    lines = [
        "# Deprecated Roblox APIs",
        "",
        f"Generated from the Engine API reference for Studio {meta['studio_version']} "
        f"(creator-docs `{meta['commit'][:7]}`) by `scripts/build_api_index.py`. "
        "Don't use these in new code; the note says what replaces them when the docs do.",
        "",
        "Hidden members and deprecated enum items are left out.",
    ]
    for kind, title in [("class", "Classes"), ("global", "Globals"), ("library", "Libraries"),
                        ("datatype", "Datatypes"), ("enum", "Enums")]:  # fmt: skip
        rows = []
        for item in items:
            if item["kind"] != kind:
                continue
            if is_deprecated(item):
                rows.append((item["name"], item.get("deprecated", "")))
                continue  # its members are implied
            prefix = {"class": item["name"] + ":", "global": ""}.get(kind, item["name"] + ".")
            for m in item["members"]:
                if m["group"] != "item" and is_deprecated(m) and "Hidden" not in m.get("tags", []):
                    rows.append((prefix + m["name"], m.get("deprecated", "")))
        if rows:
            lines += ["", f"## {title}", "", "| API | Note |", "| --- | --- |"]
            for name, note in sorted(rows):
                note = " ".join(note.split()).replace("|", "\\|")
                lines.append(f"| `{name}` | {note} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("creator_docs", type=Path)
    args = parser.parse_args()
    engine = args.creator_docs / "content" / "en-us" / "reference" / "engine"
    if not engine.is_dir():
        sys.exit(f"{engine} not found")
    commit = subprocess.run(
        ["git", "-C", str(args.creator_docs), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    meta = {
        "commit": commit,
        "studio_version": (engine / "STUDIO_VERSION").read_text().split()[0],
    }
    items = []
    for folder, kind in KINDS.items():
        for path in sorted((engine / folder).glob("*.yaml")):
            items.append(entry(kind, yaml.safe_load(path.read_text(encoding="utf-8"))))
    # The `Instance` datatype only holds Instance.new/fromExisting: fold it into the class.
    classes = {i["name"]: i for i in items if i["kind"] == "class"}
    for item in [i for i in items if i["kind"] == "datatype" and i["name"] in classes]:
        classes[item["name"]]["members"][:0] = item["members"]
        items.remove(item)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"meta": meta, "items": items}, separators=(",", ":")).encode()
    INDEX.write_bytes(gzip.compress(data, mtime=0))
    DEPRECATED.parent.mkdir(parents=True, exist_ok=True)
    DEPRECATED.write_text(deprecated_md(items, meta), encoding="utf-8")
    print(f"{len(items)} entries, Studio {meta['studio_version']}, commit {commit[:7]}: "
          f"{INDEX.stat().st_size // 1024} KB index, {DEPRECATED.name}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
