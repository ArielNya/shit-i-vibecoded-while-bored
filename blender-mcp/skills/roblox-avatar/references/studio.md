# In Roblox Studio

From the exported `.fbx` to something a character wears. Studio's built-in MCP server
(`Roblox_Studio`) covers the live session. roblox-mcp covers uploads, and its
`roblox-studio` skill has the rules for any Luau you write. Sources in creator-docs:
`avatar/rigid-accessories/import.md`, `avatar/accessory-fitting-tool.md`,
`art/accessories/creating-rigid/*`, `marketplace/publish-to-marketplace.md`.

## 1. Get the model into the place

- **By hand (preferred for avatar items):** File → Import 3D (the 3D Importer), pick
  the `.fbx`. For a rigid accessory, Rig Scale is Rthro for Normal, Rthro Narrow for
  Slender, or Default for Classic. The result is a `Model` with a `MeshPart` that has
  its texture set. Layered clothing comes in with its `WrapLayer` from the cages.
- **By tools:** roblox-mcp `upload_asset("hat.fbx")` → Studio `insert_asset(id)`. This
  uploads to the user's inventory (moderated, private), so only do it for the user's
  own designs, never for IP they don't own. Studio can't import a local file through
  MCP any other way.

## 2. Make the Accessory

**Accessory Fitting Tool (AFT)** is the documented way, and the Marketplace upload
checks its output:

1. Avatar tab → Accessory.
2. Pick the MeshPart. Choose **Accessory** (rigid) or **Clothing** (layered), then the
   asset type and body scale.
3. Test on bodies and animations. For rigid items, fit inside the bounding box: red
   means too big.
4. **Generate MeshPart Accessory.**

This is a UI tool, so ask the user to run it, or do step 2b for testing.

**2b. By script, for testing in a game** (`execute_luau`, Edit mode, undoable per
the `roblox-studio` skill). Rigid accessory; `handle_attachment_position` comes from
`check_roblox_asset`:

```lua
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local recording = ChangeHistoryService:TryBeginRecording("MCP: make accessory")
local ok, err = pcall(function()
	local mesh = workspace:FindFirstChild("UmbreonHat", true) :: MeshPart -- the imported MeshPart
	local accessory = Instance.new("Accessory")
	accessory.Name = "UmbreonHat"
	accessory.AccessoryType = Enum.AccessoryType.Hat

	local handle = mesh:Clone()
	handle.Name = "Handle"
	handle.Anchored = false
	handle.CanCollide = false
	handle.CanQuery = false
	handle.CanTouch = false
	handle.Massless = true
	handle.Material = Enum.Material.Plastic -- Marketplace: Plastic, opaque, white VertexColor
	handle.Transparency = 0

	local attachment = Instance.new("Attachment")
	attachment.Name = "HatAttachment" -- must match the body's attachment name
	attachment.Position = Vector3.new(0, -0.53, 0) -- handle_attachment_position
	attachment.Parent = handle
	handle.Parent = accessory
	accessory.Parent = game:GetService("ServerStorage")
end)
if recording then
	ChangeHistoryService:FinishRecording(recording,
		if ok then Enum.FinishRecordingOperation.Commit else Enum.FinishRecordingOperation.Cancel)
end
if not ok then error(err) end
```

Attachment names by type: HatAttachment, HairAttachment, FaceFrontAttachment,
NeckAttachment, BodyFrontAttachment, BodyBackAttachment, Left/RightShoulderAttachment,
Left/RightCollarAttachment, WaistFront/Center/BackAttachment. Keep the orientation at
0 for hats. If the item sits backwards, the model faced +Y in Blender. Fix it there
(the wearer faces -Y), not here.

## 3. Try it on

- Play test (`start_stop_play`), then in the Server datamodel run
  `humanoid:AddAccessory(ServerStorage.UmbreonHat:Clone())` on the player's character.
  Then `screen_capture`. `AddAccessory` welds the Handle's attachment to the body
  attachment with the same name.
- Or equip it on every spawn with a server script:
  `Players.PlayerAdded` → `CharacterAdded` → `Humanoid:AddAccessory(clone)`. Put the
  Accessory in ServerStorage.
- Layered clothing needs `StarterPlayer.LoadCharacterLayeredClothing` set to Enabled.
  For unskinned clothing, set the `WrapLayer.AutoSkin` to
  `Enum.WrapLayerAutoSkin.EnabledOverride`.
- For catalog items by id (not local files), use `HumanoidDescription` +
  `Humanoid:ApplyDescriptionAsync` (`ApplyDescription` is deprecated).

## 4. Sell or share it (only when the user asks)

- Right-click the generated Accessory → **Save to Roblox** → Avatar Item. Studio
  validates it: size, triangles, textures, attachments, cages, and no Scripts or extra
  Parts inside.
- Selling needs:
  - ID verification, plus Roblox Plus or Premium;
  - an upload fee and a publishing advance (Robux);
  - moderation, which can take up to a day.
- **IP:** only original designs, or ones the user holds a licence for. Fan items
  (Pokémon, anime, brands) are removed, and the account is penalised.
- A thumbnail and description come later on the Creator Hub. None of this can be done
  from Linux or without the user's account; hand it over with the checklist:
  - `check_roblox_asset` is ok;
  - the AFT generated the Accessory;
  - it's tested on Normal, Slender and Classic bodies;
  - the design is original.
