"""Resources, imported assets (textures, audio, fonts, models), TileSets and tile maps."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ._common import Godot, ToolError

MAX_ASSET_BYTES = 20 * 1024 * 1024  # base64 must fit the 32 MB bridge message

Properties = Annotated[
    dict[str, Any],
    Field(description="Property name -> value, same formats as set_node_properties"),
]


def asset_dirs() -> list[Path]:
    """Folders import_asset may read from: --asset-dir / GODOT_MCP_ASSET_DIRS (os.pathsep
    separated), else the server's working directory."""
    raw = os.environ.get("GODOT_MCP_ASSET_DIRS", "")
    dirs = [Path(d).expanduser() for d in raw.split(os.pathsep) if d.strip()]
    return [d.resolve() for d in (dirs or [Path.cwd()])]


def read_asset(source: str) -> bytes:
    """The bytes of `source`, if it is a file inside an allowed folder (after resolving
    symlinks and '..')."""
    allowed = asset_dirs()
    candidate = Path(source).expanduser()
    if not candidate.is_absolute():
        candidate = allowed[0] / candidate
    path = candidate.resolve()
    if not any(path == d or d in path.parents for d in allowed):
        raise ToolError(
            f"'{source}' is outside the folders import_asset may read "
            f"({', '.join(map(str, allowed))}). Start the server with --asset-dir <folder> "
            "(or GODOT_MCP_ASSET_DIRS) to allow another one."
        )
    if not path.is_file():
        raise ToolError(f"No file at '{path}'.")
    if path.stat().st_size > MAX_ASSET_BYTES:
        raise ToolError(f"'{path}' is over {MAX_ASSET_BYTES // 2**20} MB.")
    return path.read_bytes()


