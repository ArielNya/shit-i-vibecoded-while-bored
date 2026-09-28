@tool
extends Node
## Localhost TCP server that the MCP server connects to.
##
## Polled from _process(), i.e. on the editor's main thread, so handlers can use the
## engine API directly. Each client gets one request at a time; handlers may `await`
## (filesystem scans, frames) without blocking the editor.

const Protocol := preload("protocol.gd")
const McpError := preload("mcp_error.gd")
const LogCapture := preload("log_capture.gd")

const MAX_CLIENTS := 8
const HANDSHAKE_TIMEOUT_MSEC := 5000
const LOG_SIZE := 50

signal status_changed
signal command_logged(line: String)

## method name -> Callable(params: Dictionary) -> Variant | McpError (may be a coroutine)
var handlers: Dictionary = {}
## Merged into the handshake reply.
var server_info: Dictionary = {}
## "" disables authentication.
var token := ""
var log_capture: LogCapture

var port := 0
var last_error := ""
var recent: Array[String] = []

var _server: TCPServer
var _clients: Array[Client] = []
var _next_client_id := 1


class Client:
	var id: int
	var peer: StreamPeerTCP
	var buffer := PackedByteArray()
	var authed := false
	var busy := false
	var connected_msec := 0

	func _init(p_id: int, p_peer: StreamPeerTCP) -> void:
		id = p_id
		peer = p_peer
		connected_msec = Time.get_ticks_msec()


func start(host: String, p_port: int) -> bool:
	stop()
	_server = TCPServer.new()
	var err := _server.listen(p_port, host)
	if err != OK:
		last_error = "Could not listen on %s:%d (%s). Is another editor using the port?" % [host, p_port, error_string(err)]
		push_warning("godot-mcp: " + last_error)
		_server = null
		status_changed.emit()
		return false
	port = _server.get_local_port()
	last_error = ""
	# Machine-readable line: the integration tests and scripts wait for it.
	print("godot-mcp: listening on %s:%d" % [host, port])
	status_changed.emit()
	return true


func stop() -> void:
	for c in _clients:
		c.peer.disconnect_from_host()
	_clients.clear()
	if _server != null:
		_server.stop()
		_server = null
		status_changed.emit()


func is_listening() -> bool:
	return _server != null and _server.is_listening()


func client_count() -> int:
	return _clients.size()


func _exit_tree() -> void:
	stop()


func _process(_delta: float) -> void:
	if _server == null:
		return
	while _server.is_connection_available():
		var peer := _server.take_connection()
		if _clients.size() >= MAX_CLIENTS:
			peer.put_data(Protocol.encode(Protocol.error(null, Protocol.INVALID_REQUEST, "too many clients")))
			peer.disconnect_from_host()
			continue
		peer.set_no_delay(true)
		_clients.append(Client.new(_next_client_id, peer))
		_next_client_id += 1
		status_changed.emit()

	var dropped := false
	for c in _clients.duplicate():
		if not _poll_client(c):
			c.peer.disconnect_from_host()
			_clients.erase(c)
			dropped = true
	if dropped:
		status_changed.emit()


## Returns false when the client should be dropped.
func _poll_client(c: Client) -> bool:
	c.peer.poll()
	var status := c.peer.get_status()
	if status == StreamPeerTCP.STATUS_ERROR or status == StreamPeerTCP.STATUS_NONE:
		return false
	if status != StreamPeerTCP.STATUS_CONNECTED:
		return true
	if not c.authed and Time.get_ticks_msec() - c.connected_msec > HANDSHAKE_TIMEOUT_MSEC:
		_send(c, Protocol.error(null, Protocol.UNAUTHORIZED, "handshake timed out"))
		return false
	var available := c.peer.get_available_bytes()
	if available > 0:
		var got: Array = c.peer.get_partial_data(available)
		if got[0] != OK:
			return false
		c.buffer.append_array(got[1])
	if c.busy or c.buffer.size() < 4:
		return true
	var length := Protocol.read_length(c.buffer)
	var limit := Protocol.MAX_MESSAGE_BYTES if c.authed else Protocol.MAX_UNAUTHENTICATED_BYTES
	if length > limit:
		_send(c, Protocol.error(null, Protocol.INVALID_REQUEST, "message too large (%d bytes)" % length))
		return false
	if c.buffer.size() < 4 + length:
		return true
	var body := c.buffer.slice(4, 4 + length)
	c.buffer = c.buffer.slice(4 + length)
	var json := JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK or not (json.data is Dictionary):
		_send(c, Protocol.error(null, Protocol.PARSE_ERROR, "invalid JSON message"))
		return c.authed
	_dispatch(c, json.data)
	return true


