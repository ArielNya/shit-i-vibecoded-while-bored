"""Every tool must be usable from every major MCP client (PLAN §6), and every option
must work as a flag and as an environment variable."""

import pytest

from roblox_mcp import compat
from roblox_mcp.server import ENV, create_server, http_app, parse_args

pytestmark = pytest.mark.anyio


async def test_every_tool_is_portable_to_every_client():
    listed = await create_server().list_tools()
    assert {t.name for t in listed} == {
        "get_project_info", "init_project", "build_place", "sync_status",
        "check_code", "format_code", "run_tests", "upload_asset", "list_uploaded_assets",
        "get_api_docs", "search_api", "read_guide",
    }  # fmt: skip
    assert {t.name: compat.problems(t) for t in listed if compat.problems(t)} == {}


async def test_get_project_info_over_mcp(tmp_path):
    result = await create_server(tmp_path).call_tool("get_project_info", {})
    assert '"mode": "studio"' in str(result)


def test_every_option_has_an_environment_variable(monkeypatch):
    for opt, env in ENV.items():
        monkeypatch.setenv(env, "7" if "port" in opt else "x")
    args = parse_args([])
    assert all(getattr(args, opt) is not None for opt in ENV)
    monkeypatch.setenv("ROBLOX_MCP_PROJECT", "/env")
    assert parse_args(["--project", "/flag"]).project == "/flag"


def test_http_auth_rules(monkeypatch):
    monkeypatch.delenv("ROBLOX_MCP_HTTP_TOKEN", raising=False)
    mcp = create_server()
    with pytest.raises(SystemExit, match="bearer token"):
        http_app(mcp, parse_args(["--http"]))
    with pytest.raises(SystemExit, match="loopback"):
        http_app(mcp, parse_args(["--http", "--http-host", "0.0.0.0", "--no-http-auth"]))
    assert http_app(mcp, parse_args(["--http", "--http-token", "t"])).expected == b"Bearer t"
