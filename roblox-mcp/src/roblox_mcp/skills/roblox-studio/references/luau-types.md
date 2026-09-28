# Luau types

Sources: creator-docs `luau/type-checking.md`; `check_code` runs the same checker Studio
uses (new type solver).

- Start every script with `--!strict`. Modes: `--!strict` checks everything,
  `--!nonstrict` only annotated code, `--!nocheck` nothing.
- Annotate function parameters and returns; locals are usually inferred:
  `local function apply(health: number, amount: number): number`.
- Optional values: `number?`. Unions: `"Idle" | "Running"` (string literal types make
  good enums). Cast with `::` only when you know better than the checker:
  `character:WaitForChild("Humanoid") :: Humanoid`.
- Tables: `{ number }` (array), `{ [string]: number }` (map), `{ name: string, level: number }`
  (record). Export types from modules: `export type Item = { id: string, count: number }`,
  used as `Inventory.Item` after `require`.
- Instance types come from Roblox's definitions: `Player`, `Model`, `BasePart`;
  `FindFirstChild` returns `Instance?`, so narrow with `IsA`:
  `if part and part:IsA("BasePart") then ... end`.
- `require` with relative strings (`require("./Config")`) or instance paths; both are
  typed. Dynamic requires (a variable) can't be checked: avoid them.
- Remote arguments are `unknown` in spirit: annotate handler params as `unknown` or `any`
  and narrow with `typeof` before use (see `networking.md`).
