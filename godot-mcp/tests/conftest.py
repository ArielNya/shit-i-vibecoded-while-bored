import pytest

from godot_mcp import protocol


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def private_token_file(tmp_path, monkeypatch):
    """Never read or write the real ~/.config/godot-mcp/token in tests."""
    path = tmp_path / "godot-mcp" / "token"
    monkeypatch.setenv(protocol.TOKEN_FILE_ENV, str(path))
    return path
