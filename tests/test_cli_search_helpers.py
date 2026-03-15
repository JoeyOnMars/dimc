from datetime import datetime
from unittest.mock import MagicMock, patch

from dimcause.cli import (
    _execute_search_request,
    _is_synthetic_search_result,
    _normalize_search_source,
    _search_mode_label,
    _search_result_location_label,
    _search_result_open_path,
    _search_result_source_label,
    _search_result_summary_label,
    _search_result_trace_target,
    _truncate_search_cell,
    _view_search_result,
)
from dimcause.core.models import Event, EventType, SourceType
from dimcause.search import SearchResultView, build_search_result_view


def _make_event(**metadata_overrides):
    metadata = {
        "synthetic_result": True,
        "retrieval_source": "code",
        "retrieval_path": "/tmp/x.py",
        "retrieval_snippet": "def needle()",
    }
    metadata.update(metadata_overrides)
    return Event(
        id="unix_code_123",
        type=EventType.RESOURCE,
        timestamp=datetime.now(),
        summary="[code] src/x.py:3 - def needle()",
        content="def needle(): pass",
        source=SourceType.FILE,
        metadata=metadata,
        related_files=["src/x.py"],
    )


def test_search_result_helpers_read_synthetic_metadata():
    event = _make_event(retrieval_line=3, retrieval_display_path="src/x.py")

    assert _is_synthetic_search_result(event) is True
    assert _search_result_open_path(event) == "/tmp/x.py"
    assert _search_result_source_label(event) == "code"
    assert _search_result_location_label(event) == "src/x.py:3"
    assert _search_result_summary_label(event) == "def needle()"
    assert _search_result_trace_target(event) == "src/x.py"


def test_build_search_result_view_returns_unified_schema():
    event = _make_event(retrieval_line=3, retrieval_display_path="src/x.py")

    result_view = build_search_result_view(event)

    assert isinstance(result_view, SearchResultView)
    assert result_view.synthetic is True
    assert result_view.open_path == "/tmp/x.py"
    assert result_view.location_label == "src/x.py:3"
    assert result_view.summary_label == "def needle()"


def test_execute_search_request_uses_unix_filter_when_source_is_provided():
    engine = MagicMock()
    engine._unix_search.return_value = ["unix"]

    result = _execute_search_request(
        engine=engine,
        query="needle",
        mode="hybrid",
        top_k=5,
        use_reranker=False,
        source="code",
    )

    assert result == ["unix"]
    engine._unix_search.assert_called_once_with("needle", 5, sources=("code",))
    engine.search.assert_not_called()


def test_normalize_search_source_accepts_known_values():
    assert _normalize_search_source("Code") == "code"
    assert _normalize_search_source(" docs ") == "docs"
    assert _normalize_search_source(None) is None


@patch("dimcause.cli.console")
@patch("dimcause.cli.typer.Exit", side_effect=RuntimeError("exit"))
def test_normalize_search_source_rejects_unknown_value(_mock_exit, mock_console):
    try:
        _normalize_search_source("unknown")
    except RuntimeError as exc:
        assert str(exc) == "exit"

    assert mock_console.print.called


def test_search_mode_label_reflects_source_filter():
    assert _search_mode_label("hybrid", None) == "hybrid"
    assert _search_mode_label("hybrid", "code") == "unix[code]"


def test_execute_search_request_uses_engine_search_by_default():
    engine = MagicMock()
    engine.search.return_value = ["hybrid"]

    result = _execute_search_request(
        engine=engine,
        query="needle",
        mode="hybrid",
        top_k=5,
        use_reranker=False,
        source=None,
    )

    assert result == ["hybrid"]
    engine.search.assert_called_once_with(
        query="needle",
        mode="hybrid",
        top_k=5,
        use_reranker=False,
    )
    engine._unix_search.assert_not_called()


def test_search_result_location_falls_back_to_related_files():
    event = Event(
        id="evt_1",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="real event",
        content="content",
        source=SourceType.MANUAL,
        related_files=["src/app.py"],
    )

    assert _search_result_location_label(event) == "src/app.py"
    assert _search_result_summary_label(event) == "real event"


def test_search_result_summary_prefers_retrieval_snippet_for_real_event():
    event = Event(
        id="evt_1",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="real event summary",
        content="content",
        source=SourceType.MANUAL,
        metadata={"retrieval_snippet": "matched line from event body"},
    )

    assert _search_result_summary_label(event) == "matched line from event body"


def test_truncate_search_cell_preserves_short_values():
    assert _truncate_search_cell("short", 10) == "short"
    assert _truncate_search_cell("abcdefghijkl", 8) == "abcde..."


@patch("dimcause.cli.console")
def test_view_search_result_renders_panel_for_synthetic_result(mock_console):
    event = _make_event(retrieval_line=3)

    _view_search_result(event)

    assert mock_console.print.called
    rendered = mock_console.print.call_args[0][0]
    assert "unix_code_123" in str(rendered.title)


@patch("dimcause.cli.view")
@patch("dimcause.cli.console")
def test_view_search_result_delegates_for_real_event(_mock_console, mock_view):
    event = Event(
        id="evt_1",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="real event",
        content="content",
        source=SourceType.MANUAL,
    )

    _view_search_result(event)

    mock_view.assert_called_once_with(event_id="evt_1")
