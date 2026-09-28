--!strict
-- The item catalog: the only item ids that exist. The server checks everything against it.
export type ItemInfo = { name: string, maxStack: number }

local Items: { [string]: ItemInfo } = {
	Coin = { name = "Coin", maxStack = 999 },
	Apple = { name = "Apple", maxStack = 20 },
	Sword = { name = "Sword", maxStack = 1 },
}

return Items
