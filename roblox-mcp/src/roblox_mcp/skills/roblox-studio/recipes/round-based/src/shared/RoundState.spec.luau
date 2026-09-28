--!strict
local RoundState = require("./RoundState")

local CONFIG = { minPlayers = 2, intermission = 10, round = 30, ended = 5 }

return function(t: any)
	t.test("waits for enough players", function()
		local state = RoundState.step(RoundState.new(), 1, 1, CONFIG)
		t.expect(state.phase).toBe("Waiting")
		state = RoundState.step(state, 1, 2, CONFIG)
		t.expect(state).toEqual({ phase = "Intermission", timeLeft = 10 })
	end)
	t.test("runs a full cycle", function()
		local state = { phase = "Intermission", timeLeft = 1 } :: RoundState.State
		state = RoundState.step(state, 1, 3, CONFIG)
		t.expect(state).toEqual({ phase = "Playing", timeLeft = 30 })
		state = RoundState.step(state, 30, 3, CONFIG)
		t.expect(state.phase).toBe("Ended")
		state = RoundState.step(state, 5, 3, CONFIG)
		t.expect(state.phase).toBe("Intermission")
	end)
	t.test("ends the round early when too few are left", function()
		local state = { phase = "Playing", timeLeft = 20 } :: RoundState.State
		t.expect(RoundState.step(state, 1, 1, CONFIG).phase).toBe("Ended")
	end)
	t.test("counts down", function()
		local state = { phase = "Playing", timeLeft = 20 } :: RoundState.State
		t.expect(RoundState.step(state, 1.5, 4, CONFIG).timeLeft).toBeCloseTo(18.5)
	end)
end
