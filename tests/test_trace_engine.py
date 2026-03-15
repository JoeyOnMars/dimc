from datetime import datetime
from unittest.mock import ANY, MagicMock, patch

import pytest

from dimcause.core.trace import TraceNode, TraceService


@pytest.fixture
def mock_index():
    return MagicMock()


@pytest.fixture
def trace_service(mock_index):
    return TraceService(index=mock_index)


def test_find_files(trace_service):
    query = "test_query"

    with patch("subprocess.run") as mock_run:
        # Mock successful git grep
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "src/foo.py:12:def test_query():\nsrc/bar.py:8:test_query = True"
        mock_run.return_value = mock_process

        files = trace_service._find_files(query)

        assert files[0].path == "src/foo.py"
        assert files[0].line_start == 12
        assert files[0].summary == "def test_query():"
        assert files[1].path == "src/bar.py"
        mock_run.assert_called_with(
            ["git", "grep", "-n", "-I", "-F", query, "--", "src", "docs", "tests"],
            stdout=ANY,
            stderr=ANY,
            text=True,
            cwd=ANY,
        )


def test_find_events(trace_service, mock_index):
    query = "test_decision"

    # Mock SQL result
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []  # fallback

    # Mock iterator behavior for cursor
    rows = [
        {
            "id": "evt_1",
            "type": "decision",
            "summary": "Made a test decision",
            "timestamp": datetime.now().isoformat(),
            "markdown_path": "docs/logs/test.md",
        }
    ]
    mock_cursor.__iter__.return_value = iter(rows)

    mock_conn.execute.return_value = mock_cursor
    mock_index._get_conn.return_value = mock_conn

    events = trace_service._find_events(query)

    assert len(events) == 1
    assert events[0]["id"] == "evt_1"


def test_trace_integration(trace_service):
    # Mock files, events, and code_entities (avoid scanning real codebase)
    with (
        patch.object(trace_service, "_find_code_entities", return_value=[]),
        patch.object(
            trace_service,
            "_find_files",
            return_value=[
                TraceNode(
                    id="file:src/main.py:14",
                    type="file",
                    summary="match line",
                    timestamp=datetime(2023, 1, 1, 12, 0, 0).timestamp(),
                    path="src/main.py",
                    line_start=14,
                    relevance=0.8,
                )
            ],
        ),
        patch.object(
            trace_service,
            "_find_events",
            return_value=[
                {
                    "id": "e1",
                    "type": "decision",
                    "summary": "s1",
                    "timestamp": "2023-01-01T12:00:00",
                    "markdown_path": "doc.md",
                }
            ],
        ),
    ):
        nodes = trace_service.trace("test")

        assert len(nodes) == 2
        assert any(node.path == "src/main.py" and node.line_start == 14 for node in nodes)


def test_find_code_entities_labels_call_references(trace_service):
    with patch(
        "dimcause.core.code_indexer.trace_code",
        return_value={
            "definitions": [
                {
                    "name": "helper",
                    "type": "function",
                    "file_path": "src/utils.py",
                    "line_start": 1,
                    "line_end": 2,
                }
            ],
            "references": [
                {
                    "source_file": "src/main.py",
                    "source_entity": "main",
                    "target_name": "helper",
                    "line_number": 4,
                    "reference_type": "call",
                }
            ],
        },
    ):
        nodes = trace_service._find_code_entities("helper")

    assert any(node.type == "code_definition" for node in nodes)
    assert any(node.type == "code_reference" and node.summary == "Called by main" for node in nodes)
