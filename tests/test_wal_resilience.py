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


def test_manual_compaction(wal_test_env):
    """Verify that compaction reduces file size"""
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))

    # 1. Write 1000 items.
    for i in range(1000):
        item = create_raw_data(str(i))
        manager.append_pending(item.id, item.model_dump())
        manager.mark_completed(item.id)

    # File should be large
    log_file = wal_test_env / "active.log"
    size_before = log_file.stat().st_size
    assert size_before > 1000  # Should be substantial

    # 2. Compact
    manager.compact()

    # 3. Size should drop
    size_after = log_file.stat().st_size
    assert size_after < size_before

    # 4. Verify pending is empty
    pending = manager.recover_pending()
    assert len(pending) == 0

    # Verify functioning after compaction
    new_item = create_raw_data("after_compact")
    manager.append_pending(new_item.id, new_item.model_dump())
    assert log_file.stat().st_size > size_after

    pending = manager.recover_pending()
    assert len(pending) == 1
    assert pending[0].id == "test_after_compact"


def test_forced_corruption_recovery(wal_test_env):
    """Test handling of partially written lines"""
    manager = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    log_file = wal_test_env / "active.log"

    # 1. Write valid entry
    d1 = create_raw_data("valid_1")
    manager.append_pending(d1.id, d1.model_dump())

    # 2. Corrupt the file manually
    with open(log_file, "a") as f:
        # Half-written JSON
        f.write('{"type": "WRITE", "id": "corrupt_1", "data": {"unexpected_eof": true')
        # No newline, just stop

    # 3. Create new manager (simulate crash recovery)
    manager2 = WriteAheadLog(wal_path=str(wal_test_env / "active.log"))
    pending = manager2.recover_pending()

    # Should recover d1 and ignore the rest
    assert len(pending) == 1
    assert pending[0].id == "test_valid_1"

    # 4. Continue writing
    d2 = create_raw_data("valid_2")
    manager2.append_pending(d2.id, d2.model_dump())

    # 5. Verify both exist now
    pending_new = manager2.recover_pending()
    assert len(pending_new) == 2
    ids = {p.id for p in pending_new}
    assert "test_valid_1" in ids
    assert "test_valid_2" in ids
