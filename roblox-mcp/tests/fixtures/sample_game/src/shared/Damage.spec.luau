--!strict
local Damage = require("./Damage")

return function(t)
	t.describe("apply", function()
		t.test("subtracts the amount", function()
			t.expect(Damage.apply(100, 30)).toBe(70)
		end)
		t.test("never goes below zero", function()
			t.expect(Damage.apply(10, 30)).toBe(0)
		end)
	end)
end
