"""API reference for the connected Godot version: structure from the engine's ClassDB,
descriptions from the class reference via the editor's GDScript language server."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ..bbcode import to_markdown
from ..headless import HeadlessError
from ._common import Godot, LSPError, ToolError

DESCRIPTION_LIMIT = 1500
DOCS_RETRIES = 20
DOCS_RETRY_DELAY = 0.5
HEADLESS_NOTE = (
    "No editor connected: signatures from a headless Godot. Descriptions need the editor "
    "(its language server serves the class reference)."
)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _member_name(signature: str) -> str:
    """'wait_time: float = 1.0' -> wait_time; 'static f(x) -> int' -> f."""
    return signature.split("(")[0].split(":")[0].split(" ")[-1]


def register(mcp: MCPServer, godot: Godot) -> None:
    symbol_cache: dict[tuple[int, str], dict | None] = {}

    async def headless_docs(method: str, params: dict[str, Any]) -> Any:
        """The same handler as the editor's, run in a headless Godot."""
        try:
            return await godot.headless.request(method, params)
        except HeadlessError as exc:
            raise ToolError(f"No editor connected, and headless Godot failed: {exc}") from exc

    async def no_editor() -> bool:
        return await godot.headless.editor_info() is None

    async def class_symbol(cls: str) -> dict | None:
        """The class reference entry for a native class. Right after the editor starts
        it may still be building the reference (documentation comes back empty), so
        retry briefly and only cache complete answers."""
        lsp = await godot.lsp()
        key = (id(lsp), cls)
        if key in symbol_cache:
            return symbol_cache[key]
        sym = None
        for _ in range(DOCS_RETRIES):
            sym = await lsp.native_symbol(cls)
            if sym is None or sym.get("documentation"):
                symbol_cache[key] = sym
                return sym
            await asyncio.sleep(DOCS_RETRY_DELAY)
        return sym

    @mcp.tool()
    async def get_class_docs(
        class_name: Annotated[
            str,
            Field(
                description="Engine class (CharacterBody2D, Node, Vector2...) or a project "
                "class_name"
            ),
        ],
        member: Annotated[
            str,
            Field(description="A method, property, signal or constant to explain in full"),
        ] = "",
        include_inherited: Annotated[
            bool, Field(description="List inherited members too (long)")
        ] = False,
    ) -> dict[str, Any]:
        """Godot API reference for the editor's exact version: signatures of a class's
        properties, methods, virtual callbacks, signals and enums plus its description;
        with `member`, the full docs for that one member (searching base classes too).
        Check this before using an API you're unsure about."""
        if await no_editor():
            data = await headless_docs(
                "get_class_docs",
                {"class_name": class_name, "include_inherited": include_inherited or bool(member)},
            )
            if member:
                groups = ("properties", "methods", "virtual_methods", "signals")
                found = [s for g in groups for s in data.get(g, []) if _member_name(s) == member]
                if not found:
                    raise ToolError(
                        f"'{class_name}' and its base classes have no member '{member}'."
                    )
                return {"class_name": data["class_name"], "member": member, "signatures": found,
                        "note": HEADLESS_NOTE}  # fmt: skip
            data["note"] = HEADLESS_NOTE
            return data
        if member:
            return await _member_docs(class_name, member)
        data = await godot.call(
            "get_class_docs", class_name=class_name, include_inherited=include_inherited
        )
        if data.get("kind") == "native":
            try:
                sym = await class_symbol(class_name)
                if sym and sym.get("documentation"):
                    data["description"] = _clip(
                        to_markdown(sym["documentation"]), DESCRIPTION_LIMIT
                    )
                else:
                    data["description_unavailable"] = (
                        "The editor hasn't loaded the class reference yet; try again shortly."
                    )
            except (LSPError, ToolError) as exc:
                data["description_unavailable"] = str(exc)
        return data

    async def _member_docs(class_name: str, member: str) -> dict[str, Any]:
        data = await godot.call("get_class_docs", class_name=class_name, include_inherited=False)
        if data.get("kind") == "script":
            matches = [
                line
                for group in ("properties", "methods", "signals")
                for line in data.get(group, [])
                if _member_name(line) == member
            ]
            if not matches:
                raise ToolError(f"'{class_name}' (a project script) has no member '{member}'.")
            return {
                "class_name": data["class_name"],
                "member": member,
                "signatures": matches,
                "path": data.get("path"),
                "note": "Project class: read the script for its doc comments.",
            }
        chain = [class_name, *data.get("inherits", [])]
        try:
            for cls in chain:
                sym = await class_symbol(cls)
                for child in (sym or {}).get("children", []):
                    if child.get("name") == member:
                        out = {
                            "class_name": class_name,
                            "member": member,
                            "declared_in": cls,
                            "signature": child.get("detail", ""),
                            "description": to_markdown(child.get("documentation", "")),
                        }
                        if child.get("deprecated"):
                            out["deprecated"] = True
                        return out
        except LSPError as exc:
            raise ToolError(f"Member docs need the GDScript language server: {exc}") from exc
        raise ToolError(
            f"'{class_name}' and its base classes ({', '.join(chain[1:]) or 'none'}) have no "
            f"member '{member}'. Call get_class_docs without `member` to see what exists, or "
            "search_docs to find where it lives."
        )

    @mcp.tool()
    async def search_docs(
        query: Annotated[
            str,
            Field(
                description="Words to find in class/member names, e.g. 'raycast' or 'move slide'"
            ),
        ],
        limit: Annotated[int, Field(ge=1, le=200)] = 30,
        include_editor: Annotated[bool, Field(description="Include editor-only classes")] = False,
    ) -> dict[str, Any]:
        """Find engine and project classes, methods, properties and signals whose names
        contain all the query words. Use it to find the right API, then get_class_docs."""
        params = {"query": query, "limit": limit, "include_editor": include_editor}
        if await no_editor():
            return await headless_docs("search_docs", params)
        return await godot.call_with("search_docs", params)
