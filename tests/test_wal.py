"""
Tests for WAL (Write-Ahead Log) - 崩溃恢复机制

Critical Test: 验证daemon崩溃后数据不丢失
"""

import json
import tempfile
from pathlib import Path

import pytest

from dimcause.utils.wal import WriteAheadLog, get_wal


class TestWAL:
    """测试Write-Ahead Log"""

    @pytest.fixture
    def temp_wal_file(self):
        """临时WAL文件"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            wal_path = f.name
        yield wal_path
        # Cleanup
        Path(wal_path).unlink(missing_ok=True)

    def test_append_pending(self, temp_wal_file):
        """测试记录待处理事件"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {"content": "test data"})

        # 验证文件写入
        assert Path(temp_wal_file).exists()

        with open(temp_wal_file) as f:
            line = f.readline()
            entry = json.loads(line)
            assert entry["id"] == "evt_001"
            assert entry["event_type"] == "pending"

    def test_mark_completed(self, temp_wal_file):
        """测试标记事件完成"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {"content": "test"})
        wal.mark_completed("evt_001")

        # 验证两条记录
        with open(temp_wal_file) as f:
            lines = f.readlines()
            assert len(lines) == 2

            entry2 = json.loads(lines[1])
            assert entry2["event_type"] == "completed"

    def test_mark_failed(self, temp_wal_file):
        """测试标记事件失败"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {"content": "test"})
        wal.mark_failed("evt_001", "LLM timeout", retry_count=1)

        with open(temp_wal_file) as f:
            lines = f.readlines()
            failed_entry = json.loads(lines[1])

            assert failed_entry["event_type"] == "failed"
            assert failed_entry["data"]["error"] == "LLM timeout"
            assert failed_entry["retry_count"] == 1

    def test_recover_pending(self, temp_wal_file):
        """测试恢复未完成事件(核心功能)"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        # 模拟3个事件: 1个完成, 1个失败, 1个pending
        wal.append_pending("evt_001", {"content": "test1"})
        wal.append_pending("evt_002", {"content": "test2"})
        wal.append_pending("evt_003", {"content": "test3"})

        wal.mark_completed("evt_001")
        wal.mark_failed("evt_002", "error")
        # evt_003 保持pending

        # 恢复
        unfinished = wal.recover_pending()

        assert len(unfinished) == 1
        assert unfinished[0].id == "evt_003"

    def test_crash_recovery_scenario(self, temp_wal_file):
        """测试真实崩溃恢复场景"""
        # 第一个daemon实例
        wal1 = WriteAheadLog(wal_path=temp_wal_file)

        wal1.append_pending("evt_001", {"content": "processing..."})
        wal1.append_pending("evt_002", {"content": "processing..."})
        wal1.mark_completed("evt_001")
        # Daemon崩溃,evt_002未完成

        # 第二个daemon实例(重启后)
        wal2 = WriteAheadLog(wal_path=temp_wal_file)
        unfinished = wal2.recover_pending()

        assert len(unfinished) == 1
        assert unfinished[0].id == "evt_002"

    def test_wal_compact(self, temp_wal_file):
        """测试WAL压缩"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        # 添加10个事件,8个完成
        for i in range(10):
            wal.append_pending(f"evt_{i:03d}", {"content": f"test{i}"})

        for i in range(8):
            wal.mark_completed(f"evt_{i:03d}")

        # 压缩
        removed = wal.compact(keep_completed=False)

        assert removed > 0

        # 验证只剩2个pending
        unfinished = wal.recover_pending()
        assert len(unfinished) == 2

    def test_wal_stats(self, temp_wal_file):
        """测试WAL统计"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {})
        wal.append_pending("evt_002", {})
        wal.mark_completed("evt_001")
        wal.mark_failed("evt_003", "error")

        stats = wal.stats()

        assert stats["pending"] > 0
        assert stats["completed"] > 0
        assert stats["failed"] > 0

    def test_fsync_durability(self, temp_wal_file):
        """测试fsync确保持久化"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {"critical": "data"})

        # 立即读取(即使未flush)
        wal2 = WriteAheadLog(wal_path=temp_wal_file)
        unfinished = wal2.recover_pending()

        assert len(unfinished) > 0

    def test_concurrent_writes(self, temp_wal_file):
        """测试并发写入(简化版)"""
        wal1 = WriteAheadLog(wal_path=temp_wal_file)
        wal2 = WriteAheadLog(wal_path=temp_wal_file)

        wal1.append_pending("evt_001", {})
        wal2.append_pending("evt_002", {})

        # 验证两条记录都写入了
        with open(temp_wal_file) as f:
            lines = f.readlines()
            assert len(lines) == 2

    def test_corrupted_line_handling(self, temp_wal_file):
        """测试处理损坏的WAL行"""
        wal = WriteAheadLog(wal_path=temp_wal_file)

        wal.append_pending("evt_001", {})

        # 手动添加损坏的行
        with open(temp_wal_file, "a") as f:
            f.write("CORRUPTED JSON LINE\n")

        wal.append_pending("evt_002", {})

        # 恢复应该跳过损坏行
        unfinished = wal.recover_pending()
        assert len(unfinished) == 2

    def test_default_path_uses_dimcause(self, tmp_path, monkeypatch):
        """默认 WAL 路径应为 ~/.dimcause/wal.log"""
        monkeypatch.setenv("HOME", str(tmp_path))

        wal = WriteAheadLog()
        expected = tmp_path / ".dimcause" / "wal.log"

        assert wal.wal_path == expected
        assert expected.exists()

    def test_default_path_migrates_legacy_mal(self, tmp_path, monkeypatch):
        """若仅存在 legacy ~/.mal/wal.log，应自动迁移到 ~/.dimcause/wal.log"""
        monkeypatch.setenv("HOME", str(tmp_path))

        legacy = tmp_path / ".mal" / "wal.log"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy_content = '{"id":"evt_legacy","event_type":"pending","data":{},"timestamp":1.0}\n'
        legacy.write_text(legacy_content, encoding="utf-8")

        wal = WriteAheadLog()
        expected = tmp_path / ".dimcause" / "wal.log"

        assert wal.wal_path == expected
        assert expected.exists()
        assert expected.read_text(encoding="utf-8") == legacy_content
        assert not legacy.exists()


