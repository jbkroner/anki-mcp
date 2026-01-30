"""Pytest configuration and fixtures for Anki MCP tests."""

import pytest
from anki_mcp.anki_client import AnkiClient
from mock_anki import MockAnkiConnect


@pytest.fixture
async def mock_anki_server():
    """Start a mock AnkiConnect server for testing."""
    server = MockAnkiConnect()
    port = await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def anki_client(mock_anki_server):
    """Create an AnkiClient connected to the mock server."""
    url = f"http://127.0.0.1:{mock_anki_server.port}"
    client = AnkiClient(url=url)
    yield client
    await client.close()


@pytest.fixture
def test_deck_name():
    """Provide a consistent test deck name."""
    return "MCPTest::TestDeck"


@pytest.fixture
def mock_state(mock_anki_server):
    """Provide direct access to mock server state for test setup."""
    return mock_anki_server.state
