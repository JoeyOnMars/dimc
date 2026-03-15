"""
测试 EventChunker 分块模块

MAL-SEARCH-001 v5.2
"""

import pytest


class TestChunk:
    """测试 Chunk 数据结构"""

    def test_chunk_creation(self):
        """Chunk 应能正确创建"""
        from dimcause.extractors.chunking import Chunk

        chunk = Chunk(
            event_id="evt_001",
            seq=0,
            pos=0,
            text="Hello world",
            token_count=2,
        )

        assert chunk.event_id == "evt_001"
        assert chunk.seq == 0
        assert chunk.pos == 0
        assert chunk.text == "Hello world"
        assert chunk.token_count == 2


class TestEventChunker:
    """测试 EventChunker 分块器"""

    @pytest.fixture
    def chunker(self):
        """创建分块器实例"""
        from dimcause.extractors.chunking import EventChunker

        return EventChunker()

    @pytest.fixture
    def short_event(self):
        """创建短事件 (应只产生 1 个分块)"""
        from datetime import datetime

        from dimcause.core.models import Event, EventType, SourceType

        return Event(
            id="short_001",
            type=EventType.DECISION,
            timestamp=datetime(2026, 2, 2, 12, 0, 0),
            summary="选择使用 BGE 模型",
            content="决定使用 BAAI/bge-small-en-v1.5 作为临时嵌入模型。",
            source=SourceType.MANUAL,
        )

    @pytest.fixture
    def long_event(self):
        """创建长事件 (应产生多个分块)"""
        from datetime import datetime

        from dimcause.core.models import Event, EventType, SourceType

        # 生成足够长的内容以触发多分块
        long_content = "这是一段很长的内容。" * 500  # 约 5000 字符

        return Event(
            id="long_001",
            type=EventType.CODE_CHANGE,
            timestamp=datetime(2026, 2, 2, 14, 0, 0),
            summary="大规模重构代码",
            content=long_content,
            source=SourceType.MANUAL,
        )

    def test_short_event_single_chunk(self, chunker, short_event):
        """短事件应只产生 1 个分块"""
        chunks = chunker.chunk_event(short_event)

        assert len(chunks) == 1
        assert chunks[0].event_id == short_event.id
        assert chunks[0].seq == 0
        assert chunks[0].token_count <= chunker.CHUNK_SIZE

    def test_long_event_multiple_chunks(self, chunker, long_event):
        """长事件应产生多个分块"""
        chunks = chunker.chunk_event(long_event)

        assert len(chunks) > 1

        # 验证分块序号递增
        for i, chunk in enumerate(chunks):
            assert chunk.event_id == long_event.id
            assert chunk.seq == i

    def test_chunk_overlap(self, chunker, long_event):
        """相邻分块应有约 15% 重叠"""
        chunks = chunker.chunk_event(long_event)

        if len(chunks) < 2:
            pytest.skip("事件太短，无法测试重叠")

        # 计算理论步长
        step = int(chunker.CHUNK_SIZE * (1 - chunker.OVERLAP_RATIO))

        # 验证位置差约等于步长
        pos_diff = chunks[1].pos - chunks[0].pos
        assert abs(pos_diff - step) <= step * 0.1  # 允许 10% 误差

    def test_format_event_contains_metadata(self, chunker, short_event):
        """格式化事件应包含关键元数据"""
        formatted = chunker._format_event(short_event)

        assert "type:" in formatted.lower()
        assert "time:" in formatted.lower()
        assert "source:" in formatted.lower()
        assert short_event.summary in formatted

    def test_empty_content_event(self, chunker):
        """空内容事件应返回至少一个分块"""
        from datetime import datetime

        from dimcause.core.models import Event, EventType, SourceType

        event = Event(
            id="empty_001",
            type=EventType.UNKNOWN,
            timestamp=datetime.now(),
            summary="",
            content="",
            source=SourceType.MANUAL,
        )

        chunks = chunker.chunk_event(event)

        # 即使内容为空，也应返回至少一个分块
        assert len(chunks) >= 1
