--!strict
-- Drives RoundState once a second: teleports players into the arena (parts tagged
-- "ArenaSpawn") when a round starts, back to the lobby (spawn locations) when it ends,
-- and publishes the phase and time on ReplicatedStorage attributes for the UI.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local RoundState = require(ReplicatedStorage.Shared.RoundState)

local Rounds = {}

local inRound: { [Player]: boolean } = {}

local function aliveCount(): number
	local count = 0
	for player in inRound do
		local character = player.Character
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		if humanoid and humanoid.Health > 0 then
			count += 1
		else
			inRound[player] = nil
		end
	end
	return count
end

local function startRound()
	local spawns = CollectionService:GetTagged("ArenaSpawn")
	for i, player in Players:GetPlayers() do
		local target = spawns[(i - 1) % math.max(#spawns, 1) + 1]
		if player.Character and target and target:IsA("BasePart") then
			player.Character:PivotTo(target.CFrame + Vector3.new(0, 4, 0))
			inRound[player] = true
		end
	end
end

local function endRound()
	for player in inRound do
		task.spawn(player.LoadCharacterAsync, player) -- respawns in the lobby
	end
	table.clear(inRound)
end

function Rounds.start(config: RoundState.Config?)
	local settings = config or RoundState.DEFAULT
	local state = RoundState.new()
	Players.PlayerRemoving:Connect(function(player)
		inRound[player] = nil
	end)
	task.spawn(function()
		while true do
			local alive = if state.phase == "Playing" then aliveCount() else #Players:GetPlayers()
			local nextState = RoundState.step(state, 1, alive, settings)
			if nextState.phase ~= state.phase then
				if nextState.phase == "Playing" then
					startRound()
				elseif state.phase == "Playing" then
					endRound()
				end
			end
			state = nextState
			ReplicatedStorage:SetAttribute("RoundPhase", state.phase)
			ReplicatedStorage:SetAttribute("RoundTime", math.ceil(state.timeLeft))
			task.wait(1)
		end
	end)
end

return Rounds
