from godot_mcp.tools.project import parse_value


def test_json_values_parse_and_other_text_stays_text():
    assert parse_value("800") == 800
    assert parse_value("true") is True
    assert parse_value("null") is None
    assert parse_value('"quoted"') == "quoted"
    assert parse_value("[1, 2]") == [1, 2]
    assert parse_value("My Game") == "My Game"
    assert parse_value("Vector2(1, 2)") == "Vector2(1, 2)"
    assert parse_value("") == ""
