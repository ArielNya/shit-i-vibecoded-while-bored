--!strict
local Damage = {}

function Damage.apply(health: number, amount: number): number
	return math.max(0, health - amount)
end

return Damage
