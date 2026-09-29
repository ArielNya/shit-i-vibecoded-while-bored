# Exporting

1. **Presets** are made in the editor: *Project → Export → Add…* (Windows, Linux,
   macOS, Web, Android, iOS). They're saved in `export_presets.cfg`;
   `list_export_presets` shows them.
2. **Export templates** must be installed once per Godot version for release/debug
   builds: *Editor → Manage Export Templates → Download*. `list_export_presets` says
   whether they are.
3. **Export** with `export_project`:
   - `mode="release"` (default) or `"debug"`: a runnable build, needs templates.
   - `mode="pack"`: only the game data (`.pck`/`.zip`), no templates needed; useful to
     check the export works, or for patches/DLC.
   The output must be inside the server's export folders (default: its working
   directory).

## Common problems

- *No export template found*: install the templates (step 2), or use `mode="pack"`.
- Missing files in the build: the preset's resource filter (`export_filter`) excludes
  them, or they're loaded by a path built at runtime (`load("res://levels/" + name)`),
  which the exporter can't see. Add those folders to the preset's include filter.
- Web builds need a web server with the right headers (SharedArrayBuffer), or the
  "thread support" option off.
- The `godot_mcp` plugin is an editor tool: it's not needed in exports. Its runtime
  autoload is removed from exported games automatically; to leave its scripts out too,
  add `addons/godot_mcp/*` to the preset's exclude filter.

## Before exporting

Run `validate_project` and `run_tests` (if the project has tests): a build that
compiles in the editor can still fail on a missing file.
