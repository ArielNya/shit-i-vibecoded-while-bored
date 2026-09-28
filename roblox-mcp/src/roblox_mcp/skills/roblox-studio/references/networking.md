# Networking and security

Sources: creator-docs `scripting/events/remote.md`,
`scripting/security/security-tactics.md`, `scripting/security/client-server-boundary.md`,
`scripting/security/network-ownership.md` (Studio 0.740). Check exact signatures with
`get_api_docs RemoteEvent` etc.

## Which remote

| Need | Use |
| --- | --- |
| Client asks the server to do something | `RemoteEvent`: client `FireServer(...)`, server `OnServerEvent:Connect(function(player, ...))`. The first argument is always the real `Player`; everything after it is untrusted |
| Server tells one / all clients | `RemoteEvent`: `FireClient(player, ...)` / `FireAllClients(...)`, client `OnClientEvent` |
| Frequent, loss-tolerant updates (cosmetic positions, effects) | `UnreliableRemoteEvent`: unordered, may drop, payload over 1000 bytes is dropped |
| Client needs an answer | `RemoteFunction`: client `InvokeServer(...)`, server sets `OnServerInvoke` (only the last assignment counts) |
| Server needs an answer from a client | avoid `InvokeClient`: a client error errors the server, a disconnect errors, and a client that never returns makes the server wait forever. Use a `RemoteEvent` each way |
| Same side, script to script | a `BindableEvent`, or better a module function call |

Create remotes ahead of time (in the place, or as a Rojo `.model.json` in
`ReplicatedStorage`), not at runtime from both sides.

## What survives the trip

- Tables are **copied**: identity and metatables are lost.
- Mixed tables (numeric and string keys) and `nil` holes break; send either an
  array or a dictionary. Non-string keys become strings.
- Functions arrive as `nil`.
- Instances the receiver can't see (e.g. anything in `ServerStorage` sent to a
  client, or a part a client created locally sent to the server) arrive as `nil`.

## Never trust the client

An exploiter controls their client completely. They can:

- read (decompile) every replicated `LocalScript` and `ModuleScript`;
- fire any remote, at any rate, with any arguments;
- move their character anywhere and take network ownership of unanchored parts
  near them;
- fire `Touched`, `ProximityPrompt` and `ClickDetector` interactions from any
  distance;
- change anything in their own DataModel.

So the server owns every rule and every piece of state that matters (currency,
inventory, health, progress, cooldowns). The client renders and sends *requests*.

### Validating a remote, every time

```lua
--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Remotes = ReplicatedStorage.Remotes

local COOLDOWN = 0.5
local MAX_RANGE = 12
local lastUse: { [Player]: number } = {}

Remotes.Combat.Attack.OnServerEvent:Connect(function(player: Player, target: unknown)
	-- 1. rate limit per player
	local now = os.clock()
	if now - (lastUse[player] or 0) < COOLDOWN then
		return
	end
	lastUse[player] = now

	-- 2. type and structure: the right kind of instance, in the expected place
	if typeof(target) ~= "Instance" or not target:IsA("Model")
		or not target:IsDescendantOf(workspace.Enemies) then
		return
	end

	-- 3. context: is the player able to do this right now?
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	local enemyRoot = target:FindFirstChild("HumanoidRootPart")
	if not (root and root:IsA("BasePart") and enemyRoot and enemyRoot:IsA("BasePart")) then
		return
	end
	if (root.Position - enemyRoot.Position).Magnitude > MAX_RANGE then
		return
	end

	-- 4. only now act, using server-side values (damage comes from the server, not the client)
	local humanoid = target:FindFirstChildOfClass("Humanoid")
	if humanoid then
		humanoid:TakeDamage(10)
	end
end)

game:GetService("Players").PlayerRemoving:Connect(function(player)
	lastUse[player] = nil
end)
```

Checklist for every handler:

1. **Rate limit** per player (timestamp or token bucket); clean up on `PlayerRemoving`.
2. **Type**: `typeof(x) == "number"` / `"string"` / `"Vector3"` / `"Instance"`, then
   `:IsA(...)` and `:IsDescendantOf(...)` for instances. Never let the client name an
   arbitrary instance or path for the server to modify, delete or `require`.
3. **Numbers**: reject NaN and infinity with `math.isfinite(n)` (NaN passes
   `typeof` and fails every comparison, so range checks silently let it through).
   Check each component of a `Vector3`. Then range-check. Integers:
   `n == math.floor(n)`.
4. **Strings**: length limit; match against known values instead of using them as keys
   blindly.
5. **Context / permission**: owns the item, has the currency, is close enough, is
   alive, the round is running.
6. **Act with server data**: prices, damage, rewards come from server tables, never
   from arguments.

## Physics and ownership

The server hands unanchored parts near a player to that player's client
(network ownership) so physics feels responsive; that client can then move them
anywhere. Anchor anything gameplay-critical, or set ownership to the server with
`BasePart:SetNetworkOwner(nil)`, and validate movement on the server when it
matters (speed and teleport checks).
