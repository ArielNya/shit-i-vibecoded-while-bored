# Performance

Sources: creator-docs `performance-optimization/improve.md`,
`workspace/streaming/index.md`.

- **Scripts**: don't do work every frame unless it must be (`RunService.Heartbeat` and
  friends run 60 times a second); spread big jobs with `task.wait()`; event-driven beats
  polling.
- **Physics**: anchor what doesn't need simulating; keep mechanisms simple; use simpler
  collision fidelity for meshes that don't need precise collisions.
- **Networking**: don't send large payloads through remotes in one go; don't replicate
  what clients don't need (keep server-only things in `ServerStorage`); use
  `UnreliableRemoteEvent` for frequent cosmetic updates.
- **Instance streaming** (`Workspace.StreamingEnabled`, on by default for new places;
  not settable from scripts): clients only
  have the part of the world near them. Client code must not assume a Workspace instance
  exists: `WaitForChild` (with a timeout) or react to `ChildAdded`. Per model,
  `ModelStreamingMode` controls it: `Atomic` streams a model all at once, `Persistent`
  keeps it always present (wait for `Workspace.PersistentLoaded` on the client).
- **Measure before optimizing**: the MicroProfiler and the Developer Console show where
  frame time goes. Ask the user to profile on a real device when it matters; Studio on a
  desktop hides mobile problems.
