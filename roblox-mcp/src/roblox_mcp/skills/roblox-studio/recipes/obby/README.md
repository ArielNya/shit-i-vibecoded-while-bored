# Recipe: obby

Stages with checkpoints, kill parts, a `Stage` leaderboard stat, respawn at the last
checkpoint. Code in files (Rojo), the course built in Studio, behaviour attached by
**tags**, so the level designer never touches scripts.

Files (type-check clean, specs pass; roblox-mcp's CI checks them):

- `src/shared/Stages.luau`: the rule "advance one stage at a time", pure, with
  `Stages.spec.luau`.
- `src/server/Obby.luau`: tags → behaviour: `Checkpoint` parts with a number attribute
  `Stage`, `KillPart` parts; `leaderstats.Stage`; respawn at the checkpoint.
- `src/server/init.server.luau`: the server entry.

Build the course with Studio's `execute_luau` (Edit, undoable) after syncing the code:

```lua
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local recording = ChangeHistoryService:TryBeginRecording("MCP: build obby")
local course = Instance.new("Folder")
course.Name = "Course"
for stage = 1, 5 do
	local platform = Instance.new("Part")
	platform.Name = "Checkpoint" .. stage
	platform.Size = Vector3.new(8, 1, 8)
	platform.Position = Vector3.new(0, 5 + stage * 4, stage * 14)
	platform.Anchored = true
	platform:SetAttribute("Stage", stage)
	platform:AddTag("Checkpoint")
	platform.Parent = course
	local lava = Instance.new("Part")
	lava.Name = "Lava" .. stage
	lava.Size = Vector3.new(8, 1, 6)
	lava.Position = platform.Position + Vector3.new(0, -6, -7)
	lava.Anchored = true
	lava.Color = Color3.fromRGB(255, 60, 0)
	lava:AddTag("KillPart")
	lava.Parent = course
end
course.Parent = workspace
if recording then
	ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
end
```

Check it: `start_stop_play`, `character_navigation` to `workspace.Course.Checkpoint1`,
`execute_luau` (Server) `return game.Players:GetPlayers()[1].leaderstats.Stage.Value`
→ 1, then walk into a lava part and confirm the respawn position.

Why this shape: the server decides stages (a client teleporting to the last checkpoint
gains nothing: `Stages.advance` only accepts the next one); tags instead of a script per
part; `task.defer` so the respawn move happens after Roblox places the character.
