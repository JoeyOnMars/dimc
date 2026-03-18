# Covers: SEC-1.2 (Level A) – Markdown as Source of Truth & multi-store consistency

"""
Integration Tests: Data Pipeline End-to-End

验证完整数据流：ingest → Markdown → EventIndex → Vector/Graph
"""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.models import DimcauseConfig, Event, EventType, RawData, SourceType
from dimcause.services.pipeline import Pipeline


class TestDataPipeline:
    """测试完整数据管道"""

    def test_ingest_to_markdown_write(self, tmp_path: Path):
        """测试 ingest → Markdown 写入（当前可执行最小链路）"""
        pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
        pipeline.vector_store = Mock()
        pipeline.graph_store = Mock()
        pipeline.reasoning_engine = None

        pipeline.extractor = Mock()
        event = Event(
            id="evt_pipeline_ingest_markdown",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="ingest to markdown",
            content="验证 ingest 后 markdown 和 EventIndex 同步落地。",
        )
        pipeline.extractor.extract.return_value = event

        raw = RawData(
            id="raw_pipeline_ingest_markdown",
            source=SourceType.CLAUDE_CODE,
            timestamp=datetime.now(),
            content="我们决定先补齐 ingest -> markdown 最小链路。",
        )

        pipeline.process(raw)

        row = pipeline.event_index.get_by_id(event.id)
        assert row is not None
        markdown_path = Path(row["markdown_path"])
        assert markdown_path.exists()
        assert markdown_path.read_text(encoding="utf-8")
        stored = pipeline.event_index.load_event(event.id)
        assert stored is not None
        assert stored.summary == "ingest to markdown"
        assert stored.raw_data_id == raw.id

    def test_markdown_to_event_index_sync(self, tmp_path: Path):
        """测试 Markdown → EventIndex 同步"""
        workspace = tmp_path / "workspace"
        docs_logs = workspace / "docs" / "logs"
        data_events = workspace / ".dimcause" / "events"
        docs_logs.mkdir(parents=True, exist_ok=True)
        data_events.mkdir(parents=True, exist_ok=True)

        markdown_file = docs_logs / "event_sync.md"
        self._write_event_markdown(markdown_file, event_id="evt_pipeline_sync", summary="sync v1")

        index = EventIndex(db_path=str(workspace / ".dimcause" / "index.db"))
        first_sync = index.sync(
            [str(docs_logs), str(data_events)],
            base_docs_dir=str(docs_logs),
            base_data_dir=str(data_events),
        )
        assert first_sync["added"] == 1
        assert first_sync["errors"] == 0

        row = index.get_by_id("evt_pipeline_sync")
        assert row is not None
        assert Path(row["markdown_path"]).resolve() == markdown_file.resolve()
        loaded = index.load_event("evt_pipeline_sync")
        assert loaded is not None
        assert loaded.summary == "sync v1"

        second_sync = index.sync(
            [str(docs_logs), str(data_events)],
            base_docs_dir=str(docs_logs),
            base_data_dir=str(data_events),
        )
        assert second_sync["added"] == 0
        assert second_sync["updated"] == 0
        assert second_sync["skipped"] >= 1

        time.sleep(0.01)
        self._write_event_markdown(markdown_file, event_id="evt_pipeline_sync", summary="sync v2")
        third_sync = index.sync(
            [str(docs_logs), str(data_events)],
            base_docs_dir=str(docs_logs),
            base_data_dir=str(data_events),
        )
        assert third_sync["updated"] == 1
        refreshed = index.load_event("evt_pipeline_sync")
        assert refreshed is not None
        assert refreshed.summary == "sync v2"

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_event_index_to_vector_store(self):
        """测试 EventIndex → VectorStore 写入"""
        # TODO: 验证向量化和写入
        pass

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_partial_failure_vector_store(self):
        """测试 VectorStore 失败但 Markdown 成功"""
        # TODO: 模拟 VectorStore 失败，验证 Markdown 仍然写入成功
        #       并确保失败任务进入 RepairQueue
        pass

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_end_to_end_query(self):
        """测试完整查询链路"""
        # TODO: 写入事件后，通过 EventIndex 查询并验证一致性
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
def test_real_world_event_flow():
    """真实事件流测试"""
    # TODO: 模拟真实场景，从 ClaudeWatcher 捕获到最终可查询
    pass
