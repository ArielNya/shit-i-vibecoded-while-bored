--!strict
local Stages = require("./Stages")

return function(t: any)
	t.describe("advance", function()
		t.test("moves to the next checkpoint", function()
			t.expect(Stages.advance(0, 1)).toBe(1)
		end)
		t.test("ignores skipped checkpoints", function()
			t.expect(Stages.advance(2, 10)).toBe(2)
		end)
		t.test("ignores earlier checkpoints", function()
			t.expect(Stages.advance(5, 3)).toBe(5)
		end)
	end)
end
