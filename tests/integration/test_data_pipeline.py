# Covers: SEC-1.2 (Level A) – Markdown as Source of Truth & multi-store consistency

"""
Integration Tests: Data Pipeline End-to-End

验证完整数据流：ingest → Markdown → EventIndex → Vector/Graph
"""

import time
from datetime import datetime
from pathlib import Path

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.models import DimcauseConfig, EventType, RawData, SourceType
from dimcause.extractors.extractor import BasicExtractor
from dimcause.services.pipeline import Pipeline


class TestDataPipeline:
    """测试完整数据管道"""

    def test_ingest_to_markdown_write(self, tmp_path: Path):
        """测试 ingest → Markdown 写入（真实最小链路，无 extractor mock）"""
        pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
        pipeline.extractor = BasicExtractor(llm_client=None)

        raw = RawData(
            id="raw_pipeline_ingest_markdown",
            source=SourceType.CLAUDE_CODE,
            timestamp=datetime.now(),
            content="我们决定先补齐 ingest 到 markdown 最小链路。",
        )

        before_count = len(pipeline.event_index.query(limit=1000))
        pipeline.process(raw)
        rows = pipeline.event_index.query(limit=10)
        assert len(rows) == before_count + 1

        row = rows[0]
        assert row is not None
        markdown_path = Path(row["markdown_path"])
        assert markdown_path.exists()
        assert markdown_path.read_text(encoding="utf-8")
        stored = pipeline.event_index.load_event(row["id"])
        assert stored is not None
        assert stored.raw_data_id == raw.id
        assert stored.type in {EventType.DECISION, EventType.UNKNOWN}

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

    def test_end_to_end_query(self):
        """测试完整查询链路（ingest -> EventIndex query）"""
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            pipeline = Pipeline(config=DimcauseConfig(data_dir=tmpdir))
            pipeline.extractor = BasicExtractor(llm_client=None)

            raw = RawData(
                id="raw_pipeline_query_001",
                source=SourceType.MANUAL,
                timestamp=datetime.now(),
                content="我们决定采用事件索引进行查询验证。",
            )
            pipeline.process(raw)

            decision_rows = pipeline.event_index.query(type=EventType.DECISION, limit=20)
            if not decision_rows:
                decision_rows = pipeline.event_index.query(type=EventType.UNKNOWN, limit=20)

            assert decision_rows, "ingest 后应可通过 EventIndex 查询到事件"
            event = pipeline.event_index.load_event(decision_rows[0]["id"])
            assert event is not None
            assert event.raw_data_id == raw.id

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
