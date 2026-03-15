from datetime import datetime

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType
from dimcause.utils.wal import WriteAheadLog


def _make_event(event_id: str) -> Event:
    return Event(
        id=event_id,
        type=EventType.DECISION,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary=f"summary:{event_id}",
        content=f"content:{event_id}",
    )


def test_add_marks_wal_completed(tmp_path):
    wal = WriteAheadLog(wal_path=str(tmp_path / "index.wal.log"))
    index = EventIndex(db_path=str(tmp_path / "index.db"), wal_manager=wal)
    event = _make_event("evt_wal_add")
    md_path = tmp_path / "event.md"
    md_path.touch()

    assert index.add(event, str(md_path)) is True
    assert index.get_by_id(event.id) is not None
    assert wal.recover_pending() == []
    assert wal.stats()["completed"] == 1


def test_add_if_not_exists_duplicate_leaves_no_pending(tmp_path):
    wal = WriteAheadLog(wal_path=str(tmp_path / "index.wal.log"))
    index = EventIndex(db_path=str(tmp_path / "index.db"), wal_manager=wal)
    event = _make_event("evt_wal_dup")
    md_path = tmp_path / "duplicate.md"
    md_path.touch()

    assert index.add_if_not_exists(event, str(md_path)) is True
    assert index.add_if_not_exists(event, str(md_path)) is False
    assert wal.recover_pending() == []
    assert wal.stats()["completed"] == 2


def test_add_failure_marks_wal_failed(tmp_path, monkeypatch):
    wal = WriteAheadLog(wal_path=str(tmp_path / "index.wal.log"))
    index = EventIndex(db_path=str(tmp_path / "index.db"), wal_manager=wal)
    event = _make_event("evt_wal_fail")
    md_path = tmp_path / "failed.md"
    md_path.touch()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(index, "_add_to_conn", boom)

    assert index.add(event, str(md_path)) is False
    assert wal.recover_pending() == []
    assert wal.stats()["failed"] == 1


def test_event_index_recovers_pending_write_on_init(tmp_path):
    wal = WriteAheadLog(wal_path=str(tmp_path / "index.wal.log"))
    event = _make_event("evt_recover_init")
    md_path = tmp_path / "recover.md"
    md_path.touch()

    cold_index = EventIndex(
        db_path=str(tmp_path / "index.db"),
        wal_manager=wal,
        enable_wal_recovery=False,
    )
    wal.append_pending(
        "event-index:evt_recover_init:1",
        cold_index._build_wal_payload(
            event,
            str(md_path),
            source_chunk_id="chk_001",
            source_layer="l1",
            write_mode="add",
        ),
    )

    recovered_index = EventIndex(db_path=str(tmp_path / "index.db"), wal_manager=wal)
    row = recovered_index.get_by_id(event.id)

    assert row is not None
    assert row["source_chunk_id"] == "chk_001"
    assert row["source_layer"] == "l1"
    assert wal.recover_pending() == []
