--!strict
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Damage = require(ReplicatedStorage.Shared.Damage)

print("health after hit:", Damage.apply(100, 30))
