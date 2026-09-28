@tool
extends RefCounted
## Wire protocol shared with the MCP server (src/godot_mcp/protocol.py).
##
## JSON-RPC 2.0 messages, each prefixed with a 4-byte big-endian length. The constants
## here must match protocol.py; tests/unit/test_protocol_parity.py checks that.

const PROTOCOL_VERSION := 1
const DEFAULT_HOST := "127.0.0.1"
const DEFAULT_PORT := 9080

const MAX_MESSAGE_BYTES := 32 * 1024 * 1024
## Until a client has completed the handshake it only gets to send small messages.
const MAX_UNAUTHENTICATED_BYTES := 64 * 1024

# JSON-RPC error codes. -326xx are standard, -320xx are ours.
const PARSE_ERROR := -32700
const INVALID_REQUEST := -32600
const METHOD_NOT_FOUND := -32601
const INVALID_PARAMS := -32602
const HANDLER_ERROR := -32000
const UNAUTHORIZED := -32001
const VERSION_MISMATCH := -32002

const HANDSHAKE_METHOD := "handshake"

const TOKEN_FILE_ENV := "GODOT_MCP_TOKEN_FILE"


static func encode(message: Dictionary) -> PackedByteArray:
	var body := JSON.stringify(message, "", false).to_utf8_buffer()
	var n := body.size()
	var out := PackedByteArray([(n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])
	out.append_array(body)
	return out


static func read_length(buffer: PackedByteArray) -> int:
	return (buffer[0] << 24) | (buffer[1] << 16) | (buffer[2] << 8) | buffer[3]


static func result(id: Variant, value: Variant) -> Dictionary:
	return {"jsonrpc": "2.0", "id": id, "result": value}


static func error(id: Variant, code: int, message: String, data: Variant = null) -> Dictionary:
	var err := {"code": code, "message": message}
	if data != null:
		err["data"] = data
	return {"jsonrpc": "2.0", "id": id, "error": err}


# --- shared token file -------------------------------------------------------------------
#
# By default the plugin generates a random token and stores it in a file only this user can
# read; the MCP server reads the same file. Other accounts on the machine can reach the
# localhost port but not the file. Same locations as protocol.token_file_path() in Python.


static func token_file_path() -> String:
	var override := OS.get_environment(TOKEN_FILE_ENV)
	if override != "":
		return override
	var root := ""
	match OS.get_name():
		"Windows":
			root = OS.get_environment("APPDATA")
			if root == "":
				root = OS.get_environment("USERPROFILE")
		"macOS":
			root = OS.get_environment("HOME").path_join("Library/Application Support")
		_:
			root = OS.get_environment("XDG_CONFIG_HOME")
			if root == "":
				root = OS.get_environment("HOME").path_join(".config")
	return root.path_join("godot-mcp").path_join("token")


static func read_token_file(path: String = "") -> String:
	if path == "":
		path = token_file_path()
	if not FileAccess.file_exists(path):
		return ""
	return FileAccess.get_file_as_string(path).strip_edges()


## The token from the token file, creating the file with a new random token if needed.
static func ensure_token_file(path: String = "") -> String:
	if path == "":
		path = token_file_path()
	var existing := read_token_file(path)
	if existing != "":
		return existing
	var dir := path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var posix := OS.get_name() not in ["Windows", "UWP"]
	if posix:
		FileAccess.set_unix_permissions(dir, FileAccess.UNIX_READ_OWNER | FileAccess.UNIX_WRITE_OWNER | FileAccess.UNIX_EXECUTE_OWNER)
	var bytes := Crypto.new().generate_random_bytes(32)
	var token := Marshalls.raw_to_base64(bytes).replace("+", "-").replace("/", "_").replace("=", "")
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("godot-mcp: can't write token file %s (%s)" % [path, error_string(FileAccess.get_open_error())])
		return ""
	f.store_string(token + "\n")
	f.close()
	if posix:
		FileAccess.set_unix_permissions(path, FileAccess.UNIX_READ_OWNER | FileAccess.UNIX_WRITE_OWNER)
	return token
