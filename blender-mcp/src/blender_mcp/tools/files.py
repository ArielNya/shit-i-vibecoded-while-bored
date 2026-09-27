"""Saving, opening, importing and exporting — restricted to allowed folders."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Blender

FILE_TIMEOUT = 300.0

PATH_HELP = (
    "Relative paths go in the workspace folder (see list_files); absolute paths must be "
    "inside an allowed folder."
)


def register(mcp: MCPServer, blender: Blender) -> None:
    @mcp.tool()
    async def list_files(
        folder: Annotated[
            str | None, Field(description="Sub-folder of the workspace, or an allowed path")
        ] = None,
    ) -> dict[str, Any]:
        """List model/image/.blend files the file tools can use, and the allowed folders."""
        return await blender.call("list_files", folder=folder)

    @mcp.tool(description=f"Save the .blend file. Without a path, saves in place. {PATH_HELP}")
    async def save_blend(
        path: Annotated[str | None, Field(description="Must end in .blend")] = None,
        overwrite: bool = False,
        copy: Annotated[
            bool, Field(description="Save a copy; keep working on the current file")
        ] = False,
    ) -> dict[str, Any]:
        return await blender.call(
            "save_blend", timeout=FILE_TIMEOUT, path=path, overwrite=overwrite, copy=copy
        )

    @mcp.tool(
        description="Open a .blend file, replacing the current scene. Refuses when there are "
        f"unsaved changes unless discard_unsaved. Embedded scripts never run. {PATH_HELP}"
    )
    async def open_blend(path: str, discard_unsaved: bool = False) -> dict[str, Any]:
        return await blender.call(
            "open_blend", timeout=FILE_TIMEOUT, path=path, discard_unsaved=discard_unsaved
        )

    @mcp.tool(
        description="Import a model (.obj .fbx .glb .gltf .stl .ply .usd/.usda/.usdc/.usdz). "
        f"Returns the names of the new objects. {PATH_HELP}"
    )
    async def import_file(path: str) -> dict[str, Any]:
        return await blender.call("import_file", timeout=FILE_TIMEOUT, path=path)

    @mcp.tool(
        description="Export objects to a model file; the format comes from the extension "
        "(.glb/.gltf embed materials and textures). Refuses to overwrite unless "
        f"overwrite. {PATH_HELP}"
    )
    async def export_file(
        path: str,
        objects: Annotated[
            list[str] | None,
            Field(description="Objects to export (default: everything visible)"),
        ] = None,
        include_children: bool = True,
        apply_modifiers: bool = True,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        return await blender.call(
            "export_file", timeout=FILE_TIMEOUT, path=path, objects=objects,
            include_children=include_children, apply_modifiers=apply_modifiers,
            overwrite=overwrite,
        )  # fmt: skip
