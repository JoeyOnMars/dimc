# Covers: SEC-1.2 (Level A) – Markdown as Source of Truth & EventIndex consistency

import sqlite3
import time
from datetime import datetime

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType


class TestEventIndex:
    @pytest.fixture
    def db_path(self, tmp_path):
        return tmp_path / "test_index.db"

    @pytest.fixture
    def event_index(self, db_path):
        return EventIndex(str(db_path))

    @pytest.fixture
    def sample_event(self):
        return Event(
            id="evt_test_123",
            type=EventType.DECISION,
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            summary="Test Summary",
            content="Test Content",
            tags=["test", "unit"],
        )

    def test_schema_creation(self, event_index, db_path):
        """测试表结构是否创建成功"""
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_add_and_query(self, event_index, sample_event, tmp_path):
        """测试添加和查询"""
        md_path = tmp_path / "test.md"
        md_path.touch()

        # Add
        success = event_index.add(sample_event, str(md_path))
        assert success is True

        # Query
        results = event_index.query(type=EventType.DECISION)
        assert len(results) == 1
        assert results[0]["id"] == sample_event.id
        assert results[0]["summary"] == "Test Summary"

        # Query by ID
        item = event_index.get_by_id(sample_event.id)
        assert item is not None
        assert item["id"] == sample_event.id

    def test_load_event_cache(self, event_index, sample_event, tmp_path):
        """测试从缓存加载"""
        md_path = tmp_path / "test.md"
        md_path.touch()
        event_index.add(sample_event, str(md_path))

        # Load
        loaded = event_index.load_event(sample_event.id)
        assert loaded is not None
        assert loaded.id == sample_event.id
        assert loaded.summary == sample_event.summary
        assert isinstance(loaded.timestamp, datetime)

    def test_load_event_file_fallback(self, event_index, sample_event, tmp_path):
        """测试缓存缺失时回文件读取"""
        md_path = tmp_path / "fallback.md"
        md_path.write_text(sample_event.to_markdown(), encoding="utf-8")

        # Add but invalidate cache
        event_index.add(sample_event, str(md_path))
        event_index.invalidate_cache(sample_event.id)

        # Verify cache is gone
        item = event_index.get_by_id(sample_event.id)
        assert item["json_cache"] is None

        # Load (should read file)
        loaded = event_index.load_event(sample_event.id)
        assert loaded is not None
        assert loaded.id == sample_event.id

        # Verify cache is restored
        item = event_index.get_by_id(sample_event.id)
        assert item["json_cache"] is not None

    def test_remove(self, event_index, sample_event, tmp_path):
        """测试删除"""
        md_path = tmp_path / "del.md"
        md_path.touch()
        event_index.add(sample_event, str(md_path))

        assert event_index.get_by_id(sample_event.id) is not None

        success = event_index.remove(sample_event.id)
        assert success is True

        assert event_index.get_by_id(sample_event.id) is None

    def test_sync(self, event_index, sample_event, tmp_path):
        """测试同步功能"""
        # 1. Prepare files
        # EventIndex requires scanning both docs and data dirs
        docs_dir = tmp_path / "docs" / "logs"
        docs_dir.mkdir(parents=True)

        events_dir = tmp_path / "events"
        events_dir.mkdir(parents=True)

        # Valid event file in events dir
        file1 = events_dir / "evt1.md"
        file1.write_text(sample_event.to_markdown(), encoding="utf-8")

        # Another valid event
        evt2 = sample_event.model_copy()
        evt2.id = "evt_test_456"
        file2 = events_dir / "evt2.md"
        file2.write_text(evt2.to_markdown(), encoding="utf-8")

        # Invalid file (no frontmatter)
        file3 = events_dir / "readme.md"
        file3.write_text("# Just a readme", encoding="utf-8")

        # 2. First Sync
        # Must pass base dirs and scan both
        stats = event_index.sync(
            scan_paths=[docs_dir, events_dir], base_docs_dir=docs_dir, base_data_dir=events_dir
        )
        assert stats["added"] == 2
        assert stats["updated"] == 0
        assert stats["skipped"] == 0

        # 3. Second Sync (No changes)
        stats = event_index.sync(
            scan_paths=[docs_dir, events_dir], base_docs_dir=docs_dir, base_data_dir=events_dir
        )
        assert stats["added"] == 0
        assert stats["skipped"] >= 2  # Might skip readme too or explicitly skip it

        # 4. Modify file
        time.sleep(0.1)  # Ensure mtime changes
        file1.touch()

        stats = event_index.sync(
            scan_paths=[docs_dir, events_dir], base_docs_dir=docs_dir, base_data_dir=events_dir
        )
        # Content unchanged, but mtime changed -> parsed -> same ID -> update
        assert stats["updated"] == 1
        # other file skipped
        assert stats["skipped"] >= 1
