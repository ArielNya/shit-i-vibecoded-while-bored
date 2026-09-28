--!strict
-- Pure checkpoint rules, testable without the engine.
local Stages = {}

-- A player may only advance one stage at a time: touching checkpoint 10 from stage 2
-- (a teleport exploit, or a fall onto a later platform) doesn't count.
function Stages.advance(current: number, touched: number): number
	if touched == current + 1 then
		return touched
	end
	return current
end

return Stages
