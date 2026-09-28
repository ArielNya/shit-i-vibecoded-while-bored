# Physics and characters

Sources: creator-docs `physics/mover-constraints.md`, `physics/network-ownership.md`,
`workspace/collisions.md`, `characters/pathfinding.md`.

## Physics

- **Anchor** everything that shouldn't move (level geometry, decorations). It's cheaper
  and can't be pushed or stolen by clients.
- Move things with **constraints**: `LinearVelocity`, `AngularVelocity`, `AlignPosition`,
  `AlignOrientation`, `VectorForce`. The `Body*` movers are deprecated. For scripted
  motion that ignores physics, tween or set `CFrame` on anchored parts (`PivotTo` for
  models).
- **Network ownership**: the server hands unanchored parts near a player to that client,
  which can then move them anywhere. For gameplay-critical parts,
  `part:SetNetworkOwner(nil)` (server) or anchor them, and validate on the server.
- **Collision groups**: `workspace:RegisterCollisionGroup("Projectiles")`,
  `workspace:CollisionGroupSetCollidable("Projectiles", "Players", false)`, then set
  `part.CollisionGroup = "Projectiles"`. The `PhysicsService` versions of these methods
  are deprecated.
- Exploiters can trigger `Touched` (and prompts, click detectors) from any distance: for
  damage or rewards, check distance and state on the server.

## Characters

- A player's character is `player.Character` (a `Model` with a `Humanoid` and
  `HumanoidRootPart`); it's replaced on every respawn, so connect to
  `player.CharacterAdded` and re-find parts each time. Use `WaitForChild` on the client,
  where parts may still be streaming in.
- Damage with `Humanoid:TakeDamage` (respects `ForceField`); react to death with
  `Humanoid.Died`.
- Animations: an `Animation` with `AnimationId`, loaded through the `Animator` inside the
  Humanoid (`animator:LoadAnimation(animation)`); `Humanoid:LoadAnimation` is deprecated.
- NPC movement: `PathfindingService:CreatePath()`, `path:ComputeAsync(from, to)`, walk
  the waypoints with `Humanoid:MoveTo` and `Humanoid.MoveToFinished`, and recompute when
  `path.Blocked` fires. Paths can fail; handle `path.Status`.
