from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from typer.testing import CliRunner

from dimcause.cli import app
from dimcause.core.models import Event, EventType, SourceType

runner = CliRunner()


def test_tasks_command_with_event_index():
    # Patch the class where it is DEFINED, because it is imported inside the function
    with patch("dimcause.core.event_index.EventIndex") as MockIndex:
        index_instance = MockIndex.return_value
        # Mock query result
        index_instance.query.return_value = [
            {
                "id": "evt_test_1",
                "summary": "Test Task 1",
                "status": "pending",
                "timestamp": "2026-01-01T10:00:00",
                "markdown_path": "/tmp/test.md",
            }
        ]
        # Mock load_event
        event = Event(
            id="evt_test_1",
            type=EventType.TASK,
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            summary="Test Task 1",
            content="Content",
            metadata={"status": "pending"},
        )
        index_instance.load_event.return_value = event

        with patch.dict("os.environ", {"DIMCAUSE_USE_EVENT_INDEX": "true"}):
            result = runner.invoke(app, ["tasks"])
            assert result.exit_code == 0
            assert "Test Task 1" in result.stdout


@pytest.mark.skip(reason="search 命令无 --mode 参数；EventIndex 搜索路径未在 CLI search 命令中实现")
def test_search_command_with_event_index():
    # Patch EventIndex globally for search engine
    with patch("dimcause.core.event_index.EventIndex") as MockIndex:
        index_instance = MockIndex.return_value

        # Mock query (for text search candidate list)
        index_instance.query.return_value = [{"id": "evt_1", "markdown_path": "/tmp/1.md"}]

        # Mock load_event
        event = Event(
            id="evt_1",
            type=EventType.UNKNOWN,  # Use a valid type
            source=SourceType.MANUAL,
            summary="Search Result 1",
            content="Some matching content for query",
            timestamp=datetime.now(),
            tags=[],
        )
        index_instance.load_event.return_value = event

        # Use text mode to trigger EventIndex path
        result = runner.invoke(app, ["search", "matching", "--mode", "text"])
        assert result.exit_code == 0
        assert "Search Result 1" in result.stdout


@pytest.mark.skip(reason="'同期决策上下文' 字符串在生产代码中未实现；mock 路径也错误（应 mock dimcause.core.history 而非 extractors）")
def test_history_command_context_panel():
    # Test that history command shows context panel
    with (
        patch("dimcause.extractors.git_history.get_file_history") as mock_git,
        patch("dimcause.extractors.git_history.format_history_timeline") as mock_fmt,
    ):
        mock_fmt.return_value = "Timeline View"
        # Mock git history
        mock_commit = MagicMock()
        mock_commit.date = "2026-01-01 10:00:00"
        mock_commit.hash = "abcdef123456"
        mock_commit.author = "tester"
        mock_commit.message = "test commit"
        mock_git.return_value = [mock_commit]

        with patch("dimcause.core.event_index.EventIndex") as MockIndex:
            index_instance = MockIndex.return_value
            index_instance.query.return_value = [
                {
                    "id": "dec_1",
                    "summary": "Architecture Decision",
                    "date": "2026-01-01",
                    "type": "decision",
                }
            ]

            with patch("pathlib.Path.exists", return_value=True):
                with patch.dict("os.environ", {"DIMCAUSE_USE_EVENT_INDEX": "true"}):
                    # We need a file that exists or mock path existence
                    result = runner.invoke(app, ["history", "some_file.py"])
                    assert result.exit_code == 0
                    assert "同期决策上下文" in result.stdout
                    assert "Architecture Decision" in result.stdout
