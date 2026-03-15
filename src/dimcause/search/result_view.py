from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.models import Event


@dataclass(frozen=True)
class SearchResultView:
    event_id: str
    synthetic: bool
    open_path: Optional[str]
    trace_target: str
    source_label: str
    location_label: str
    summary_label: str
    line_no: Optional[int]


def build_search_result_view(event: Event) -> SearchResultView:
    metadata = getattr(event, "metadata", {}) or {}
    synthetic = bool(metadata.get("synthetic_result"))
    open_path = (
        getattr(event, "markdown_path", None)
        or metadata.get("retrieval_path")
        or metadata.get("markdown_path")
    )

    related_files = getattr(event, "related_files", []) or []
    trace_target = related_files[0] if related_files else event.id

    source_label = metadata.get("retrieval_source", "-")

    path = metadata.get("retrieval_display_path")
    if not path and related_files:
        path = related_files[0]

    line_no = metadata.get("retrieval_line")
    if path and line_no:
        location_label = f"{path}:{line_no}"
    elif path:
        location_label = path
    else:
        location_label = "-"

    snippet = metadata.get("retrieval_snippet")
    if isinstance(snippet, str) and snippet.strip():
        summary_label = snippet.strip()
    else:
        summary = getattr(event, "summary", "") or ""
        if synthetic and " - " in summary:
            summary_label = summary.split(" - ", 1)[1]
        else:
            summary_label = summary

    return SearchResultView(
        event_id=event.id,
        synthetic=synthetic,
        open_path=open_path,
        trace_target=trace_target,
        source_label=source_label,
        location_label=location_label,
        summary_label=summary_label,
        line_no=line_no,
    )
