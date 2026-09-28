@tool
extends RefCounted
## Returned by a handler instead of a result to report a failure to the MCP server.
## (GDScript has no exceptions, so handlers `return McpError.new("...")`.)

const Protocol := preload("protocol.gd")

var code: int
var message: String
var data: Variant


func _init(p_message: String, p_code: int = Protocol.HANDLER_ERROR, p_data: Variant = null) -> void:
	message = p_message
	code = p_code
	data = p_data

