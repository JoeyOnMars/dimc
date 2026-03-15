from datetime import datetime

from dimcause.extractors.log_parser import extract_log_time_range, is_log_relevant


def test_extract_log_time_range():
    # Case 1: Standard ISO
    content = """
    Start: 2026-02-18 10:00:00
    ...
    End: 2026-02-18 12:00:00
    """
    min_t, max_t = extract_log_time_range(content)
    assert min_t == datetime(2026, 2, 18, 10, 0, 0)
    assert max_t == datetime(2026, 2, 18, 12, 0, 0)

    # Case 2: Slash format
    content = "Log entry at 2026/02/18 13:30:00 ending."
    min_t, max_t = extract_log_time_range(content)
    assert min_t == datetime(2026, 2, 18, 13, 30, 0)
    assert max_t == datetime(2026, 2, 18, 13, 30, 0)

    # Case 3: No dates
    content = "Hello world"
    assert extract_log_time_range(content) is None


def test_is_log_relevant():
    session_start = datetime(2026, 2, 18, 9, 0, 0)

    # Case 1: Content is strictly after start
    content = "Event at 2026-02-18 10:00:00"
    assert is_log_relevant(content, session_start) is True

    # Case 2: Content is slightly before start (within 1h tolerance)
    # 8:30 is within 1 hour of 9:00
    content = "Event at 2026-02-18 08:30:00"
    assert is_log_relevant(content, session_start, tolerance_seconds=3600) is True

    # Case 3: Content is too old
    # 7:00 is outside 1 hour tolerance
    content = "Event at 2026-02-18 07:00:00"
    assert is_log_relevant(content, session_start, tolerance_seconds=3600) is False

    # Case 4: No dates found -> Fallback True (Let mtime decide)
    content = "No dates here"
    assert is_log_relevant(content, session_start) is True
