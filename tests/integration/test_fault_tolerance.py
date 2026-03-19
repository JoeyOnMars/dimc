# Covers: SEC-1.1 (Level A) – WAL partial failure & recovery

"""
Integration Tests: Fault Tolerance & Recovery

验证容错能力：Daemon 崩溃、部分写入失败、WAL 恢复
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.models import DimcauseConfig, RawData, SourceType
from dimcause.daemon.manager import DaemonManager
from dimcause.extractors import BasicExtractor


class TestFaultTolerance:
    """测试容错与恢复"""

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_daemon_crash_recovery(self):
        """测试 Daemon 崩溃后恢复"""
        # TODO: 模拟 daemon 崩溃，验证 WAL 恢复未完成事件
        pass

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_partial_write_failure(self):
        """测试部分写入失败"""
        # TODO: Markdown 写入成功，但索引更新失败，验证可恢复
        pass

    def test_wal_recovery_on_startup(self, tmp_path, monkeypatch):
        """测试启动时 WAL 恢复。"""
        data_dir = tmp_path / ".dimcause"
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        manager = DaemonManager(
            config=DimcauseConfig(
                data_dir=str(data_dir),
                watcher_claude={"enabled": False, "path": "dummy"},
                watcher_cursor={"enabled": False, "path": "dummy"},
                watcher_continue_dev={"enabled": False, "path": "dummy"},
                watcher_state={"enabled": False, "path": "dummy"},
                watcher_windsurf={"enabled": False, "path": "dummy"},
            )
        )

        # 这条测试只验证「WAL -> 恢复 -> Markdown/EventIndex 落库」主链；
        # 向量与图谱属于旁路存储，不在本断言范围内。
        manager._pipeline.extractor = BasicExtractor(llm_client=None)
        manager._pipeline.reasoning_engine = None
        monkeypatch.setattr(manager._pipeline.vector_store, "add", lambda event: None)
        monkeypatch.setattr(manager._pipeline.graph_store, "add_event_relations", lambda event: None)

        raw = RawData(
            id="raw_recovery_001",
            source=SourceType.MANUAL,
            timestamp=datetime(2026, 3, 19, 10, 0, 0),
            content="修复 SQLite 写锁竞争，补充恢复逻辑并验证启动恢复。",
            files_mentioned=[],
            project_path=str(workspace),
        )
        manager.wal.append_pending(raw.id, raw.model_dump(mode="json"))
        assert len(manager.wal.recover_pending()) == 1

        manager._recover_pending()

        assert manager.wal.recover_pending() == []

        rows = manager._pipeline.event_index.query(limit=10)
        assert len(rows) == 1

        recovered = manager._pipeline.event_index.load_event(rows[0]["id"])
        assert recovered is not None
        assert recovered.raw_data_id == raw.id
        assert recovered.metadata["project_path"] == str(workspace)

        markdown_files = list((data_dir / "events").rglob("*.md"))
        assert len(markdown_files) == 1
        assert recovered.id in markdown_files[0].name

    def test_index_corruption_rebuild(self, tmp_path):
        """测试索引损坏后可从 Markdown 数据源重建。"""
        workspace = tmp_path / "workspace"
        docs_logs = workspace / "docs" / "logs"
        data_events = workspace / ".dimcause" / "events"
        docs_logs.mkdir(parents=True, exist_ok=True)
        data_events.mkdir(parents=True, exist_ok=True)

        self._write_event_markdown(
            docs_logs / "event_docs.md",
            event_id="evt_docs_001",
            summary="docs event",
        )
        self._write_event_markdown(
            data_events / "event_data.md",
            event_id="evt_data_001",
            summary="data event",
        )

        db_path = workspace / ".dimcause" / "index.db"
        index = EventIndex(db_path=str(db_path))

        initial_stats = index.sync(
            [str(docs_logs), str(data_events)],
            base_docs_dir=str(docs_logs),
            base_data_dir=str(data_events),
        )
        assert initial_stats["added"] == 2
        assert index.get_by_id("evt_docs_001") is not None
        assert index.get_by_id("evt_data_001") is not None

        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("DROP TABLE events")
            conn.commit()

        repaired_index = EventIndex(db_path=str(db_path))
        rebuilt_stats = repaired_index.sync(
            [str(docs_logs), str(data_events)],
            base_docs_dir=str(docs_logs),
            base_data_dir=str(data_events),
        )
        assert rebuilt_stats["added"] == 2
        assert repaired_index.get_by_id("evt_docs_001") is not None
        assert repaired_index.get_by_id("evt_data_001") is not None

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_concurrent_write_conflict(self):
        """测试并发写入冲突处理"""
        # TODO: 多进程/线程同时写入，验证数据一致性
        pass

    @staticmethod
    def _write_event_markdown(path: Path, event_id: str, summary: str) -> None:
        content = f"""---
id: {event_id}
type: task
source: manual
timestamp: 2026-03-18T10:00:00
summary: {summary}
tags: []
status: pending
schema_version: 2
---

# {summary}

content for {event_id}
"""
        path.write_text(content, encoding="utf-8")


@pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
def test_real_world_crash_scenario():
    """真实崩溃场景测试"""
    # TODO: 完整模拟：写入 → 崩溃 → 重启 → 恢复 → 验证数据完整
    pass
