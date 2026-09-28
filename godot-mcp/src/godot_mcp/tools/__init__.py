"""MCP tool definitions, grouped by area. Each module exposes register(mcp, godot)."""

from . import docs, edit, project, run, scene, script, view

# Toolset names for --toolsets / GODOT_MCP_TOOLSETS, in registration order.
TOOLSETS = {
    "project": project,
    "scene": scene,
    "edit": edit,
    "script": script,
    "docs": docs,
    "view": view,
    "run": run,
}

# Presets for clients with tool limits or slow tool routing: names of individual tools.
MINIMAL = [
    "get_project_info", "get_scene_tree", "get_node_properties", "read_script",
    "write_script", "edit_script", "get_diagnostics", "get_class_docs", "add_node",
    "set_node_properties", "save_scene", "run_project", "get_runtime_errors",
]  # fmt: skip
CORE = MINIMAL + [
    "list_files", "search_files", "search_docs", "open_scene", "new_scene", "remove_node",
    "create_script", "attach_script", "connect_signal", "edit_input_map", "undo",
    "get_editor_screenshot", "stop_project", "get_output", "get_live_properties",
    "send_input", "wait_for", "get_game_screenshot",
]  # fmt: skip
PRESETS = {"minimal": MINIMAL, "core": CORE}
