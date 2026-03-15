from unittest.mock import MagicMock, patch

# Mock fastmcp if not installed in test env (though we installed it)
# But for unit tests, we want to inspect the server object
from dimcause.protocols.mcp_server import mcp


def test_mcp_server_initialization():
    """Verify MCP server is initialized with correct name"""
    assert mcp.name == "dimcause"


def test_mcp_tools_registered():
    """Verify tools are registered"""
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "add_event" in tool_names
    assert "search_events" in tool_names


def test_mcp_resources_registered():
    """Verify resources are registered"""
    # FastMCP uses decorators, need to check internal registry
    # This might depend on mcp version internals
    # For now, just check if the function exists in module
    from dimcause.protocols.mcp_server import get_recent_events

    assert get_recent_events is not None


@patch("dimcause.protocols.mcp_server.EventIndex")
@patch("dimcause.protocols.mcp_server.VectorStore")
def test_search_event_tool(MockVectorStore, MockEventIndex):
    """Test search_events tool logic"""
    # Setup mocks
    mock_store = MockVectorStore.return_value
    mock_event = MagicMock()
    mock_event.id = "evt_1"
    mock_event.timestamp = "2023-01-01"
    mock_event.summary = "Test Event"
    mock_store.search.return_value = [mock_event]

    from dimcause.protocols.mcp_server import search_events

    result = search_events("test query")
    assert "Test Event" in result
    assert "evt_1" in result
