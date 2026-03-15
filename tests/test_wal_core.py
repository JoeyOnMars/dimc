from datetime import datetime

import pytest

from dimcause.core.models import RawData, SourceType
from dimcause.utils.wal import WriteAheadLog


@pytest.fixture
def wal_test_env(tmp_path):
    wal_dir = tmp_path / "wal"
    return wal_dir


def create_raw_data(id_suffix: str) -> RawData:
    return RawData(
        id=f"test_{id_suffix}",
        source=SourceType.MANUAL,
        content=f"content_{id_suffix}",
        timestamp=datetime.now(),
    )


def test_wal_write_and_read(wal_test_env):
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))

    # Write entries
    data1 = create_raw_data("1")
    data2 = create_raw_data("2")

    manager.append_pending(data1.id, data1.model_dump())
    manager.append_pending(data2.id, data2.model_dump())

    # Check if file exists
    assert (wal_test_env / "active.log").exists()

    # Read pending
    pending = manager.recover_pending()
    assert len(pending) == 2
    assert pending[0].id == data1.id
    assert pending[1].id == data2.id


def test_wal_ack_and_pending(wal_test_env):
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))

    # Write 10 items
    items = [create_raw_data(str(i)) for i in range(10)]
    for item in items:
        manager.append_pending(item.id, item.model_dump())

    # Ack 5 items (indices 0-4)
    for i in range(5):
        manager.mark_completed(items[i].id)

    # Check pending (should be indices 5-9)
    pending = manager.recover_pending()
    assert len(pending) == 5

    pending_ids = {p.id for p in pending}
    expected_ids = {items[i].id for i in range(5, 10)}
    assert pending_ids == expected_ids


def test_wal_persistence_recovery(wal_test_env):
    # Instance 1: Write and Crash (stop using)
    manager1 = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    data1 = create_raw_data("persist")
    manager1.append_pending(data1.id, data1.model_dump())

    # Instance 2: Start fresh and Recover
    manager2 = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    pending = manager2.recover_pending()

    assert len(pending) == 1
    assert pending[0].id == data1.id
    # WALEntry stores data in .data dictionary
    assert pending[0].data["content"] == data1.content


def test_wal_rotation(wal_test_env):
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))

    # Write 3, Ack 2
    d1 = create_raw_data("1")
    d2 = create_raw_data("2")
    d3 = create_raw_data("3")

    manager.append_pending(d1.id, d1.model_dump())
    manager.append_pending(d2.id, d2.model_dump())
    manager.append_pending(d3.id, d3.model_dump())

    manager.mark_completed(d1.id)
    manager.mark_completed(d3.id)

    # Expect d2 pending
    assert len(manager.recover_pending()) == 1

    # Inspect file size before rotation
    log_file = wal_test_env / "active.log"
    size_before = log_file.stat().st_size

    # Rotate/Compact
    manager.compact()

    # Inspect after
    size_after = log_file.stat().st_size
    assert size_after < size_before  # Should be smaller

    # Verify d2 is still there
    new_manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    pending = new_manager.recover_pending()
    assert len(pending) == 1
    assert pending[0].id == d2.id


def test_corrupt_wal_handling(wal_test_env):
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    d = create_raw_data("ok")
    manager.append_pending(d.id, d.model_dump())

    # Manually append garbage
    log_file = wal_test_env / "active.log"
    with open(log_file, "a") as f:
        f.write("THIS_IS_GARBAGE_JSON\n")
        f.write('{"type": "WRITE", "broken_json": ...}\n')

    d2 = create_raw_data("ok2")
    manager.append_pending(d2.id, d2.model_dump())

    # Should ignore garbage and load valid
    pending = manager.recover_pending()
    assert len(pending) == 2
    assert pending[0].id == "test_ok"
    assert pending[1].id == "test_ok2"
