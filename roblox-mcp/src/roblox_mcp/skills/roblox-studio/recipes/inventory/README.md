# Recipe: inventory with saved data

Items picked up from ProximityPrompts, stacked per item with limits, saved per player
across sessions, and a `DropItem` remote validated on the server.

Files (type-check clean, specs pass):

- `src/shared/Items.luau`: the catalog, the only item ids that exist.
- `src/shared/Inventory.luau`: pure rules: `add` (stack limits), `remove`, and `sanitize`
  for loaded data (unknown items, NaN, fractions, over-limit counts dropped), with
  `Inventory.spec.luau`.
- `src/server/PlayerData.luau`: load on join (`GetAsync` with retries, backoff and
  jitter), keep in memory, save on leave, on shutdown (`BindToClose`) and every 180 s
  with a per-server random offset. A player whose load failed is kicked and never saved,
  so a failed load can't wipe their data.
- `src/server/Items.luau`: givers are `ProximityPrompt`s tagged `ItemGiver` with a
  string attribute `ItemId`; `DropItem` is rate-limited, type-checked (`unknown` →
  `typeof`, `math.isfinite`) and checked against what the player owns.
- `src/remotes/Inventory.model.json`: `ReplicatedStorage.Remotes.Inventory.DropItem`.

In Studio: data stores only work in Studio with **Game Settings → Security → Enable Studio
Access to API Services** on (the place must be published). Add a prompt with an
undoable `execute_luau`: a part with a `ProximityPrompt` child that has
`prompt:SetAttribute("ItemId", "Apple")` and `prompt:AddTag("ItemGiver")`.

Not included, on purpose: session locking and purchase receipts. Without them one
server owns a player's key while they're in it, which is fine for this. Add both before
trading or selling items (`references/data.md`).
