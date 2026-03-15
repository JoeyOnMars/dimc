"""Helpers for resolving and parsing scheduler status files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

MODERN_STATUS_FILE = "docs/STATUS.md"
LEGACY_STATUS_FILE = "docs/V5.2/STATUS-5.2-001.md"


def resolve_status_file(project_root: Path) -> Optional[Path]:
    """Resolve scheduler status file from modern V6 path only."""
    candidate = project_root / MODERN_STATUS_FILE
    return candidate if candidate.exists() else None


def is_modern_status_path(path: Optional[Path], project_root: Path) -> bool:
    """Return True when the resolved path is the modern V6 status file."""
    return path == project_root / MODERN_STATUS_FILE


def extract_modern_progress_rows(content: str) -> List[Tuple[str, str, str]]:
    """Extract task/content/status rows from the V6.1 progress table in docs/STATUS.md."""
    section = _extract_heading_section(content, r"^##\s+3\.", r"^##\s+4\.")
    if not section:
        return []

    rows: List[Tuple[str, str, str]] = []
    for cells in _iter_markdown_table_rows(section):
        if len(cells) != 3:
            continue
        task_id, name, status = cells
        if not _looks_like_status_cell(status):
            continue
        rows.append((task_id, name, status))
    return rows


def extract_legacy_rows(content: str) -> List[Tuple[str, str, str, str]]:
    """Extract ID/name/cli/status rows from the legacy four-column scheduler table."""
    pattern = (
        r"\|\s*\*?\*?([^|]+?)\*?\*?\s*"
        r"\|\s*\*?\*?([^|]+?)\*?\*?\s*"
        r"\|\s*`([^`]+)`\s*"
        r"\|\s*\*?\*?([^|]+?)\*?\*?\s*\|"
    )
    return [
        tuple(cell.strip() for cell in match.groups())  # type: ignore[return-value]
        for match in re.finditer(pattern, content)
    ]


def extract_compact_task_ids(content: str, modern: bool) -> Sequence[str]:
    """Extract compact task IDs (D1/H2/T1 style) used by legacy agent-task cards."""
    if modern:
        rows = extract_modern_progress_rows(content)
        return [task_id for task_id, _, _ in rows if _looks_like_compact_task_id(task_id)]

    rows = extract_legacy_rows(content)
    return [task_id for task_id, _, _, _ in rows if _looks_like_compact_task_id(task_id)]


def _extract_heading_section(content: str, start_pattern: str, end_pattern: str) -> str:
    lines = content.splitlines()
    start_idx: Optional[int] = None
    end_idx = len(lines)

    for idx, line in enumerate(lines):
        if start_idx is None and re.match(start_pattern, line):
            start_idx = idx + 1
            continue
        if start_idx is not None and re.match(end_pattern, line):
            end_idx = idx
            break

    if start_idx is None:
        return ""
    return "\n".join(lines[start_idx:end_idx])


def _iter_markdown_table_rows(content: str) -> Iterator[List[str]]:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or _is_separator_row(cells):
            continue
        yield cells


def _is_separator_row(cells: Sequence[str]) -> bool:
    for cell in cells:
        if not cell:
            continue
        stripped = cell.replace(":", "").replace("-", "").strip()
        if stripped:
            return False
    return True


def _looks_like_status_cell(text: str) -> bool:
    normalized = text.strip()
    return any(
        marker in normalized
        for marker in (
            "✅",
            "🔄",
            "📋",
            "📝",
            "⛔",
            "Done",
            "In Progress",
            "Blocked",
            "待",
            "完成",
            "已创建",
        )
    )


def _looks_like_compact_task_id(text: str) -> bool:
    normalized = text.strip().upper()
    return bool(re.fullmatch(r"[A-Z]{1,3}\d?", normalized))
