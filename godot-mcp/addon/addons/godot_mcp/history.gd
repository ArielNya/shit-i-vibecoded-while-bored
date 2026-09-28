@tool
extends RefCounted
## The editor actions made through MCP, so the agent can undo/redo its own changes.
##
## EditorUndoRedoManager keeps one history per scene plus a global one, and has no
## public "undo whatever is newest" call. We remember (history id, action name) for each
## MCP action and only undo it while it is still the newest action in its history, so
## an agent never silently reverts something a human did afterwards.

const MAX_ENTRIES := 200

var done: Array[Dictionary] = []
var undone: Array[Dictionary] = []


func record(history_id: int, action_name: String) -> void:
	done.append({"history": history_id, "name": action_name})
	if done.size() > MAX_ENTRIES:
		done.remove_at(0)
	undone.clear()
