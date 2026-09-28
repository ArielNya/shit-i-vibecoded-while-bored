--!strict
-- Client entry: a status label that follows the round attributes the server sets.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local gui = Instance.new("ScreenGui")
gui.Name = "RoundStatus"
gui.ResetOnSpawn = false

local label = Instance.new("TextLabel")
label.AnchorPoint = Vector2.new(0.5, 0)
label.Position = UDim2.fromScale(0.5, 0.02)
label.Size = UDim2.fromScale(0.3, 0.06)
label.BackgroundTransparency = 0.4
label.TextScaled = true
label.Parent = gui

local TEXT = {
	Waiting = "Waiting for players",
	Intermission = "Next round in %ds",
	Playing = "Round: %ds left",
	Ended = "Round over",
}

local function refresh()
	local phase = ReplicatedStorage:GetAttribute("RoundPhase")
	local time = ReplicatedStorage:GetAttribute("RoundTime")
	local text = TEXT[phase :: string]
	if text then
		label.Text = string.format(text, if typeof(time) == "number" then time else 0)
	end
end

ReplicatedStorage:GetAttributeChangedSignal("RoundPhase"):Connect(refresh)
ReplicatedStorage:GetAttributeChangedSignal("RoundTime"):Connect(refresh)
refresh()
gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
