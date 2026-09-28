"""run_tests: spec discovery and the cloud flow against a fake Open Cloud server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from roblox_mcp import opencloud
from roblox_mcp.tools import tests

SAMPLE = Path(__file__).parent.parent / "fixtures" / "sample_game"
TASK = "universes/1/places/2/versions/7/luau-execution-sessions/s1/tasks/t1"


def test_specs_are_found_in_synced_folders():
    assert tests.find_specs(SAMPLE, "") == ["src/shared/Damage.spec"]
    assert tests.find_specs(SAMPLE, "src/server") == []


def test_luau_literals_and_error_cleanup():
    assert tests.lua_string('a "b"\n') == '"a \\"b\\"\\n"'
    root = Path("/games/x")
    err = "/games/x/src/a.spec:3: expected 1, got 2\nstack traceback:\n\t[C]: in ?"
    assert tests.clean(err, root) == "src/a.spec:3: expected 1, got 2"


class FakeCloud(BaseHTTPRequestHandler):
    calls: list = []
    task_state = "COMPLETE"
    spec = "ReplicatedStorage.Shared.Damage.spec"
    results = [
        [
            {"name": f"{spec} > a", "ok": True},
            {"name": f"{spec} > b", "ok": False, "error": f"{spec}:9: expected 0, got -20"},
        ]
    ]
    polls = 0

    def log_message(self, *args):
        pass

    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeCloud.calls.append(("POST", self.path, self.headers["x-api-key"],
                                self.headers["Content-Type"], body))  # fmt: skip
        if self.path.startswith("/universes/v1/1/places/2/versions"):
            self.reply({"versionNumber": 7})
        else:
            self.reply({"path": TASK, "state": "QUEUED"})

    def do_GET(self):
        FakeCloud.calls.append(("GET", self.path))
        if self.path.endswith("/logs"):
            self.reply({"luauExecutionSessionTaskLogs": [{"messages": ["hello from Roblox"]}]})
            return
        FakeCloud.polls += 1
        if FakeCloud.polls == 1:
            self.reply({"path": TASK, "state": "PROCESSING"})
        elif FakeCloud.task_state == "COMPLETE":
            self.reply({"path": TASK, "state": "COMPLETE", "output": {"results": self.results}})
        else:
            self.reply({"path": TASK, "state": "FAILED",
                        "error": {"code": "SCRIPT_ERROR", "message": "boom"}})  # fmt: skip


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    server = HTTPServer(("127.0.0.1", 0), FakeCloud)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeCloud.calls, FakeCloud.polls, FakeCloud.task_state = [], 0, "COMPLETE"
    monkeypatch.setenv(opencloud.BASE_ENV, f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("ROBLOX_API_KEY", "key123")
    monkeypatch.setenv("ROBLOX_UNIVERSE_ID", "1")
    monkeypatch.setenv("ROBLOX_TEST_PLACE_ID", "2")
    monkeypatch.setenv("ROBLOX_PLACE_ID", "99")
    monkeypatch.setattr(opencloud.time, "sleep", lambda s: None)

    def fake_build(root, output):
        (root / output).parent.mkdir(parents=True, exist_ok=True)
        (root / output).write_bytes(b"<roblox!place-bytes")
        return {"output": output, "bytes": 19}

    monkeypatch.setattr(tests, "build", fake_build)
    yield tmp_path
    server.shutdown()


def test_cloud_run_uploads_runs_and_reports(cloud):
    result = tests.run_cloud(cloud, "Damage")
    assert (result["passed"], result["failed"], result["place_version"]) == (1, 1, 7)
    assert result["failures"] == [
        "ReplicatedStorage.Shared.Damage.spec > b: "
        "ReplicatedStorage.Shared.Damage.spec:9: expected 0, got -20"
    ]
    assert result["output"] == ["hello from Roblox"]
    upload, create = FakeCloud.calls[0], FakeCloud.calls[1]
    assert upload == ("POST", "/universes/v1/1/places/2/versions?versionType=Saved", "key123",
                      "application/octet-stream", b"<roblox!place-bytes")  # fmt: skip
    assert create[1] == "/cloud/v2/universes/1/places/2/versions/7/luau-execution-session-tasks"
    body = json.loads(create[4])
    assert body["timeout"] == "300s" and 'local FILTER = "Damage"' in body["script"]
    assert "function runSpec" in body["script"]
    assert ("GET", f"/cloud/v2/{TASK}") in FakeCloud.calls
    assert FakeCloud.calls[-1] == ("GET", f"/cloud/v2/{TASK}/logs")


def test_cloud_failures_are_explained(cloud, monkeypatch):
    FakeCloud.task_state = "FAILED"
    with pytest.raises(opencloud.CloudError, match="FAILED.*SCRIPT_ERROR"):
        tests.run_cloud(cloud, "")
    monkeypatch.setenv("ROBLOX_TEST_PLACE_ID", "99")
    with pytest.raises(opencloud.CloudError, match="separate place"):
        tests.run_cloud(cloud, "")
    monkeypatch.delenv("ROBLOX_API_KEY")
    with pytest.raises(opencloud.CloudError, match="set ROBLOX_API_KEY"):
        tests.run_cloud(cloud, "")


def test_http_errors_carry_a_hint(monkeypatch):
    class Limited(FakeCloud):
        def do_POST(self):
            self.send_response(429)
            self.end_headers()
            self.wfile.write(b"slow down")

    server = HTTPServer(("127.0.0.1", 0), Limited)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(opencloud.BASE_ENV, f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("ROBLOX_API_KEY", "k")
    with pytest.raises(opencloud.CloudError, match="429 .rate limited.*slow down"):
        opencloud.save_place_version("1", "2", b"x")
    server.shutdown()
