# Project layout

Sources: creator-docs `scripting/locations.md`, `scripting/security/security-tactics.md`
(Studio 0.740); Rojo 7.7 docs (`sync-details.md`, `project-format.md`) and changelog.

## Where things go

| Container | Replicates to clients | Put here |
| --- | --- | --- |
| `ServerScriptService` | no | the server entry `Script` and server-only modules: game logic, data, validation |
| `ServerStorage` | no | server-only assets: maps, tools and NPCs to clone, secret config |
| `ReplicatedStorage` | yes | shared modules, remotes (`RemoteEvent` / `RemoteFunction`), the client entry `Script` (`RunContext = Client`), assets both sides clone |
| `ReplicatedFirst` | yes, first | only a loading screen: one client script, few modules |
| `Workspace` | yes | the 3D world. No scripts here: tag instances and drive them from a module |
| `StarterPlayer.StarterPlayerScripts` / `StarterCharacterScripts`, `StarterGui`, `StarterPack` | copied into each player | `LocalScript`s only when you must; UI (`ScreenGui`) lives in `StarterGui` |
| `Lighting`, `SoundService`, `Teams`, `Chat`, … | yes | service settings and their children |

Anything a client can see, an exploiter can read, including every `ModuleScript` in
a replicated container even if it never runs there. Secrets and authoritative
logic live in `ServerScriptService` / `ServerStorage` only.

## Roblox's recommended script structure

- **One server entry**: a `Script` with `RunContext = Server` in
  `ServerScriptService`.
- **One client entry**: a `Script` with `RunContext = Client` in
  `ReplicatedStorage`. (A `Script` with a Client run context in a `Starter*`
  container runs twice: the original and the copy.)
- **Everything else is `ModuleScript`s** that the entries `require`. Give each module
  a `start()` so all modules load before any runs:

```lua
--!strict
-- ServerScriptService.Server (Script, RunContext = Server)
local ServerScriptService = game:GetService("ServerScriptService")
local Rounds = require(ServerScriptService.Rounds)
local Shop = require(ServerScriptService.Shop)

Rounds.start()
Shop.start()
```

- Instances that need behaviour (doors, coins, NPCs) get a **tag**, and one module
  handles all of them:

```lua
--!strict
local CollectionService = game:GetService("CollectionService")

local Coins = {}

local function setUp(coin: Instance) end
local function cleanUp(coin: Instance) end

function Coins.start()
	for _, coin in CollectionService:GetTagged("Coin") do
		setUp(coin)
	end
	CollectionService:GetInstanceAddedSignal("Coin"):Connect(setUp)
	CollectionService:GetInstanceRemovedSignal("Coin"):Connect(cleanUp)
end

return Coins
```

The exception: models and packages meant for the Creator Store carry their own
scripts. Set each one's `RunContext` explicitly.

A new `Script` defaults to `RunContext = Legacy`: server-side, and only runs in a
server container (`ServerScriptService`, `Workspace`).

## Rojo (files ↔ instances)

| File | Becomes |
| --- | --- |
| folder | `Folder` |
| `Name.server.luau` | `Script` (see `emitLegacyScripts` below) |
| `Name.client.luau` | `LocalScript`, or `Script` with `RunContext = Client` |
| `Name.plugin.luau` | `Script` with `RunContext = Plugin` |
| `Name.luau` | `ModuleScript` |
| `init.server.luau` / `init.client.luau` / `init.luau` | turns its **folder** into that script; the other files become its children |
| `Name.model.json` | hand-written instances (remotes, folders, values) |
| `Name.meta.json` / `init.meta.json` | properties or `className` for the matching file / folder |
| `Name.rbxm` / `.rbxmx` | a model saved from Studio |
| `Name.json` / `.toml` | `ModuleScript` returning that data |
| `Name.txt` | `StringValue` |
| `Name.csv` | `LocalizationTable` |

For the recommended structure, set `"emitLegacyScripts": false` in
`default.project.json`: `*.server.luau` then becomes a `Script` with
`RunContext = Server` and `*.client.luau` a `Script` with `RunContext = Client`, so
the client entry can live in `ReplicatedStorage`. It defaults to `true` (legacy
`Script` / `LocalScript`).

```json
{
  "name": "my-game",
  "emitLegacyScripts": false,
  "tree": {
    "$className": "DataModel",
    "ReplicatedStorage": {
      "Shared": { "$path": "src/shared" },
      "Client": { "$path": "src/client" },
      "Remotes": { "$path": "src/remotes" }
    },
    "ServerScriptService": {
      "Server": { "$path": "src/server" }
    }
  }
}
```

Remotes as a JSON model, e.g. `src/remotes/Combat.model.json` (becomes
`ReplicatedStorage.Remotes.Combat`):

```json
{
  "ClassName": "Folder",
  "Children": [
    { "Name": "Attack", "ClassName": "RemoteEvent" },
    { "Name": "GetInventory", "ClassName": "RemoteFunction" }
  ]
}
```

What Rojo can't live-sync (build a place file with `rojo build` and open it
instead): binary data such as Terrain and CSG parts, `MeshPart.MeshId`,
`HttpService.HttpEnabled`. So the **world** (terrain, meshes, level geometry)
usually stays in the place and is edited in Studio; **code** and simple instances
live in files.

To pull an existing place into files once: `rojo syncback <project> --input
place.rbxl` (Rojo 7.7+). Rojo syncs files → Studio; don't edit synced scripts in
Studio, the next sync overwrites them.
