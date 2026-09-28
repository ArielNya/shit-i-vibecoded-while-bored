--!strict
local Inventory = require("./Inventory")

return function(t: any)
	t.describe("add", function()
		t.test("stacks up to the item's limit", function()
			local inventory = {}
			t.expect(Inventory.add(inventory, "Apple", 15)).toBe(true)
			t.expect(Inventory.add(inventory, "Apple", 5)).toBe(true)
			local ok, err = Inventory.add(inventory, "Apple", 1)
			t.expect(ok).toBe(false)
			t.expect(err).toBe("stack full")
			t.expect(inventory.Apple).toBe(20)
		end)
		t.test("refuses unknown items and bad counts", function()
			local inventory = {}
			t.expect((Inventory.add(inventory, "Dragon", 1))).toBe(false)
			t.expect((Inventory.add(inventory, "Coin", 0))).toBe(false)
			t.expect((Inventory.add(inventory, "Coin", 1.5))).toBe(false)
			t.expect(inventory).toEqual({})
		end)
	end)
	t.test("remove", function()
		local inventory = { Coin = 3 }
		t.expect(Inventory.remove(inventory, "Coin", 5)).toBe(false)
		t.expect(Inventory.remove(inventory, "Coin", 3)).toBe(true)
		t.expect(inventory.Coin).toBeNil()
	end)
	t.test("sanitize drops anything invalid", function()
		local dirty = { Coin = 10, Apple = 0 / 0, Sword = 5, Dragon = 1, [1] = 2, Gem = "x" }
		t.expect(Inventory.sanitize(dirty)).toEqual({ Coin = 10, Sword = 1 })
		t.expect(Inventory.sanitize("garbage")).toEqual({})
	end)
end
