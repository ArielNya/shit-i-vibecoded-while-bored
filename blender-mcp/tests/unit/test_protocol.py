from pathlib import Path

import pytest

from blender_mcp import protocol

ROOT = Path(__file__).resolve().parents[2]


def test_encode_decode_roundtrip():
    msg = protocol.request(7, "get_scene_info", {"detail": True})
    frame = protocol.encode(msg)
    length = protocol.parse_header(frame[: protocol.HEADER.size])
    assert length == len(frame) - protocol.HEADER.size
    assert protocol.decode_body(frame[protocol.HEADER.size :]) == msg


def test_encode_falls_back_for_non_json_types():
    class Vec:  # stands in for mathutils.Vector
        def __iter__(self):
            return iter((1.0, 2.0, 3.0))

    frame = protocol.encode(protocol.result(1, {"loc": Vec(), "obj": object}))
    decoded = protocol.decode_body(frame[protocol.HEADER.size :])
    assert decoded["result"]["loc"] == [1.0, 2.0, 3.0]
    assert isinstance(decoded["result"]["obj"], str)


def test_rejects_oversized_header():
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_header(protocol.HEADER.pack(protocol.MAX_MESSAGE_BYTES + 1))


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b"\xff\xfe"])
def test_rejects_bad_bodies(body):
    with pytest.raises(protocol.ProtocolError):
        protocol.decode_body(body)


def test_addon_protocol_copy_is_in_sync():
    src = ROOT / "src" / "blender_mcp" / "protocol.py"
    vendored = ROOT / "addon" / "blender_mcp_addon" / "protocol.py"
    assert vendored.read_text() == src.read_text(), (
        "addon protocol.py is stale; run: python scripts/build_addon.py --sync"
    )
