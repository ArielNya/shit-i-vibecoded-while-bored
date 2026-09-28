--!strict
-- Loads each player's inventory when they join, keeps it in memory, saves it on leave,
-- on shutdown and every few minutes. Never saves data that failed to load.
-- One server holds a player's data while they're in it. For trading or purchases, add
-- session locking (see references/data.md).
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Inventory = require(ReplicatedStorage.Shared.Inventory)

local STORE = DataStoreService:GetDataStore("PlayerData")
local SAVE_INTERVAL = 180
local ATTEMPTS = 4

local PlayerData = {}

local loaded: { [Player]: Inventory.Inventory } = {}

local function key(player: Player): string
	return "Player_" .. player.UserId
end

-- pcall with capped exponential backoff and jitter
local function retry<T>(attempt: () -> T): (boolean, T | string)
	local lastError = ""
	for i = 1, ATTEMPTS do
		local ok, result = pcall(attempt)
		if ok then
			return true, result
		end
		lastError = tostring(result)
		if i < ATTEMPTS then
			task.wait(math.min(2 ^ i, 16) + math.random())
		end
	end
	return false, lastError
end

local function load(player: Player)
	local ok, data = retry(function()
		return STORE:GetAsync(key(player))
	end)
	if not ok then
		warn(`couldn't load {player.Name}'s data: {data}`)
		player:Kick("Your data couldn't load. Please rejoin.")
		return
	end
	if player.Parent then -- still in the server
		loaded[player] = Inventory.sanitize(data)
	end
end

local function save(player: Player)
	local inventory = loaded[player]
	if not inventory then
		return -- never loaded: saving would overwrite their real data
	end
	local ok, err = retry(function()
		-- The whole inventory replaces the stored one (it doesn't depend on the old value),
		-- the case the docs give for SetAsync. Two servers writing one key needs session
		-- locking through UpdateAsync instead (references/data.md).
		return STORE:SetAsync(key(player), inventory)
	end)
	if not ok then
		warn(`couldn't save {player.Name}'s data: {err}`)
	end
end

function PlayerData.get(player: Player): Inventory.Inventory?
	return loaded[player]
end

function PlayerData.start()
	Players.PlayerAdded:Connect(load)
	for _, player in Players:GetPlayers() do
		task.spawn(load, player)
	end
	Players.PlayerRemoving:Connect(function(player)
		save(player)
		loaded[player] = nil
	end)
	game:BindToClose(function()
		local pending = 0
		for player in loaded do
			pending += 1
			task.spawn(function()
				save(player)
				pending -= 1
			end)
		end
		while pending > 0 do
			task.wait()
		end
	end)
	task.spawn(function()
		task.wait(math.random() * SAVE_INTERVAL) -- servers don't all save at once
		while true do
			for player in loaded do
				task.spawn(save, player)
			end
			task.wait(SAVE_INTERVAL)
		end
	end)
end

return PlayerData
