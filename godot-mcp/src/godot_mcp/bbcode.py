"""Convert Godot's class-reference BBCode to compact Markdown for the model."""

from __future__ import annotations

import re

_CODEBLOCK = re.compile(r"\[codeblocks?\](.*?)\[/codeblocks?\]", re.S)
_GDSCRIPT = re.compile(r"\[gdscript[^\]]*\](.*?)\[/gdscript\]", re.S)
_CSHARP = re.compile(r"\[csharp[^\]]*\].*?\[/csharp\]", re.S)
_REFS = re.compile(
    r"\[(method|member|signal|constant|enum|annotation|theme_item|constructor|operator|param)"
    r" ([^\]]+)\]"
)
_URL = re.compile(r"\[url=([^\]]+)\](.*?)\[/url\]", re.S)
_CLASS = re.compile(r"\[([A-Z][A-Za-z0-9_]*)\]")


def _code_block(match: re.Match) -> str:
    body = match.group(1).strip("\n")
    body = "\n".join(line.replace("\t", "    ") for line in body.split("\n"))
    return f"\n```gdscript\n{body}\n```\n"


def to_markdown(text: str) -> str:
    if not text:
        return ""
    out = _CSHARP.sub("", text)
    out = _GDSCRIPT.sub(lambda m: m.group(1), out)
    out = _CODEBLOCK.sub(_code_block, out)
    out = re.sub(r"\[codeblocks?\]|\[/codeblocks?\]", "", out)

    def ref(m: re.Match) -> str:
        kind, name = m.group(1), m.group(2)
        return f"`{name}()`" if kind in ("method", "constructor") else f"`{name}`"

    out = _REFS.sub(ref, out)
    out = _URL.sub(lambda m: f"{m.group(2)} ({m.group(1)})", out)
    out = out.replace("[code]", "`").replace("[/code]", "`")
    out = out.replace("[b]", "**").replace("[/b]", "**")
    out = out.replace("[i]", "*").replace("[/i]", "*")
    out = out.replace("[kbd]", "`").replace("[/kbd]", "`")
    out = re.sub(r"\[/?(u|s|center|br)\]", "", out)
    out = _CLASS.sub(lambda m: f"`{m.group(1)}`", out)
    out = out.replace("[lb]", "[").replace("[rb]", "]")
    return re.sub(r"\n{3,}", "\n\n", out).strip()
