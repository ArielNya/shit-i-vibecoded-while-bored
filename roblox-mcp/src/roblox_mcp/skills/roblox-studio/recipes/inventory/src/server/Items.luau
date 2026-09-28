--!strict
-- Item givers (ProximityPrompts tagged "ItemGiver" with a string attribute "ItemId") and
-- the validated DropItem remote.
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Inventory = require(ReplicatedStorage.Shared.Inventory)
local PlayerData = require(script.Parent.PlayerData)

local ItemsServer = {}

local COOLDOWN = 0.25
local lastDrop: { [Player]: number } = {}

local function setUpGiver(instance: Instance)
	if not instance:IsA("ProximityPrompt") then
		return
	end
	instance.Triggered:Connect(function(player)
		local inventory = PlayerData.get(player)
		local itemId = instance:GetAttribute("ItemId")
		if inventory and typeof(itemId) == "string" then
			Inventory.add(inventory, itemId, 1)
		end
	end)
end

local function onDrop(player: Player, itemId: unknown, count: unknown)
	local now = os.clock()
	if now - (lastDrop[player] or 0) < COOLDOWN then
		return
	end
	lastDrop[player] = now
	if typeof(itemId) ~= "string" or #itemId > 32 then
		return
	end
	if typeof(count) ~= "number" or not math.isfinite(count) then
		return
	end
	local inventory = PlayerData.get(player)
	if inventory then
		Inventory.remove(inventory, itemId, count) -- checks the count and what they own
	end
end

function ItemsServer.start()
	for _, prompt in CollectionService:GetTagged("ItemGiver") do
		setUpGiver(prompt)
	end
	CollectionService:GetInstanceAddedSignal("ItemGiver"):Connect(setUpGiver)
	local remotes = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("Inventory")
	local drop = remotes:WaitForChild("DropItem") :: RemoteEvent
	drop.OnServerEvent:Connect(onDrop)
	game:GetService("Players").PlayerRemoving:Connect(function(player)
		lastDrop[player] = nil
	end)
end

return ItemsServer
