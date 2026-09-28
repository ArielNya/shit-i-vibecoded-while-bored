-- roblox-mcp test harness: plain Luau, runs the same under Lune and inside Roblox.
-- A spec is a ModuleScript `*.spec.luau` that returns function(t), where t has
-- describe/test/expect. The runner prepends this file and calls runSpec per spec.

local function show(value: any): string
	if type(value) == "string" then
		return string.format("%q", value)
	end
	return tostring(value)
end

local function deepEqual(a: any, b: any): boolean
	if a == b then
		return true
	end
	if type(a) ~= "table" or type(b) ~= "table" then
		return false
	end
	for k, v in a do
		if not deepEqual(v, b[k]) then
			return false
		end
	end
	for k in b do
		if a[k] == nil then
			return false
		end
	end
	return true
end

local function expect(actual: any)
	local function fail(message: string)
		error(message, 3) -- level 3: the line in the spec that called the matcher
	end
	return {
		toBe = function(expected: any)
			if actual ~= expected then
				fail(`expected {show(expected)}, got {show(actual)}`)
			end
		end,
		toEqual = function(expected: any)
			if not deepEqual(actual, expected) then
				fail(`expected tables to be deeply equal (got {show(actual)})`)
			end
		end,
		toBeCloseTo = function(expected: number, digits: number?)
			local tolerance = 10 ^ -(digits or 2) / 2
			if type(actual) ~= "number" or math.abs(actual - expected) >= tolerance then
				fail(`expected {show(actual)} to be close to {expected}`)
			end
		end,
		toBeNil = function()
			if actual ~= nil then
				fail(`expected nil, got {show(actual)}`)
			end
		end,
		toBeTruthy = function()
			if not actual then
				fail(`expected a truthy value, got {show(actual)}`)
			end
		end,
		toThrow = function(substring: string?)
			local ok, err = pcall(actual)
			if ok then
				fail("expected the function to throw")
			elseif substring and not string.find(tostring(err), substring, 1, true) then
				fail(`expected an error containing {show(substring)}, got {show(err)}`)
			end
		end,
	}
end

-- Runs one spec function; appends {name, ok, error} records to results.
local function runSpec(specName: string, spec: any, filter: string, results: { any })
	local prefix = { specName }
	local t = { expect = expect }
	function t.describe(name: string, body: () -> ())
		table.insert(prefix, name)
		body()
		table.remove(prefix)
	end
	function t.test(name: string, body: () -> ())
		local full = table.concat(prefix, " > ") .. " > " .. name
		if filter ~= "" and not string.find(full, filter, 1, true) then
			return
		end
		local ok, err = pcall(body)
		table.insert(results, { name = full, ok = ok, error = if ok then nil else tostring(err) })
	end
	if type(spec) ~= "function" then
		table.insert(results, {
			name = specName,
			ok = false,
			error = "a spec must return function(t); this one returned " .. typeof(spec),
		})
		return
	end
	local ok, err = pcall(spec, t)
	if not ok then
		table.insert(results, { name = specName, ok = false, error = tostring(err) })
	end
end

local function loadFailed(specName: string, err: any, results: { any })
	table.insert(results, { name = specName, ok = false, error = "couldn't load: " .. tostring(err) })
end
