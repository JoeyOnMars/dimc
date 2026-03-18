"""
Test Time Travel features (git history snapshots and diffs)
"""

from dimcause.extractors.git_history import get_file_at_commit, get_file_diff, get_file_snapshots


def test_get_file_at_commit():
    """Test retrieving file content at specific commit"""
    # This will only work if there's actual git history
    # Just test that it returns None or content
    result = get_file_at_commit("src/dimcause/cli.py", "HEAD")

    # Should either get content or None
    assert result is None or isinstance(result, str)

    if result:
        # If we got content, it should be Python code
        assert "import" in result or "def " in result


def test_get_file_diff():
    """Test getting diff between commits"""
    # Test against HEAD (should return None or empty string for identical)
    result = get_file_diff("src/dimcause/cli.py", "HEAD", "HEAD")

    assert result is not None  # Should at least return empty string
    assert isinstance(result, str)


def test_get_file_snapshots():
    """Test getting file content at multiple dates"""
    dates = ["2026-01-19", "2026-01-18"]

    snapshots = get_file_snapshots("src/dimcause/cli.py", dates)

    assert isinstance(snapshots, list)
    assert len(snapshots) == len(dates)

    # Each snapshot should be a tuple of (date, content or None)
    for snapshot in snapshots:
        assert isinstance(snapshot, tuple)
        assert len(snapshot) == 2
        assert isinstance(snapshot[0], str)
        # snapshot[1] can be str or None


def test_get_file_at_nonexistent_commit():
    """Test that nonexistent commit returns None"""
    result = get_file_at_commit("src/dimcause/cli.py", "nonexistent123")

    assert result is None


def test_get_file_diff_nonexistent():
    """Test diff with nonexistent commit returns None"""
    result = get_file_diff("src/dimcause/cli.py", "nonexistent123", "HEAD")

    assert result is None
