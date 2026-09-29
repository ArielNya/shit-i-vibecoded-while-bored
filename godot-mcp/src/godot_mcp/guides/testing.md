# Testing a Godot project

## Quick checks, no test framework needed

- `validate_project`: every script compiles and every scene/resource loads; missing
  files, main scene and autoloads are reported. Run it after a batch of changes.
- `get_diagnostics`: errors and warnings for GDScript files (editor needed).
- `run_project` + `get_runtime_errors`: script errors while the game runs.

## Unit tests

`run_tests` runs **GUT** (`addons/gut`) or **GdUnit4** (`addons/gdUnit4`) headless and
returns pass/fail counts and failures with file:line. Install either from the Asset
Library (the user does this, or copy the addon folder in). Tests live in `res://test/`.

### GUT

Files named `test_*.gd`, extending `GutTest`, methods named `test_*`:

```gdscript
extends GutTest


func test_damage_reduces_health() -> void:
	var health := 3
	health -= 1
	assert_eq(health, 2)


func test_array_contains() -> void:
	assert_has([1, 2, 3], 2)
```

Useful asserts: `assert_eq`, `assert_ne`, `assert_true`, `assert_almost_eq`,
`assert_has`, `assert_null`, `assert_signal_emitted` (after `watch_signals(obj)`).
Nodes you create: `add_child_autofree(node)` so they're freed after the test.

### GdUnit4

Files named `*_test.gd`, extending `GdUnitTestSuite`:

```gdscript
extends GdUnitTestSuite


func test_damage_reduces_health() -> void:
	var health := 3
	health -= 1
	assert_int(health).is_equal(2)
```

### What to test

Game logic kept in plain scripts or resources (score, inventory, damage rules, state
machines) is the easiest to test. Load the script with `load("res://...gd").new()` in
the test, call its methods, assert the results. For nodes, instance the scene with
`load("res://x.tscn").instantiate()`, add it to the tree (`add_child_autofree` in GUT,
`auto_free` in GdUnit4), and `await` frames if it needs `_ready`/physics.

## Play-testing (no framework)

`run_project`, then `send_input` / `wait_for` / `get_live_properties` checks behaviour
the way a player would; `get_game_screenshot` to look at it.