class TestWALSingleton:
    """测试WAL单例模式"""

    def test_get_wal_singleton(self):
        """测试全局单例"""
        wal1 = get_wal()
        wal2 = get_wal()

        assert wal1 is wal2


def test_real_world_daemon_crash():
    """测试真实daemon崩溃场景"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        wal_path = f.name

    try:
        # Daemon启动,处理3个事件
        wal = WriteAheadLog(wal_path=wal_path)

        events = [
            ("evt_001", {"type": "code_change", "file": "main.py"}),
            ("evt_002", {"type": "conversation", "content": "debug help"}),
            ("evt_003", {"type": "commit", "hash": "abc123"}),
        ]

        for event_id, data in events:
            wal.append_pending(event_id, data)

        # 只完成第一个
        wal.mark_completed("evt_001")

        # Daemon崩溃 (模拟: 不标记evt_002和evt_003为完成)

        # Daemon重启后恢复
        wal_new = WriteAheadLog(wal_path=wal_path)
        unfinished = wal_new.recover_pending()

        # 验证恢复了未完成的2个事件
        assert len(unfinished) == 2
        unfinished_ids = {e.id for e in unfinished}
        assert "evt_002" in unfinished_ids
        assert "evt_003" in unfinished_ids

        # 重新处理并标记完成
        for event in unfinished:
            wal_new.mark_completed(event.id)

        # 再次恢复,应该没有pending事件
        final_check = wal_new.recover_pending()
        assert len(final_check) == 0

    finally:
        Path(wal_path).unlink(missing_ok=True)
