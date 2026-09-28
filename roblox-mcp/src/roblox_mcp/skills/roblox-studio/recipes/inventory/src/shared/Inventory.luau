--!strict
-- Pure inventory rules (no engine): stacks per item id, limited by the catalog.
local Items = require("./Items")

local Inventory = {}

export type Inventory = { [string]: number }

function Inventory.add(inventory: Inventory, itemId: string, count: number): (boolean, string?)
	local info = Items[itemId]
	if not info then
		return false, "unknown item"
	end
	if count < 1 or count ~= math.floor(count) then
		return false, "bad count"
	end
	local total = (inventory[itemId] or 0) + count
	if total > info.maxStack then
		return false, "stack full"
	end
	inventory[itemId] = total
	return true, nil
end

function Inventory.remove(inventory: Inventory, itemId: string, count: number): boolean
	local have = inventory[itemId] or 0
	if count < 1 or count ~= math.floor(count) or count > have then
		return false
	end
	inventory[itemId] = if have == count then nil else have - count
	return true
end

-- Loaded data is untrusted too (old versions, manual edits, bugs): keep only known items
-- with whole, finite, in-range counts.
function Inventory.sanitize(data: unknown): Inventory
	local clean: Inventory = {}
	if typeof(data) ~= "table" then
		return clean
	end
	for itemId, count in data :: { [unknown]: unknown } do
		local info = typeof(itemId) == "string" and Items[itemId :: string]
		if info and typeof(count) == "number" and math.isfinite(count) then
			local whole = math.floor(count)
			if whole >= 1 then
				clean[itemId :: string] = math.min(whole, info.maxStack)
			end
		end
	end
	return clean
end

return Inventory
