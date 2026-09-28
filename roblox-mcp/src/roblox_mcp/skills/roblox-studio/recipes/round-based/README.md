# Recipe: round-based game

A lobby and an arena: waits for enough players, intermission countdown, a timed round
(ends early when too few are left alive), a short end screen, repeat. A status label shows
the phase and time on every client.

Files (type-check clean, specs pass):

- `src/shared/RoundState.luau`: the loop as a pure state machine (`step(state, dt, alive,
  config)`), with `RoundState.spec.luau`. Change the rules here and test them with
  `run_tests` in a second, no Studio needed.
- `src/server/Rounds.luau`: drives it once a second, teleports players to parts tagged
  `ArenaSpawn`, respawns them in the lobby at the end, publishes `RoundPhase` and
  `RoundTime` as attributes on `ReplicatedStorage`.
- `src/client/init.client.luau`: the client entry (a Client-RunContext Script in
  `ReplicatedStorage`): builds the status label and follows the attributes.

No remotes: server → all clients state that everyone sees is simplest as replicated
attributes. Add a `RemoteEvent` only for things clients ask for (with validation, see
`networking.md`).

In Studio: a lobby with a `SpawnLocation`, an arena away from it with a few parts tagged
`ArenaSpawn` (`part:AddTag("ArenaSpawn")` in an undoable `execute_luau`). To play-test
with the 2-player minimum, use Studio's multi-client test, or pass
`{ minPlayers = 1, intermission = 5, round = 30, ended = 3 }` to `Rounds.start` while
testing alone.
