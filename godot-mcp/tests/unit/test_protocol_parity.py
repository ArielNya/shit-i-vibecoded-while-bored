"""protocol.py and its GDScript twin protocol.gd must agree on every constant."""

import re
from pathlib import Path

from godot_mcp import protocol

GD = Path(__file__).resolve().parents[2] / "addon" / "addons" / "godot_mcp" / "protocol.gd"
CONST = re.compile(r"^const (\w+) := (.+)$", re.M)


def _gd_constants() -> dict:
    out = {}
    for name, expr in CONST.findall(GD.read_text()):
        out[name] = eval(expr, {})  # simple literals and integer arithmetic only
    return out


def test_constants_match():
    gd = _gd_constants()
    assert gd, "no constants parsed from protocol.gd"
    for name, value in gd.items():
        assert getattr(protocol, name) == value, name


def test_all_shared_constants_are_mirrored():
    gd = _gd_constants()
    shared = [n for n in dir(protocol) if n.isupper() and n not in ("HEADER",)]
    assert sorted(shared) == sorted(gd)
