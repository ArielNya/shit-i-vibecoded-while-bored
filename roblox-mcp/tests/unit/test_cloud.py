"""Open Cloud operations against a fake server, and the opt-in gating."""

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from roblox_mcp import opencloud
from roblox_mcp.server import create_server, parse_args
from roblox_mcp.tools import cloud

TASK = "universes/1/places/2/luau-execution-sessions/s/tasks/t"
pytestmark = pytest.mark.anyio


class Fake(BaseHTTPRequestHandler):
    calls: list = []

    def log_message(self, *args):
        pass

    def reply(self, body):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def record(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        Fake.calls.append((self.command, self.path, self.headers.get("Content-Type"), body))

    def do_POST(self):
        self.record()
        if "/versions?versionType=" in self.path:
            self.reply({"versionNumber": 12})
        else:
            self.reply({"path": TASK, "state": "QUEUED"})

    def do_PATCH(self):
        self.record()
        self.reply({"id": "k", "revisionId": "r2", "etag": "e2"})

    def do_GET(self):
        self.record()
        path = urllib.parse.urlparse(self.path)
        if path.path.endswith("/entries/New"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"NOT_FOUND"}')
            return
        if path.path.endswith("/logs"):
            self.reply({"luauExecutionSessionTaskLogs": [{"messages": ["printed"]}]})
        elif TASK in path.path:
            self.reply({"path": TASK, "state": "COMPLETE", "output": {"results": [42]}})
        elif path.path.endswith("/data-stores"):
            self.reply({"dataStores": [{"id": "PlayerData"}, {"id": "Stats"}],
                        "nextPageToken": "p2"})  # fmt: skip
        elif path.path.endswith("/entries"):
            self.reply({"dataStoreEntries": [{"id": "Player_1"}, {"id": "Player_2"}]})
        else:
            self.reply({"id": "Player_1", "value": {"coins": 5}, "revisionId": "r1",
                        "etag": "e1", "users": ["users/1"], "path": "x"})  # fmt: skip


@pytest.fixture
def fake(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    Fake.calls = []
    monkeypatch.setenv(opencloud.BASE_ENV, f"http://127.0.0.1:{server.server_port}")
    for name, value in [("ROBLOX_API_KEY", "k"), ("ROBLOX_UNIVERSE_ID", "1"),
                        ("ROBLOX_PLACE_ID", "2"), ("ROBLOX_TEST_PLACE_ID", "3")]:  # fmt: skip
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(opencloud.time, "sleep", lambda s: None)
    yield
    server.shutdown()


def test_run_luau_on_the_latest_version(fake):
    out = cloud.run_script("return 6 * 7", "test", allow_live=False)
    assert out == {"state": "COMPLETE", "results": [42], "output": ["printed"]}
    method, path, _, body = Fake.calls[0]
    assert (method, path) == ("POST", "/cloud/v2/universes/1/places/3/luau-execution-session-tasks")
    assert json.loads(body)["script"] == "return 6 * 7"
    with pytest.raises(opencloud.CloudError, match="--allow-publish"):
        cloud.run_script("return 1", "live", allow_live=False)
    cloud.run_script("return 1", "live", allow_live=True)
    assert Fake.calls[-3][1] == "/cloud/v2/universes/1/places/2/luau-execution-session-tasks"


def test_datastores(fake):
    assert cloud.list_stores("", "", "") == {"data_stores": ["PlayerData", "Stats"],
                                             "next_page_token": "p2"}  # fmt: skip
    keys = cloud.list_stores("Player Data", "Player_", "tok")
    assert keys == {"store": "Player Data", "keys": ["Player_1", "Player_2"]}
    url = urllib.parse.urlparse(Fake.calls[-1][1])
    assert url.path == "/cloud/v2/universes/1/data-stores/Player%20Data/entries"
    query = urllib.parse.parse_qs(url.query)
    assert query["filter"] == ['id.startsWith("Player_")']
    assert (query["maxPageSize"], query["pageToken"]) == (["100"], ["tok"])
    entry = cloud.read_entry("PlayerData", "Player/1")
    assert entry == {"id": "Player_1", "value": {"coins": 5}, "revisionId": "r1", "etag": "e1",
                     "users": ["users/1"]}  # fmt: skip
    assert Fake.calls[-1][1].endswith("/data-stores/PlayerData/entries/Player%2F1")


def test_datastore_set_keeps_users_and_attributes(fake):
    out = cloud.set_entry("PlayerData", "Player_1", '{"coins": 10}', "e1")
    assert out == {"id": "k", "revisionId": "r2", "etag": "e2", "created": False}
    read, write = Fake.calls[-2], Fake.calls[-1]
    assert read[:2] == ("GET", "/cloud/v2/universes/1/data-stores/PlayerData/entries/Player_1")
    assert write[:2] == (
        "PATCH",
        "/cloud/v2/universes/1/data-stores/PlayerData/entries/Player_1?allowMissing=true",
    )
    # Open Cloud clears users/attributes that an update leaves out: they're carried over
    assert json.loads(write[3]) == {"value": {"coins": 10}, "users": ["users/1"], "etag": "e1"}
    created = cloud.set_entry("PlayerData", "New", "5", "")
    assert created["created"] is True
    assert json.loads(Fake.calls[-1][3]) == {"value": 5}
    with pytest.raises(ValueError, match="must be JSON"):
        cloud.set_entry("PlayerData", "Player_1", "coins: 10", "")


def test_publish_guards_and_uploads(fake, tmp_path):
    (tmp_path / "default.project.json").write_text(
        json.dumps({"tree": {"ServerScriptService": {}}})
    )
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "game.rbxl").write_bytes(b"<roblox!")
    with pytest.raises(ValueError, match="no world"):
        cloud.publish(tmp_path, "build/game.rbxl", "Published")
    (tmp_path / "saved").mkdir()
    (tmp_path / "saved" / "game.rbxlx").write_text("<roblox>")
    out = cloud.publish(tmp_path, "saved/game.rbxlx", "Published")
    assert out == {"place_id": "2", "version": 12, "type": "Published"}
    method, path, content_type, body = Fake.calls[-1]
    assert path == "/universes/v1/1/places/2/versions?versionType=Published"
    assert (content_type, body) == ("application/xml", b"<roblox>")
    with pytest.raises(ValueError, match="Saved"):
        cloud.publish(tmp_path, "saved/game.rbxlx", "Live")
    with pytest.raises(ValueError, match="not a .rbxl"):
        cloud.publish(tmp_path, "default.project.json", "Saved")


async def names(**flags):
    return {t.name for t in await create_server(**flags).list_tools()}


async def test_writes_are_opt_in(monkeypatch):
    base = await names()
    assert {"run_luau_cloud", "datastore_list", "datastore_read"} <= base
    assert not {"datastore_set", "publish_place"} & base
    assert await names(allow_datastore_writes=True) - base == {"datastore_set"}
    assert await names(allow_publish=True) - base == {"publish_place"}
    monkeypatch.setenv("ROBLOX_MCP_ALLOW_PUBLISH", "1")
    args = parse_args([])
    assert args.allow_publish and not args.allow_datastore_writes
    assert parse_args(["--allow-datastore-writes"]).allow_datastore_writes
