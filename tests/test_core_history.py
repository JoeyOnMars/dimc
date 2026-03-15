from unittest.mock import MagicMock, patch

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.history import get_file_history


@pytest.fixture
def mock_event_index():
    index = MagicMock(spec=EventIndex)
    return index


@patch("dimcause.core.history.run_git")
def test_history_with_context_aggregation(mock_run_git, mock_event_index):
    """
    Test that get_file_history can aggregate events from EventIndex.
    """
    # 1. Mock Git Output
    # Commit at 2026-01-02 12:00:00
    mock_run_git.return_value = (0, "abc1234|2026-01-02|dev|fix bug", "")

    # 2. Mock EventIndex Query
    # Event happened at 2026-01-02 (same day)
    mock_event = {
        "id": "evt_1",
        "date": "2026-01-02",
        "summary": "Decided to fix bug",
        "type": "decision",
    }
    mock_event_index.query.return_value = [mock_event]
    mock_event_index.get_by_file.return_value = None

    # 3. Call function with event_index
    # Note: verify that we can pass event_index to get_file_history
    commits = get_file_history("src/main.py", limit=1, event_index=mock_event_index)

    # 4. Verify Context
    assert len(commits) == 1
    commit = commits[0]

    # Check if events were attached (we expect GitCommit to have .context_events)
    # This requires updating GitCommit dataclass in implementation
    assert hasattr(commit, "context_events")
    assert len(commit.context_events) == 1
    assert commit.context_events[0]["id"] == "evt_1"

    # Verify query date range (heuristic: look back 1 day)
    mock_event_index.query.assert_called_once()
    kwargs = mock_event_index.query.call_args[1]
    assert kwargs["date_to"] == "2026-01-02"
    assert kwargs["date_from"] == "2026-01-01"  # Assuming 1 day lookback logic


@patch("dimcause.core.history.run_git")
def test_history_without_context(mock_run_git):
    """Verify backward compatibility when no EventIndex is provided."""
    mock_run_git.return_value = (0, "def456|2026-01-01|dev|init", "")

    commits = get_file_history("src/main.py")

    assert len(commits) == 1
    commit = commits[0]
    # Should still have the field but empty
    assert hasattr(commit, "context_events")
    assert commit.context_events == []