def register(mcp: MCPServer, godot: Godot) -> None:
    @mcp.tool()
    async def create_resource(
        path: Annotated[str, Field(description="Where to save it, e.g. res://data/stats.tres")],
        type: Annotated[
            str,
            Field(
                description="Resource class: engine (Curve, Gradient, StandardMaterial3D"
                ", ...) or a project class_name"
            ),
        ],
        properties: Properties = {},  # noqa: B006
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Create a resource file (.tres) of any Resource type, with initial properties.
        Assign it to nodes with set_node_properties (value: its res:// path)."""
        return await godot.call(
            "create_resource", path=path, type=type, properties=properties, overwrite=overwrite
        )

    @mcp.tool()
    async def get_resource(
        path: Annotated[str, Field(description="res:// path of a resource or imported asset")],
        filter: Annotated[str, Field(description="Only properties containing this")] = "",
        include_defaults: bool = False,
    ) -> dict[str, Any]:
        """A resource's properties (a .tres, or an imported texture/audio/font/scene)."""
        return await godot.call(
            "get_resource", path=path, filter=filter, include_defaults=include_defaults
        )

    @mcp.tool()
    async def set_resource_properties(
        path: Annotated[str, Field(description="res:// path of a .tres/.res resource")],
        properties: Properties,
    ) -> dict[str, Any]:
        """Change properties of a saved resource and save it (one undo step). All values
        are checked first; if one is invalid nothing changes."""
        return await godot.call("set_resource_properties", path=path, properties=properties)

    @mcp.tool()
    async def import_asset(
        source: Annotated[
            str,
            Field(
                description="File on this machine (image, audio, font, model), inside the "
                "server's asset folders (default: its working directory)"
            ),
        ],
        path: Annotated[str, Field(description="Where it goes, e.g. res://art/player.png")],
        import_options: Annotated[
            dict[str, Any],
            Field(
                description='Importer options to set, e.g. {"mipmaps/generate": true}; '
                "import_asset's result lists them"
            ),
        ] = {},  # noqa: B006
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Copy an asset file into the project and import it. Returns its resource type,
        size and import options. For crisp pixel art also set the project setting
        rendering/textures/canvas_textures/default_texture_filter to 0 (Nearest)."""
        data = read_asset(source)
        return await godot.call(
            "import_asset",
            timeout=120,
            path=path,
            data_base64=base64.b64encode(data).decode(),
            import_options=import_options,
            overwrite=overwrite,
        )

    @mcp.tool()
    async def reimport(
        paths: Annotated[list[str], Field(description="res:// paths of imported assets")],
        import_options: Annotated[
            dict[str, Any], Field(description="Importer options to change first")
        ] = {},  # noqa: B006
    ) -> dict[str, Any]:
        """Reimport assets, optionally changing their import options."""
        return await godot.call("reimport", timeout=120, paths=paths, import_options=import_options)

    @mcp.tool()
    async def create_tileset(
        path: Annotated[str, Field(description="Where to save the TileSet, e.g. res://tiles.tres")],
        texture: Annotated[str, Field(description="res:// path of the sprite sheet")],
        tile_size: Annotated[list[int], Field(description="[width, height] in pixels")] = [16, 16],  # noqa: B006
        collision: Annotated[
            Literal["none", "all"], Field(description="Full-tile collision on every tile, or none")
        ] = "none",
        solid_tiles: Annotated[
            list[list[int]],
            Field(description="Instead: only these [column, row] tiles collide (ground, walls)"),
        ] = [],  # noqa: B006
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Make a TileSet from a sprite sheet: one tile per grid cell (empty cells
        skipped), optional collision. Returns the tiles' [column, row] atlas coordinates
        to use with set_tiles."""
        return await godot.call(
            "create_tileset",
            path=path,
            texture=texture,
            tile_size=tile_size,
            collision=solid_tiles or collision,
            overwrite=overwrite,
        )

    @mcp.tool()
    async def get_tiles(
        node: Annotated[str, Field(description="Path of a TileMapLayer node")],
        format: Annotated[str, Field(description="'grid' (ASCII map + legend) or 'cells'")] = (
            "grid"
        ),
        scene: Annotated[str, Field(description="Scene to read; empty = current")] = "",
    ) -> dict[str, Any]:
        """The tiles painted on a TileMapLayer, as an ASCII map (one character per kind of
        tile, with a legend) or as a list of cells."""
        return await godot.call("get_tiles", node=node, format=format, scene=scene)

    @mcp.tool()
    async def set_tiles(
        node: Annotated[str, Field(description="Path of a TileMapLayer node")],
        grid: Annotated[
            list[str],
            Field(
                description="Rows of characters, top to bottom, mapped through `legend`; "
                "' ' leaves a cell alone"
            ),
        ] = [],  # noqa: B006
        legend: Annotated[
            dict[str, Any],
            Field(
                description='Character -> tile: [atlas_column, atlas_row], or {"atlas": '
                '[c, r], "source": id}; null erases. E.g. {"#": [0, 0], "=": [1, 0], ".": null}'
            ),
        ] = {},  # noqa: B006
        origin: Annotated[
            list[int], Field(description="Cell [x, y] of the grid's top-left corner")
        ] = [0, 0],  # noqa: B006
        cells: Annotated[
            list[list[int]], Field(description="[x, y, atlas_column, atlas_row] cells")
        ] = [],  # noqa: B006
        fill_rects: Annotated[
            list[list[int]],
            Field(description="[x, y, width, height, atlas_column, atlas_row] areas"),
        ] = [],  # noqa: B006
        erase: Annotated[list[list[int]], Field(description="[x, y] cells to clear")] = [],  # noqa: B006
        source: Annotated[int, Field(description="Tile source id; default: the first")] = -1,
        scene: Annotated[str, Field(description="Scene to edit; empty = current")] = "",
    ) -> dict[str, Any]:
        """Paint a TileMapLayer (one undo step). Easiest: draw the level as `grid` rows
        with a `legend`. The layer needs a tile_set (see create_tileset)."""
        params: dict[str, Any] = {
            "node": node,
            "grid": grid,
            "legend": legend,
            "origin": origin,
            "cells": cells,
            "fill_rects": fill_rects,
            "erase": erase,
            "scene": scene,
        }
        if source >= 0:
            params["source"] = source
        return await godot.call_with("set_tiles", params)
