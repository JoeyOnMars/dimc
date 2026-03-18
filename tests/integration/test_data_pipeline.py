# Covers: SEC-1.2 (Level A) – Markdown as Source of Truth & multi-store consistency

"""
Integration Tests: Data Pipeline End-to-End

验证完整数据流：ingest → Markdown → EventIndex → Vector/Graph
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

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

    @pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
    def test_markdown_to_event_index_sync(self):
        """测试 Markdown → EventIndex 同步"""
        # TODO: 验证 EventIndex.sync() 正确索引 Markdown 文件
        pass

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


@pytest.mark.skip(reason="待 v5.1 核心功能完成后实现")
def test_real_world_event_flow():
    """真实事件流测试"""
    # TODO: 模拟真实场景，从 ClaudeWatcher 捕获到最终可查询
    pass
