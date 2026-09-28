# Publishing and live data

Sources: creator-docs `cloud/guides/usage-place-publishing.md`,
`reference/cloud/universes-api/v1.json` and `reference/cloud/openapi.json` (data stores,
Luau execution).

These act on the **real game**. Do them only when the user asked for that exact thing.
The risky tools don't exist unless roblox-mcp was started with `--allow-publish`
(`publish_place`, `run_luau_cloud place="live"`) or `--allow-datastore-writes`
(`datastore_set`). If a tool is missing, say which flag it needs; don't work around it.

## Publishing

| The place's content lives in | Publish with |
| --- | --- |
| Studio (world built there, code synced by Rojo) — the default layout | **Studio**: File → Publish to Roblox. Ask the user to do it |
| Entirely in the Rojo project (Workspace included) | `build_place`, then `publish_place file="build/<name>.rbxl"` |
| A place file saved from Studio | `publish_place file="<that file>"` |

- `publish_place` **replaces the whole place** with the file. A Rojo build only contains
  what the project defines, so it's refused when the project has no `Workspace`:
  publishing it would delete the world.
- `version_type="Saved"` adds a version without making it live; `"Published"` makes it
  live for players. Default to Saved; publish only when asked.
- The API doesn't update `EditableImage`, `EditableMesh`, `PartOperation` (unions),
  `SurfaceAppearance` or `BaseWrap` instances: places that changed those must be published
  from Studio.
- Key scope: `universe-places:write`.

## Running Luau in the cloud

`run_luau_cloud script="..."` runs a script in a headless server on the latest saved
version of the test place (`place="live"` for the real one, with `--allow-publish`).
Returned values come back as `results` (instances become null), `print` as `output`.
Useful to check a place without Studio: count instances, find missing parts, try an API.
Nothing is saved unless the script calls `AssetService:SavePlaceAsync`; never do that
on the live place unless asked. 5 runs a minute; 5 minutes each. Scopes:
`universe.place.luau-execution-session:write` and `:read`.

## Data stores

- `datastore_list` (stores, or keys in one; `prefix`, 100 per page) and `datastore_read`
  read the live game's standard data stores. Scopes: `universe-datastores.control:list`,
  `universe-datastores.objects:list`, `universe-datastores.objects:read`.
- `datastore_set` replaces one entry's value (JSON) or creates it, keeping the entry's
  users and attributes (Open Cloud would otherwise clear them). Always `datastore_read`
  first and pass its `etag`, so the write fails instead of clobbering a change a live
  server made in between. Scopes: `universe-datastores.objects:read` and `:update`.
- Values that aren't valid JSON numbers come back tagged:
  `{"m": null, "t": "numeric", "v": "nan"}` (also `"inf"`, `"-inf"`). That's usually a bug
  in the game's save code (see NaN in `networking.md`).
- In game code, save with `UpdateAsync` (it works from the current stored value, so
  concurrent servers don't overwrite each other) rather than `SetAsync`.
