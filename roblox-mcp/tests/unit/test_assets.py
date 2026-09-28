"""upload_asset against a fake Open Cloud Assets API."""

import email.parser
import email.policy
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from roblox_mcp import opencloud
from roblox_mcp.tools import assets


class FakeAssets(BaseHTTPRequestHandler):
    uploads: list = []
    polls = 0
    next_id = 1000

    def log_message(self, *args):
        pass

    def reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        assert self.path == "/assets/v1/assets" and self.headers["x-api-key"] == "key"
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw
        )
        parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
        request = json.loads(parts["request"].get_content())
        file = parts["fileContent"]
        FakeAssets.uploads.append({"request": request, "filename": file.get_filename(),
                                   "type": file.get_content_type(),
                                   "data": file.get_payload(decode=True)})  # fmt: skip
        FakeAssets.next_id += 1
        self.reply({"path": f"operations/op{FakeAssets.next_id}", "done": False})

    def do_GET(self):
        if self.path.startswith("/assets/v1/operations/"):
            FakeAssets.polls += 1
            asset_id = int(self.path.rsplit("op", 1)[1])
            response = {"assetId": str(asset_id),
                        "moderationResult": {"moderationState": "Reviewing"}}  # fmt: skip
            self.reply({"path": self.path, "done": True, "response": response})
        elif self.path.endswith("?readMask=moderationResult"):
            self.reply({"moderationResult": {"moderationState": "Approved"}})


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    server = HTTPServer(("127.0.0.1", 0), FakeAssets)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeAssets.uploads, FakeAssets.polls = [], 0
    monkeypatch.setenv(opencloud.BASE_ENV, f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("ROBLOX_API_KEY", "key")
    monkeypatch.setenv("ROBLOX_CREATOR_USER_ID", "42")
    monkeypatch.delenv("ROBLOX_CREATOR_GROUP_ID", raising=False)
    monkeypatch.setattr(opencloud.time, "sleep", lambda s: None)
    (tmp_path / "assets").mkdir()
    yield tmp_path
    server.shutdown()


def test_upload_then_reuse(cloud):
    glb = cloud / "assets" / "sword.glb"
    glb.write_bytes(b"glTF\x02\x00binary")
    first = assets.upload(cloud, "assets/sword.glb", "", "A sword", "")
    assert first["uri"] == f"rbxassetid://{first['asset_id']}" and not first["cached"]
    assert (first["asset_type"], first["moderation"]) == ("Model", "Reviewing")
    assert "insert_asset" in first["use"]
    sent = FakeAssets.uploads[0]
    assert sent["request"] == {"assetType": "Model", "displayName": "sword",
                               "description": "A sword",
                               "creationContext": {"creator": {"userId": 42}}}  # fmt: skip
    assert (sent["filename"], sent["type"], sent["data"]) == (
        "sword.glb",
        "model/gltf-binary",
        b"glTF\x02\x00binary",
    )
    # unchanged file: no second upload
    again = assets.upload(cloud, "assets/sword.glb", "", "", "")
    assert again["cached"] and again["asset_id"] == first["asset_id"]
    assert len(FakeAssets.uploads) == 1
    # changed file: uploaded again, manifest updated
    glb.write_bytes(b"glTF\x02\x00changed")
    changed = assets.upload(cloud, "assets/sword.glb", "", "", "")
    assert not changed["cached"] and changed["asset_id"] != first["asset_id"]
    manifest = json.loads((cloud / "assets.lock.json").read_text())
    assert manifest["assets/sword.glb"]["asset_id"] == changed["asset_id"]


def test_types_and_overrides(cloud):
    (cloud / "assets" / "icon.png").write_bytes(b"\x89PNG")
    (cloud / "assets" / "walk.rbxm").write_bytes(b"<roblox!")
    assert assets.upload(cloud, "assets/icon.png", "", "", "")["asset_type"] == "Image"
    anim = assets.upload(cloud, "assets/walk.rbxm", "", "", "Animation")
    assert anim["asset_type"] == "Animation" and "AnimationId" in anim["use"]
    assert FakeAssets.uploads[-1]["type"] == "model/x-rbxm"
    with pytest.raises(ValueError, match="uploaded as Image or Decal"):
        assets.upload(cloud, "assets/icon.png", "", "", "Audio")


def test_refusals(cloud, monkeypatch):
    (cloud / "notes.txt").write_text("hi")
    with pytest.raises(ValueError, match="can't upload .txt"):
        assets.upload(cloud, "notes.txt", "", "", "")
    with pytest.raises(ValueError, match="outside the project"):
        assets.upload(cloud, "../secret.png", "", "", "")
    big = cloud / "assets" / "huge.png"
    big.write_bytes(b"\0" * (assets.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="20 MB"):
        assets.upload(cloud, "assets/huge.png", "", "", "")
    (cloud / "assets" / "a.ogg").write_bytes(b"OggS")
    monkeypatch.delenv("ROBLOX_CREATOR_USER_ID")
    with pytest.raises(opencloud.CloudError, match="ROBLOX_CREATOR_USER_ID"):
        assets.upload(cloud, "assets/a.ogg", "", "", "")
    assert FakeAssets.uploads == []


def test_group_creator_and_listing(cloud, monkeypatch):
    monkeypatch.setenv("ROBLOX_CREATOR_GROUP_ID", "7")
    (cloud / "assets" / "hit.ogg").write_bytes(b"OggS")
    assets.upload(cloud, "assets/hit.ogg", "Hit", "", "")
    assert FakeAssets.uploads[0]["request"]["creationContext"] == {"creator": {"groupId": 7}}
    listed = assets.list_uploaded(cloud, refresh=False)["assets"]
    assert [(a["file"], a["moderation"], a["file_changed"]) for a in listed] == [
        ("assets/hit.ogg", "Reviewing", False)
    ]
    (cloud / "assets" / "hit.ogg").write_bytes(b"OggS2")
    refreshed = assets.list_uploaded(cloud, refresh=True)["assets"][0]
    assert (refreshed["moderation"], refreshed["file_changed"]) == ("Approved", True)
