"""
Test Git History Extractor
"""

from dimcause.extractors.git_history import (
    GitCommit,
    format_history_timeline,
    get_file_creation_date,
    get_file_history,
    get_recent_changes,
)


def test_get_file_history(tmp_path):
    """Test basic file history retrieval"""
    # Test on a real file in the project
    history = get_file_history("src/dimcause/cli.py", max_count=5)

    assert isinstance(history, list)
    if history:  # Only check if we're in a git repo
        assert all(isinstance(c, GitCommit) for c in history)
        assert all(c.hash for c in history)
        assert all(c.date for c in history)


def test_get_file_creation_date(tmp_path):
    """Test file creation date extraction"""
    creation_date = get_file_creation_date("src/dimcause/cli.py")

    # Should return None or a valid date string
    if creation_date:
        assert len(creation_date) == 10  # YYYY-MM-DD format
        assert creation_date.count("-") == 2


def test_get_recent_changes():
    """Test recent changes retrieval"""
    changes = get_recent_changes("src/dimcause/cli.py", since_date="2026-01-01")

    assert isinstance(changes, list)
    if changes:
        assert all(isinstance(c, GitCommit) for c in changes)


def test_format_history_timeline():
    """Test timeline formatting"""
    commits = [
        GitCommit(
            hash="abc123def456", date="2026-01-19", message="Add trace command", author="Joey"
        ),
        GitCommit(hash="def456ghi789", date="2026-01-18", message="Initial commit", author="Joey"),
    ]

    timeline = format_history_timeline(commits)

    assert "Git History Timeline" in timeline
    assert "2026-01-19" in timeline
    assert "Add trace command" in timeline
    assert "abc123de" in timeline  # Short hash


def test_empty_history():
    """Test behavior with non-existent file"""
    history = get_file_history("nonexistent_file_xyz.txt")

    assert history == []

    timeline = format_history_timeline([])
    assert "No commit history" in timeline
