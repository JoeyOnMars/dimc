"""
Log Correlator

Correlates Git commits with Dimcause log entries for Causal Chain feature.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dimcause.extractors.git_history import GitCommit
from dimcause.utils.config import get_config


@dataclass
class LogEntry:
    """Represents a relevant log entry"""

    date: str
    source: str  # daily.md, job/start.md, etc.
    content: str
    file_path: Path
    relevance_score: float = 0.0


def get_logs_by_date_range(
    start_date: str, end_date: str, logs_dir: Optional[Path] = None
) -> List[LogEntry]:
    """
    Retrieve all log entries within a date range.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        logs_dir: Path to logs directory (defaults to config)

    Returns:
        List of LogEntry objects
    """
    if logs_dir is None:
        config = get_config()
        logs_dir = config.root_dir / "docs" / "logs"

    entries = []

    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Iterate through date range
    current = start
    while current <= end:
        year = current.strftime("%Y")
        day = current.strftime("%m-%d")

        day_dir = logs_dir / year / day
        if day_dir.exists():
            # Collect all .md files in this day
            for md_file in day_dir.rglob("*.md"):
                if md_file.name in ["start.md", "end.md", "daily.md", "session.md"]:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")

                    entries.append(
                        LogEntry(
                            date=current.strftime("%Y-%m-%d"),
                            source=str(md_file.relative_to(day_dir)),
                            content=content,
                            file_path=md_file,
                        )
                    )

        current += timedelta(days=1)

    return entries


def search_logs_by_keywords(
    entries: List[LogEntry], keywords: List[str], case_sensitive: bool = False
) -> List[LogEntry]:
    """
    Filter log entries by keywords.

    Args:
        entries: List of LogEntry objects
        keywords: Keywords to search for
        case_sensitive: Whether search should be case-sensitive

    Returns:
        Filtered and scored list of LogEntry objects
    """
    if not keywords:
        return entries

    scored_entries = []

    for entry in entries:
        content = entry.content if case_sensitive else entry.content.lower()
        search_keywords = keywords if case_sensitive else [k.lower() for k in keywords]

        # Calculate relevance score (number of keyword matches)
        score = sum(1 for kw in search_keywords if kw in content)

        if score > 0:
            entry.relevance_score = score
            scored_entries.append(entry)

    # Sort by relevance (highest first)
    scored_entries.sort(key=lambda e: e.relevance_score, reverse=True)

    return scored_entries


def correlate_commits_with_logs(
    commits: List[GitCommit], time_window_days: int = 3, logs_dir: Optional[Path] = None
) -> Dict[str, List[LogEntry]]:
    """
    Correlate Git commits with relevant log entries.

    For each commit, find log entries within a time window.

    Args:
        commits: List of GitCommit objects
        time_window_days: Number of days before/after commit to search
        logs_dir: Path to logs directory

    Returns:
        Dictionary mapping commit hash to relevant log entries
    """
    correlations = {}

    for commit in commits:
        # Calculate time window
        commit_date = datetime.strptime(commit.date, "%Y-%m-%d")
        start_date = (commit_date - timedelta(days=time_window_days)).strftime("%Y-%m-%d")
        end_date = (commit_date + timedelta(days=time_window_days)).strftime("%Y-%m-%d")

        # Get logs in time window
        entries = get_logs_by_date_range(start_date, end_date, logs_dir)

        # Extract keywords from commit message
        keywords = extract_keywords(commit.message)

        # Filter by keywords
        relevant_entries = search_logs_by_keywords(entries, keywords)

        correlations[commit.hash] = relevant_entries

    return correlations


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """
    Extract meaningful keywords from text.

    Args:
        text: Input text
        min_length: Minimum keyword length

    Returns:
        List of keywords
    """
    # Simple keyword extraction (can be improved with NLP)
    stop_words = {
        "add",
        "fix",
        "update",
        "refactor",
        "chore",
        "feat",
        "docs",
        "test",
        "for",
        "and",
        "the",
        "with",
        "from",
        "that",
        "this",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "of",
        "by",
    }

    words = text.lower().split()
    keywords = [
        w.strip(".,;:!?()[]{}\"'")
        for w in words
        if len(w) >= min_length and w.lower() not in stop_words
    ]

    return keywords


def format_correlation_report(
    commit: GitCommit, entries: List[LogEntry], max_entries: int = 3
) -> str:
    """
    Format a correlation report for a single commit.

    Args:
        commit: GitCommit object
        entries: Related log entries
        max_entries: Maximum number of entries to include

    Returns:
        Formatted string
    """
    lines = [
        f"## Commit: {commit.hash[:8]}",
        f"**Date**: {commit.date}",
        f"**Message**: {commit.message}",
        f"**Author**: {commit.author}",
        "",
        f"### Related Memory Entries ({len(entries)} found):",
        "",
    ]

    for i, entry in enumerate(entries[:max_entries], 1):
        lines.append(f"{i}. **{entry.source}** (Score: {entry.relevance_score})")

        # Show first 200 chars of content
        preview = entry.content[:200].replace("\n", " ").strip()
        if len(entry.content) > 200:
            preview += "..."

        lines.append(f"   {preview}")
        lines.append("")

    if len(entries) > max_entries:
        lines.append(f"   ... and {len(entries) - max_entries} more entries")

    return "\n".join(lines)
