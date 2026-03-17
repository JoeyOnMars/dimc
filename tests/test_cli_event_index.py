from datetime import datetime
from unittest.mock import patch

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
