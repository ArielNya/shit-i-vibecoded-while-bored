"""M5: resources, imported assets, TileSets and tile maps."""

import pytest

from .pixel_art import tile_sheet

pytestmark = pytest.mark.anyio


@pytest.fixture
def art_dir(tmp_path, monkeypatch):
    folder = tmp_path / "incoming"
    folder.mkdir()
    (folder / "tiles.png").write_bytes(tile_sheet())
    (folder / "notes.txt").write_text("not an asset")
    monkeypatch.setenv("GODOT_MCP_ASSET_DIRS", str(folder))
    return folder


async def test_resources(call, call_error, project_dir):
    made = await call(
        "create_resource",
        path="res://data/jump.tres",
        type="Curve",
        properties={"max_value": 2.0, "bake_resolution": 50},
    )
    assert made["type"] == "Curve"
    assert {p["name"]: p["value"] for p in made["properties"]}["max_value"] == 2.0
    assert (project_dir / "data" / "jump.tres").is_file()
    assert "already exists" in await call_error(
        "create_resource", path="res://data/jump.tres", type="Curve"
    )

    changed = await call(
        "set_resource_properties", path="res://data/jump.tres", properties={"max_value": 5}
    )
    assert changed["values"] == {"max_value": 5.0}
    assert "_limits = [0.0, 5.0" in (project_dir / "data" / "jump.tres").read_text()
    got = await call("get_resource", path="res://data/jump.tres", filter="max")
    assert [p["name"] for p in got["properties"]] == ["max_value"]

    await call("undo")
    assert "_limits = [0.0, 2.0" in (project_dir / "data" / "jump.tres").read_text()

    assert "unknown resource class" in await call_error(
        "create_resource", path="res://x.tres", type="NotAThing"
    )
    assert "not a resource class" in await call_error(
        "create_resource", path="res://x.tres", type="Node2D"
    )
    assert "Nothing was changed" in await call_error(
        "set_resource_properties", path="res://data/jump.tres", properties={"max_valu": 1}
    )


async def test_import_and_reimport(call, call_error, art_dir):
    imported = await call("import_asset", source="tiles.png", path="res://art/tiles.png")
    assert imported["type"] == "CompressedTexture2D"
    assert imported["size"] == "64x16"
    assert imported["importer"] == "texture"
    assert imported["import_options"]["mipmaps/generate"] is False

    again = await call(
        "reimport", paths=["res://art/tiles.png"], import_options={"mipmaps/generate": True}
    )
    assert again["assets"][0]["import_options"]["mipmaps/generate"] is True

    assert "already exists" in await call_error(
        "import_asset", source="tiles.png", path="res://art/tiles.png"
    )
    assert "outside the folders" in await call_error(
        "import_asset", source="/etc/hostname", path="res://art/h.png"
    )
    assert "import_asset takes" in await call_error(
        "import_asset", source="notes.txt", path="res://notes.txt"
    )
    assert "not an import option" in await call_error(
        "reimport", paths=["res://art/tiles.png"], import_options={"nope": 1}
    )


async def test_tileset_and_tiles(call, call_error, art_dir):
    await call("import_asset", source="tiles.png", path="res://art/sheet.png", overwrite=True)
    ts = await call(
        "create_tileset",
        path="res://art/sheet_tiles.tres",
        texture="res://art/sheet.png",
        tile_size=[16, 16],
        solid_tiles=[[1, 0], [2, 0]],
    )
    assert ts["atlas_grid"] == [4, 1]
    assert ts["tiles"] == [[0, 0], [1, 0], [2, 0]]  # the transparent cell is skipped
    assert ts["solid_tiles"] == 2

    await call("new_scene", path="res://t/tiles.tscn", root_type="Node2D")
    await call(
        "add_node", type="TileMapLayer", name="Ground",
        properties={"tile_set": "res://art/sheet_tiles.tres"},
    )  # fmt: skip
    painted = await call(
        "set_tiles",
        node="Ground",
        grid=["        ", "  ===   ", "########"],
        legend={"#": [2, 0], "=": [1, 0]},
        origin=[-2, 3],
    )
    assert painted["cells"] == 11
    tiles = await call("get_tiles", node="Ground")
    assert tiles["origin"] == [-2, 4]  # the blank first row isn't part of the used area
    char = {tuple(v["atlas"]): k for k, v in tiles["legend"].items()}
    assert tiles["grid"] == [".." + char[(1, 0)] * 3 + "...", char[(2, 0)] * 8]

    await call("set_tiles", node="Ground", erase=[[-2, 5]], cells=[[0, 0, 0, 0]])
    cells = await call("get_tiles", node="Ground", format="cells")
    coords = {(c[0], c[1]) for c in cells["cell_list"]}
    assert (0, 0) in coords and (-2, 5) not in coords

    await call("undo")  # the erase + single cell
    await call("undo")  # the grid
    assert (await call("get_tiles", node="Ground"))["cells"] == 0

    assert "not in the legend" in await call_error(
        "set_tiles", node="Ground", grid=["#x"], legend={"#": [2, 0]}
    )
    assert "no tile at atlas" in await call_error(
        "set_tiles", node="Ground", cells=[[0, 0, 3, 0]]
    )  # the empty cell
    assert "not a TileMapLayer" in await call_error("get_tiles", node=".")
    await call("add_node", type="TileMapLayer", name="Bare")
    assert "has no tile_set" in await call_error("set_tiles", node="Bare", cells=[[0, 0, 0, 0]])
