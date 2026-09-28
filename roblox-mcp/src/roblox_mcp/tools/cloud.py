"""Open Cloud operations on the game: running Luau against a place, DataStores, and
publishing. Anything that can change the live game is only registered when the server
is started with the matching --allow-* flag."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .. import opencloud
from .project import find_project_file, inside

MAX_LOG_LINES = 100


def run_script(script: str, place: str, allow_live: bool) -> dict[str, Any]:
    if place == "test":
        env = opencloud.config("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID", "ROBLOX_TEST_PLACE_ID")
        place_id = env["ROBLOX_TEST_PLACE_ID"]
    elif place == "live":
        if not allow_live:
            raise opencloud.CloudError("running against the live place needs the server "
                                       "started with --allow-publish")  # fmt: skip
        env = opencloud.config("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID", "ROBLOX_PLACE_ID")
        place_id = env["ROBLOX_PLACE_ID"]
    else:
        raise ValueError('place must be "test" or "live"')
    task = opencloud.run_luau(env["ROBLOX_UNIVERSE_ID"], place_id, None, script)
    out: dict[str, Any] = {"state": task["state"], "results": task["results"]}
    if task["error"]:
        out["error"] = task["error"]
    if task["logs"]:
        out["output"] = task["logs"][-MAX_LOG_LINES:]
    return out


def universe() -> str:
    return opencloud.config("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID")["ROBLOX_UNIVERSE_ID"]


def q(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def list_stores(store: str, prefix: str, page_token: str) -> dict[str, Any]:
    base = f"cloud/v2/universes/{universe()}/data-stores"
    params = {"maxPageSize": "100"}
    if page_token:
        params["pageToken"] = page_token
    if prefix:
        params["filter"] = f"id.startsWith({json.dumps(prefix)})"
    query = urllib.parse.urlencode(params)
    if not store:
        reply = opencloud.request("GET", f"{base}?{query}") or {}
        out: dict[str, Any] = {"data_stores": [d["id"] for d in reply.get("dataStores", [])]}
    else:
        reply = opencloud.request("GET", f"{base}/{q(store)}/entries?{query}") or {}
        out = {"store": store, "keys": [e["id"] for e in reply.get("dataStoreEntries", [])]}
    if reply.get("nextPageToken"):
        out["next_page_token"] = reply["nextPageToken"]
    return out


def read_entry(store: str, key: str) -> dict[str, Any]:
    entry = opencloud.request(
        "GET", f"cloud/v2/universes/{universe()}/data-stores/{q(store)}/entries/{q(key)}"
    )
    return {k: entry.get(k) for k in ("id", "value", "revisionId", "revisionCreateTime",
                                      "etag", "users", "attributes") if k in entry}  # fmt: skip


def set_entry(store: str, key: str, value: str, etag: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except ValueError as e:
        raise ValueError(f"value must be JSON (a string needs quotes): {e}") from None
    path = f"cloud/v2/universes/{universe()}/data-stores/{q(store)}/entries/{q(key)}"
    # An update clears users and attributes it doesn't include: carry the current ones.
    try:
        current = opencloud.request("GET", path)
    except opencloud.CloudError as e:
        if e.status != 404:
            raise
        current = {}
    body: dict[str, Any] = {"value": parsed}
    for field in ("users", "attributes"):
        if current.get(field):
            body[field] = current[field]
    if etag:
        body["etag"] = etag  # only update if nobody changed it since it was read
    entry = opencloud.request("PATCH", f"{path}?allowMissing=true", json.dumps(body).encode())
    return {"id": entry.get("id", key), "revisionId": entry.get("revisionId"),
            "etag": entry.get("etag"), "created": not current}  # fmt: skip


def publish(root: Path, file: str, version_type: str) -> dict[str, Any]:
    if version_type not in ("Saved", "Published"):
        raise ValueError('version_type must be "Saved" or "Published"')
    place_file = inside(root, file)
    if place_file.suffix not in (".rbxl", ".rbxlx") or not place_file.is_file():
        raise ValueError(f"'{file}' is not a .rbxl/.rbxlx file in the project")
    project_file = find_project_file(root)
    if project_file and place_file.is_relative_to(root / "build"):
        tree = json.loads(project_file.read_text(encoding="utf-8")).get("tree", {})
        if "Workspace" not in tree:
            raise ValueError(
                "this looks like a Rojo build, and the project doesn't include Workspace: "
                "publishing it would replace the place with one that has no world. Publish "
                "from Studio (File > Publish to Roblox), or publish a place file saved from "
                "Studio."
            )
    env = opencloud.config("ROBLOX_API_KEY", "ROBLOX_UNIVERSE_ID", "ROBLOX_PLACE_ID")
    version = opencloud.save_place_version(
        env["ROBLOX_UNIVERSE_ID"], env["ROBLOX_PLACE_ID"], place_file.read_bytes(),
        version_type, xml=place_file.suffix == ".rbxlx",
    )  # fmt: skip
    return {"place_id": env["ROBLOX_PLACE_ID"], "version": version, "type": version_type}


def register(mcp: MCPServer, root: Path, allow_publish: bool, allow_datastore_writes: bool):
    @mcp.tool()
    def run_luau_cloud(
        script: Annotated[
            str,
            Field(
                description="Luau to run server-side; `return` values "
                "come back as results, print() as output"
            ),
        ],  # fmt: skip
        place: Annotated[
            str,
            Field(description='"test" (ROBLOX_TEST_PLACE_ID) or "live" (needs --allow-publish)'),
        ] = "test",  # fmt: skip
    ) -> dict[str, Any]:
        """Run Luau in a headless Roblox server on the latest saved version of a place,
        through Open Cloud: inspect the place, try engine APIs, check data. Nothing is
        saved unless the script calls AssetService:SavePlaceAsync. Up to 5 runs a minute."""
        return run_script(script, place, allow_publish)

    @mcp.tool()
    def datastore_list(
        store: Annotated[str, Field(description="Data store name; empty lists the stores")] = "",
        prefix: Annotated[str, Field(description="Only names/keys starting with this")] = "",
        page_token: Annotated[str, Field(description="next_page_token from a previous call")] = "",
    ) -> dict[str, Any]:
        """List the game's standard data stores, or the keys in one (100 per page).
        This is the live game's data (the whole universe)."""
        return list_stores(store, prefix, page_token)

    @mcp.tool()
    def datastore_read(
        store: Annotated[str, Field(description="Data store name")],
        key: Annotated[str, Field(description="Entry key, e.g. Player_123")],
    ) -> dict[str, Any]:
        """Read one data store entry of the live game: value, revision, etag, users,
        attributes."""
        return read_entry(store, key)

    if allow_datastore_writes:

        @mcp.tool()
        def datastore_set(
            store: Annotated[str, Field(description="Data store name")],
            key: Annotated[str, Field(description="Entry key")],
            value: Annotated[str, Field(description='New value as JSON, e.g. {"coins": 10}')],
            etag: Annotated[
                str,
                Field(
                    description="etag from datastore_read: only write "
                    "if the entry hasn't changed since"
                ),
            ] = "",  # fmt: skip
        ) -> dict[str, Any]:
            """Create or replace a data store entry in the LIVE game. Players' data: only
            when the user asked for exactly this change. Pass the etag you read."""
            return set_entry(store, key, value, etag)

    if allow_publish:

        @mcp.tool()
        def publish_place(
            file: Annotated[str, Field(description=".rbxl/.rbxlx in the project to upload")],
            version_type: Annotated[
                str,
                Field(
                    description='"Saved" (a new version, not '
                    'live) or "Published" (live for players)'
                ),
            ] = "Saved",  # fmt: skip
        ) -> dict[str, Any]:
            """Upload a place file as a new version of ROBLOX_PLACE_ID. It REPLACES the whole
            place: a Rojo build only has what the project defines (refused when the project
            has no Workspace). Only when the user asked to publish."""
            return publish(root, file, version_type)
