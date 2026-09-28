import os

import pytest

from godot_mcp.server import ENV, apply_to_environment, bridge_config, http_app, parse_args


def test_flags_win_over_environment(monkeypatch):
    monkeypatch.setenv("GODOT_MCP_PORT", "9999")
    monkeypatch.setenv("GODOT_MCP_TIMEOUT", "12")
    args = parse_args(["--godot-port", "9081"])
    config = bridge_config(args)
    assert (config.port, config.timeout) == (9081, 12.0)


def test_every_option_has_an_environment_variable(monkeypatch):
    for opt, env in ENV.items():
        monkeypatch.setenv(env, "7" if "port" in opt or opt == "timeout" else "x")
    args = parse_args([])
    assert all(getattr(args, opt) is not None for opt in ENV)


def test_flags_reach_modules_that_read_the_environment(monkeypatch, tmp_path):
    # apply_to_environment writes os.environ; register the keys so monkeypatch restores them.
    for env in ("GODOT_MCP_TOKEN_FILE", "GODOT_MCP_LSP_PORT", "GODOT_MCP_IMAGE_MODE"):
        monkeypatch.setenv(env, "")
    token = tmp_path / "tok"
    apply_to_environment(
        parse_args(["--token-file", str(token), "--lsp-port", "6010", "--image-mode", "file"])
    )
    assert os.environ["GODOT_MCP_TOKEN_FILE"] == str(token)
    assert os.environ["GODOT_MCP_LSP_PORT"] == "6010"
    assert os.environ["GODOT_MCP_IMAGE_MODE"] == "file"


def test_http_auth_rules(tmp_path, monkeypatch):
    from godot_mcp.server import create_server

    mcp = create_server()
    monkeypatch.setenv("GODOT_MCP_TOKEN_FILE", str(tmp_path / "missing"))
    with pytest.raises(SystemExit, match="bearer token"):
        http_app(mcp, parse_args(["--http"]))
    with pytest.raises(SystemExit, match="loopback"):
        http_app(mcp, parse_args(["--http", "--http-host", "0.0.0.0", "--no-http-auth"]))
    assert http_app(mcp, parse_args(["--http", "--http-token", "t"])).expected == b"Bearer t"
