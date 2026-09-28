# UI

Sources: creator-docs `ui/position-and-size.md`, `ui/on-screen-containers.md`,
`ui/list-flex-layouts.md`, `ui/text-filtering.md`.

## Layout that works on every device

- UI lives in a `ScreenGui` under `StarterGui` (copied into each player's `PlayerGui`).
  `ResetOnSpawn` defaults to `true` (the UI is rebuilt on every respawn); set it to `false`
  for persistent HUDs. `ScreenInsets` controls safe-area behaviour on notched devices.
- Size and position with **Scale** (`UDim2.fromScale`), not pixel Offset, so it fits
  phones and monitors. Keep proportions with `UIAspectRatioConstraint`; use `AnchorPoint`
  `(0.5, 0.5)` to center.
- Let layouts place things: `UIListLayout` (with `UIFlexItem` for flex sizing),
  `UIGridLayout`, `UIPadding`. Don't hand-position lists.
- Mobile: the default controls sit in the bottom-left and bottom-right corners; keep
  important UI and buttons out of them, and frequently used buttons within thumb reach.
- UI is client-side: build it with a client script. The server tells clients what to show
  through `RemoteEvent`s or replicated values/attributes; it never trusts what a UI
  button claims.
- Animate with `TweenService:Create`, not per-frame loops.

## Text filtering (required)

You must filter any text you display that you don't control: player-typed text (names
for pets or plots, signs, custom messages), text stored in data stores, generated words,
text from external servers. Roblox removes games that don't filter.

```lua
--!strict
-- server side: filter what one player typed before showing it to everyone
local TextService = game:GetService("TextService")

local function filterForEveryone(text: string, fromUserId: number): string?
	local ok, result = pcall(function()
		return TextService:FilterStringAsync(text, fromUserId)
	end)
	if not ok then
		return nil -- filtering failed: show nothing, not the raw text
	end
	local ok2, filtered = pcall(function()
		return result:GetNonChatStringForBroadcastAsync()
	end)
	return if ok2 then filtered else nil
end
```

Filter on the server, after validating the text (type, length). Chat goes through
`TextChatService`, which filters by itself; `TextFilterResult:GetChatForUserAsync` is
deprecated and returns an empty string.
