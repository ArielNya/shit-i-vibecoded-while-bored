--!strict
-- Checkpoints and kill parts, driven by tags: tag a part "Checkpoint" and give it a
-- number attribute "Stage" (1, 2, 3, ...); tag hazards "KillPart". No scripts in parts.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Stages = require(ReplicatedStorage.Shared.Stages)

local Obby = {}

local stageOf: { [Player]: IntValue } = {}

local function playerFromHit(hit: BasePart): (Player?, Humanoid?)
	local character = hit.Parent
	if not character or not character:IsA("Model") then
		return nil, nil
	end
	local player = Players:GetPlayerFromCharacter(character)
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	if not player or not humanoid or humanoid.Health <= 0 then
		return nil, nil
	end
	return player, humanoid
end

local function checkpointFor(stage: number): BasePart?
	for _, part in CollectionService:GetTagged("Checkpoint") do
		if part:IsA("BasePart") and part:GetAttribute("Stage") == stage then
			return part
		end
	end
	return nil
end

local function setUpCheckpoint(instance: Instance)
	if not instance:IsA("BasePart") then
		return
	end
	instance.Touched:Connect(function(hit)
		local player = playerFromHit(hit)
		local stage = player and stageOf[player]
		local touched = instance:GetAttribute("Stage")
		if stage and typeof(touched) == "number" then
			stage.Value = Stages.advance(stage.Value, touched)
		end
	end)
end

local function setUpKillPart(instance: Instance)
	if not instance:IsA("BasePart") then
		return
	end
	instance.Touched:Connect(function(hit)
		local _, humanoid = playerFromHit(hit)
		if humanoid then
			humanoid.Health = 0
		end
	end)
end

local function onPlayerAdded(player: Player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats" -- shown on the player list
	local stage = Instance.new("IntValue")
	stage.Name = "Stage"
	stage.Parent = leaderstats
	leaderstats.Parent = player
	stageOf[player] = stage

	player.CharacterAdded:Connect(function(character)
		local checkpoint = checkpointFor(stage.Value)
		if checkpoint then
			-- after the character is placed at the default spawn, move it to its checkpoint
			task.defer(function()
				character:PivotTo(checkpoint.CFrame + Vector3.new(0, 4, 0))
			end)
		end
	end)
end

function Obby.start()
	for _, tag in { "Checkpoint", "KillPart" } do
		local setUp = if tag == "Checkpoint" then setUpCheckpoint else setUpKillPart
		for _, instance in CollectionService:GetTagged(tag) do
			setUp(instance)
		end
		CollectionService:GetInstanceAddedSignal(tag):Connect(setUp)
	end
	Players.PlayerAdded:Connect(onPlayerAdded)
	for _, player in Players:GetPlayers() do
		onPlayerAdded(player)
	end
	Players.PlayerRemoving:Connect(function(player)
		stageOf[player] = nil
	end)
end

return Obby