func _dispatch(c: Client, msg: Dictionary) -> void:
	c.busy = true
	var id: Variant = msg.get("id")
	if id is float and id == floorf(id):
		id = int(id)
	var method: Variant = msg.get("method")
	var params: Variant = msg.get("params", {})
	if params == null:
		params = {}
	var reply: Dictionary
	if not (method is String) or not (params is Dictionary):
		reply = Protocol.error(id, Protocol.INVALID_REQUEST, "expected {method: string, params: object}")
	elif method == Protocol.HANDSHAKE_METHOD:
		reply = _handshake(c, id, params)
	elif not c.authed:
		reply = Protocol.error(id, Protocol.UNAUTHORIZED, "handshake required")
	elif not handlers.has(method):
		reply = Protocol.error(id, Protocol.METHOD_NOT_FOUND, "unknown method '%s'" % method)
	else:
		reply = await _run_handler(id, method, params)
	if is_instance_valid(c.peer):
		_send(c, reply)
	c.busy = false


func _run_handler(id: Variant, method: String, params: Dictionary) -> Dictionary:
	var started := Time.get_ticks_msec()
	var mark: int = log_capture.mark() if log_capture != null else 0
	var handler: Callable = handlers[method]
	var value: Variant = await handler.call(params)
	var ms := Time.get_ticks_msec() - started
	if value is McpError:
		_log("%s ✗ %s" % [method, value.message])
		return Protocol.error(id, value.code, value.message, value.data)
	if value == null:
		# A GDScript runtime error aborts the handler and yields null; report what the
		# engine logged so the model (and the user) can see why.
		var logged: Array[Dictionary] = log_capture.errors_since(mark) if log_capture != null else []
		var details := "\n".join(logged.map(func(e: Dictionary) -> String: return "%s:%s: %s" % [e.get("file", ""), e.get("line", ""), e["message"]]))
		_log("%s ✗ internal error" % method)
		return Protocol.error(id, Protocol.HANDLER_ERROR, "Internal error in the Godot plugin while running '%s'." % method, details if details != "" else null)
	_log("%s ✓ %d ms" % [method, ms])
	return Protocol.result(id, value)


func _handshake(c: Client, id: Variant, params: Dictionary) -> Dictionary:
	var version: Variant = params.get("protocol_version")
	if not (version is float or version is int) or int(version) != Protocol.PROTOCOL_VERSION:
		return Protocol.error(id, Protocol.VERSION_MISMATCH, "protocol version mismatch: the MCP server speaks %s, the Godot plugin speaks %d. Update both to the same release." % [str(version), Protocol.PROTOCOL_VERSION])
	if token != "":
		var given: Variant = params.get("token")
		if not (given is String) or given.sha256_text() != token.sha256_text():
			_log("handshake ✗ bad token")
			return Protocol.error(id, Protocol.UNAUTHORIZED, "invalid or missing token")
	c.authed = true
	_log("client %d connected" % c.id)
	var info := server_info.duplicate()
	info["protocol_version"] = Protocol.PROTOCOL_VERSION
	return Protocol.result(id, info)


func _send(c: Client, message: Dictionary) -> void:
	if c.peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var data := Protocol.encode(message)
	if data.size() - 4 > Protocol.MAX_MESSAGE_BYTES:
		data = Protocol.encode(Protocol.error(message.get("id"), Protocol.HANDLER_ERROR, "result too large (%d bytes); ask for less (smaller limit/size)" % data.size()))
	c.peer.put_data(data)


func _log(line: String) -> void:
	recent.append("%s  %s" % [Time.get_time_string_from_system(), line])
	if recent.size() > LOG_SIZE:
		recent.remove_at(0)
	command_logged.emit(line)
