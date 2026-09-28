# Testing

`run_tests` (roblox-mcp) runs `*.spec.luau` files. Specs use a small harness that
roblox-mcp provides, so the same spec runs in both places:

| target | Runs on | Good for | Needs |
| --- | --- | --- | --- |
| `local` (default) | Lune, on this machine, in about a second | pure logic modules: math, inventories, state machines, parsers | the toolchain (`lune`) |
| `cloud` | a real headless Roblox server (Open Cloud Luau Execution) | anything using the engine: `Instance`, `Vector3`, services, physics, DataStores (in a test place) | `ROBLOX_API_KEY`, `ROBLOX_UNIVERSE_ID`, `ROBLOX_TEST_PLACE_ID` |

Local runs have no Roblox engine: `game`, `Instance`, `Vector3`, `CFrame`, services and
`task` are missing. Keep game logic in modules that take plain values, and test those
locally; test engine glue in the cloud.

## Writing a spec

Put the spec next to the module: `src/shared/Damage.luau` →
`src/shared/Damage.spec.luau`. It returns a function that receives the harness `t`:

```lua
--!strict
local Damage = require("./Damage")

return function(t)
	t.describe("apply", function()
		t.test("subtracts the amount", function()
			t.expect(Damage.apply(100, 30)).toBe(70)
		end)
		t.test("never goes below zero", function()
			t.expect(Damage.apply(10, 30)).toBe(0)
		end)
	end)
end
```

- **Require with relative string paths** (`"./Damage"`, `"../Shared/Config"`). Roblox
  resolves them from the script's position in the DataModel, Lune from the file's position
  on disk; with Rojo the two match. Instance paths
  (`require(ReplicatedStorage.Shared.Damage)`) only work in Roblox.
- Matchers: `toBe` (`==`), `toEqual` (deep table equality), `toBeCloseTo(n, digits?)`,
  `toBeNil`, `toBeTruthy`, `toThrow(substring?)` (on a function:
  `t.expect(function() ... end).toThrow("bad")`).
- A failure reports the spec line: `src/shared/Damage.spec:10: expected 0, got -20`.
- `filter` runs only tests whose full name (`spec > describe > test`) contains the text.

## Cloud runs

`run_tests target="cloud"` builds the place (`rojo build`), uploads it as a **saved**
(not published) version of `ROBLOX_TEST_PLACE_ID`, and runs every ModuleScript named
`*.spec` in a headless server. Rules:

- The test place must be a separate place from the real game (the tool refuses when
  `ROBLOX_TEST_PLACE_ID` equals `ROBLOX_PLACE_ID`): each run adds a version to it.
- The API key needs the scopes `universe-places:write`,
  `universe.place.luau-execution-session:write` and `:read` for that experience.
- Open Cloud allows 5 runs per minute per key owner, and 5 minutes per run. Batch fixes
  before re-running.
- `print` output from the run comes back as `output`.

Specs sync into the place like any other module (that's how cloud runs find them). To
keep them out of the published game, publish from a project file with
`"globIgnorePaths": ["**/*.spec.luau"]`.
