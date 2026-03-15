import sqlite3
from datetime import datetime

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType


def _make_event(event_id: str, related_files=None) -> Event:
    return Event(
        id=event_id,
        type=EventType.DECISION,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary=f"summary for {event_id}",
        content=f"content for {event_id}",
        related_files=related_files or [],
    )


def test_add_populates_events_cache_and_file_refs(tmp_path):
    db_path = tmp_path / "index.db"
    index = EventIndex(str(db_path))
    md_path = tmp_path / "evt-cache.md"
    md_path.touch()

    event = _make_event("evt-cache", related_files=["src/dimcause/cli.py"])
    assert index.add(event, str(md_path)) is True

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cache_row = conn.execute("SELECT * FROM events_cache WHERE id = ?", (event.id,)).fetchone()
    ref_rows = conn.execute(
        "SELECT file_path, file_name FROM event_file_refs WHERE event_id = ? ORDER BY file_path",
        (event.id,),
    ).fetchall()
    conn.close()

    assert cache_row is not None
    assert cache_row["markdown_path"] == str(md_path.resolve())
    assert {row["file_path"] for row in ref_rows} >= {
        "src/dimcause/cli.py",
        str(md_path.resolve()),
    }
    assert {row["file_name"] for row in ref_rows} >= {"cli.py", md_path.name}


def test_get_by_file_uses_file_ref_index_when_json_cache_missing(tmp_path):
    db_path = tmp_path / "index.db"
    index = EventIndex(str(db_path))
    md_path = tmp_path / "evt-ref.md"
    md_path.touch()

    event = _make_event("evt-ref", related_files=["src/dimcause/search/engine.py"])
    assert index.add(event, str(md_path)) is True

    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE events SET json_cache = NULL WHERE id = ?", (event.id,))
    conn.commit()
    conn.close()

    results = index.get_by_file("src/dimcause/search/engine.py")
    assert [row["id"] for row in results] == [event.id]


def test_load_event_uses_events_cache_when_primary_cache_missing(tmp_path):
    db_path = tmp_path / "index.db"
    index = EventIndex(str(db_path))
    md_path = tmp_path / "evt-load.md"
    md_path.touch()

    event = _make_event("evt-load", related_files=["docs/STATUS.md"])
    assert index.add(event, str(md_path)) is True

    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE events SET json_cache = NULL WHERE id = ?", (event.id,))
    conn.commit()
    conn.close()

    loaded = index.load_event(event.id)
    assert loaded is not None
    assert loaded.id == event.id
    assert loaded.related_files == ["docs/STATUS.md"]


def test_reopen_backfills_missing_query_cache_tables(tmp_path):
    db_path = tmp_path / "index.db"
    md_path = tmp_path / "evt-backfill.md"
    md_path.touch()

    first_index = EventIndex(str(db_path))
    event = _make_event("evt-backfill", related_files=["src/dimcause/core/history.py"])
    assert first_index.add(event, str(md_path)) is True

    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM events_cache WHERE id = ?", (event.id,))
    conn.execute("DELETE FROM event_file_refs WHERE event_id = ?", (event.id,))
    conn.commit()
    conn.close()

    reopened = EventIndex(str(db_path))
    loaded = reopened.load_event(event.id)
    assert loaded is not None
    assert loaded.id == event.id

    results = reopened.get_by_file("src/dimcause/core/history.py")
    assert [row["id"] for row in results] == [event.id]
