--!strict
-- The round loop as a pure state machine: Waiting → Intermission → Playing → Ended →
-- Intermission ... Time is passed in, so specs can step it without waiting.
local RoundState = {}

export type Phase = "Waiting" | "Intermission" | "Playing" | "Ended"
export type State = { phase: Phase, timeLeft: number }
export type Config = { minPlayers: number, intermission: number, round: number, ended: number }

local DEFAULT: Config = { minPlayers = 2, intermission = 15, round = 120, ended = 5 }
RoundState.DEFAULT = DEFAULT

function RoundState.new(): State
	return { phase = "Waiting", timeLeft = 0 }
end

-- Advances by dt seconds. `alive` is how many players are still in the round (or in the
-- server, outside of Playing). Returns the new state (the old one is not modified).
function RoundState.step(state: State, dt: number, alive: number, config: Config): State
	if state.phase ~= "Waiting" and state.phase ~= "Ended" and alive < config.minPlayers then
		if state.phase == "Playing" then
			return { phase = "Ended", timeLeft = config.ended }
		end
		return { phase = "Waiting", timeLeft = 0 }
	end
	if state.phase == "Waiting" then
		if alive >= config.minPlayers then
			return { phase = "Intermission", timeLeft = config.intermission }
		end
		return state
	end
	local timeLeft = state.timeLeft - dt
	if timeLeft > 0 then
		return { phase = state.phase, timeLeft = timeLeft }
	end
	if state.phase == "Intermission" then
		return { phase = "Playing", timeLeft = config.round }
	elseif state.phase == "Playing" then
		return { phase = "Ended", timeLeft = config.ended }
	end
	return { phase = "Intermission", timeLeft = config.intermission }
end

return RoundState
