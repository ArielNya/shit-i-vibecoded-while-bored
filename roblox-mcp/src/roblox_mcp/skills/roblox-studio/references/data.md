# Player data (DataStores in game code)

Sources: creator-docs `cloud-services/data-stores/best-practices.md`,
`player-data-purchasing.md`, `error-codes-and-limits.md`. Recipe: `recipe-inventory`.

- **One key per player** (`"Player_" .. player.UserId`) in **few data stores**, with
  static key patterns. Don't create a data store per feature.
- **Load once, keep it in memory, save at the right moments**: when the player joins,
  update the server-side copy on every change (never a request per change), then save
  periodically (the docs' sample uses 180 s, with a random offset per server so servers
  don't save in sync), on `Players.PlayerRemoving`, in `game:BindToClose` (server
  shutdown), and right after purchases.
- **`UpdateAsync` for writes that depend on the stored value** or that several servers
  might make; `SetAsync` only for a new key or a value that doesn't depend on the old one.
- **Wrap every call in `pcall`** and retry transient failures with capped exponential
  backoff plus jitter; don't retry invalid requests. Process retries for a key in order:
  an old retry landing after a newer write overwrites it. A failed call may still have
  written.
- **Don't let a failed load become an empty save.** If loading fails, mark the player's
  data as not loaded and never save it (kick or retry), or the next save wipes their
  progress.
- **Session locking** stops two servers from holding the same player's data at once (item
  duplication, lost progress): write a lock into the key inside the same `UpdateAsync`
  that loads it, refuse to load while another server holds it, release it in the final
  save. The docs' player-data sample implements this; use it or an established module
  rather than inventing one for a game with trading or purchases.
- **Purchases** (`MarketplaceService.ProcessReceipt`): grant, record the `PurchaseId`, and
  save before returning `PurchaseGranted`, so a crash can't grant twice or lose a
  purchase.
- Validate before saving: only JSON-able values, no NaN/inf (`math.isfinite`), strings
  within limits. Stored text written by players must be filtered when shown (see
  `ui.md`).
- Test the save logic as a pure module locally (`run_tests`); inspect real entries with
  `datastore_read` (see `publishing.md`).
