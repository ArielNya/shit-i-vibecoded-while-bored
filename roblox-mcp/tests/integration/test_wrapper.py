"""--wrap-studio end to end: roblox-mcp as a separate process, wrapping a fake Studio MCP
server, driven by an MCP client (PLAN §9)."""

import json
import shutil
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from roblox_mcp import toolchain
from roblox_mcp.wrapper import RECORD_WRAP

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(toolchain.find("rojo") is None, reason="rojo not installed"),
]

FIXTURES = Path(__file__).parents[1] / "fixtures"
FAKE = f"{sys.executable} {FIXTURES / 'fake_studio_mcp.py'}"


@pytest.fixture
def game(tmp_path):
    shutil.copytree(FIXTURES / "sample_game", tmp_path / "game")
    return tmp_path / "game"


def client(game: Path, **env: str) -> Client:
    import os

    args = ["-m", "roblox_mcp.server", "--project", str(game), "--wrap-studio",
            "--studio-mcp", FAKE]  # fmt: skip
    return Client(StdioServerParameters(command=sys.executable, args=args,
                                        env={**os.environ, **env}))  # fmt: skip


def body(result) -> str:
    return "\n".join(c.text for c in result.content if hasattr(c, "text"))


async def call(c: Client, tool: str, args: dict) -> tuple[bool, str]:
    result = await c.call_tool(tool, args)
    return result.is_error, body(result)


async def test_both_servers_tools_are_listed(game):
    async with client(game) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert {"execute_luau", "multi_edit", "list_roblox_studios", "check_code"} <= names


async def test_multi_edit_on_rojo_scripts_is_refused(game):
    async with client(game) as c:
        error, text = await call(c, "multi_edit", {
            "studio_id": "s1", "path": "game.ReplicatedStorage.Shared.Damage",
            "edits": [], "datamodel_type": "Edit"})  # fmt: skip
        assert error and "src/shared/Damage.luau" in text and "overwritten" in text
        error, text = await call(c, "multi_edit", {
            "studio_id": "s1", "path": "game.ServerScriptService.Server.NewThing",
            "edits": [], "datamodel_type": "Edit"})  # fmt: skip
        assert error and "create the script as a file" in text and "src/server" in text
        error, text = await call(c, "multi_edit", {
            "studio_id": "s1", "path": "game.Workspace.Door.Script",
            "edits": [], "datamodel_type": "Edit"})  # fmt: skip
        assert not error and json.loads(text)["args"]["path"] == "game.Workspace.Door.Script"


async def test_edit_mode_luau_becomes_undoable(game):
    async with client(game) as c:
        _, text = await call(c, "execute_luau", {"studio_id": "s1", "code": "return 1",
                                                 "datamodel_type": "Edit"})  # fmt: skip
        sent = json.loads(text)["args"]["code"]
        assert sent == RECORD_WRAP.format(code="return 1")
        _, text = await call(c, "execute_luau", {"studio_id": "s1", "code": "return 1",
                                                 "datamodel_type": "Server"})  # fmt: skip
        assert json.loads(text)["args"]["code"] == "return 1"
        own = 'local r = game:GetService("ChangeHistoryService"):TryBeginRecording("x")'
        _, text = await call(c, "execute_luau", {"studio_id": "s1", "code": own,
                                                 "datamodel_type": "Edit"})  # fmt: skip
        assert json.loads(text)["args"]["code"] == own


async def test_studio_id_is_filled_or_asked_for(game):
    async with client(game) as c:  # one Studio: filled in
        _, text = await call(c, "script_read", {"path": "game.Workspace"})
        assert json.loads(text)["args"]["studio_id"] == "s1"
    studios = json.dumps([{"studio_id": "a", "place_id": 1}, {"studio_id": "b", "place_id": 2}])
    async with client(game, FAKE_STUDIOS=studios, ROBLOX_PLACE_ID="2") as c:
        _, text = await call(c, "script_read", {"path": "game.Workspace"})
        assert json.loads(text)["args"]["studio_id"] == "b"  # matches the project's place
    async with client(game, FAKE_STUDIOS=studios, ROBLOX_PLACE_ID="9") as c:
        error, text = await call(c, "script_read", {"path": "game.Workspace"})
        assert error and "several Studio windows" in text and "a (place 1)" in text


async def test_play_without_rojo_serving_warns(game):
    async with client(game) as c:
        error, text = await call(c, "start_stop_play", {"studio_id": "s1", "mode": "start"})
    assert not error and "Rojo isn't serving" in text and '"mode": "start"' in text


async def test_insert_asset_checks_moderation(game):
    manifest = {"assets/a.png": {"asset_id": 5, "moderation": "Rejected", "sha256": "x",
                                 "asset_type": "Image"},
                "assets/b.glb": {"asset_id": 6, "moderation": "Reviewing", "sha256": "y",
                                 "asset_type": "Model"}}  # fmt: skip
    (game / "assets.lock.json").write_text(json.dumps(manifest))
    async with client(game) as c:
        error, text = await call(c, "insert_asset", {"studio_id": "s1", "asset_id": 5})
        assert error and "rejected by moderation" in text
        error, text = await call(c, "insert_asset", {"studio_id": "s1", "asset_id": 6})
        assert not error and "still in moderation (Reviewing)" in text
        error, text = await call(c, "insert_asset", {"studio_id": "s1", "asset_id": 7})
        assert not error and "moderation" not in text


async def test_missing_studio_server_still_serves_ours(game):
    import os

    args = ["-m", "roblox_mcp.server", "--project", str(game), "--wrap-studio",
            "--studio-mcp", "/nonexistent/StudioMCP"]  # fmt: skip
    params = StdioServerParameters(command=sys.executable, args=args, env=dict(os.environ))
    async with Client(params) as c:
        names = {t.name for t in (await c.list_tools()).tools}
    assert "check_code" in names and "execute_luau" not in names


STUB = """
local log = {}
game = { GetService = function(_, name)
	return {
		TryBeginRecording = function(_, label)
			table.insert(log, "begin " .. label)
			return RECORDING
		end,
		FinishRecording = function(_, id, op)
			table.insert(log, "finish " .. tostring(id) .. " " .. op)
		end,
	}
end }
Enum = { FinishRecordingOperation = { Commit = "Commit", Cancel = "Cancel" } }
local function run(code)
	local chunk = require("@lune/luau").load(code)
	local results = table.pack(pcall(chunk))
	print(table.concat(log, ";"), results[1], results[2], results[3])
	table.clear(log)
end
"""


@pytest.mark.skipif(toolchain.find("lune") is None, reason="lune not installed")
@pytest.mark.parametrize("code, recording, expected", [
    ("return 1, 2", '"r1"', "begin MCP: execute_luau;finish r1 Commit true 1 2"),
    ('error("boom")', '"r1"', "begin MCP: execute_luau;finish r1 Cancel false"),
    ("return 5", "nil", "begin MCP: execute_luau true 5 nil"),  # playtest: not recording
])  # fmt: skip
def test_recording_wrapper_keeps_results_and_errors(tmp_path, code, recording, expected):
    import subprocess

    wrapped = RECORD_WRAP.format(code=code)
    (tmp_path / "t.luau").write_text(f"RECORDING = {recording}\n{STUB}\nrun([==[{wrapped}]==])\n")
    out = subprocess.run([toolchain.find("lune"), "run", "t.luau"], cwd=tmp_path,
                         capture_output=True, text=True, timeout=60)  # fmt: skip
    assert out.stdout.strip().startswith(expected), out.stdout + out.stderr
    if "boom" in code:
        assert "boom" in out.stdout
