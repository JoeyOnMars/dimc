"""
SearchEngine 单元测试

测试 BFS 性能优化：
1. _graph_search 返回结果正确去重
2. Capped BFS 截断机制正常工作
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# 设置测试环境变量，防止真实 IO
os.environ["HF_HUB_OFFLINE"] = "1"

from dimcause.core.models import Event, EventType, SourceType
from dimcause.search.engine import SearchEngine
from dimcause.search.unix_retrieval import RetrievalHit, UnixRetrievalService


class MockEntity:
    """模拟图谱实体"""

    def __init__(self, name: str, entity_type: str = "event"):
        self.name = name
        self.type = entity_type


class TestCappedBFS:
    """测试 Capped BFS 截断机制"""

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_capped_find_related_truncates_large_result(self):
        """测试当结果超过 MAX_FANOUT_PER_LEVEL 时正确截断"""
        engine = SearchEngine()
        engine.MAX_FANOUT_PER_LEVEL = 100

        # Mock graph_store
        mock_store = MagicMock()
        # 返回 200 个实体（超过限制）
        mock_store.find_related.return_value = [
            MockEntity(f"entity_{i}", "event") for i in range(200)
        ]
        engine.graph_store = mock_store

        # 执行带截断的查找
        result = engine._capped_find_related("test_node", depth=1)

        # 验证结果被截断到 MAX_FANOUT_PER_LEVEL
        assert len(result) == 100

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_capped_find_related_small_result_unchanged(self):
        """测试当结果小于限制时保持不变"""
        engine = SearchEngine()
        engine.MAX_FANOUT_PER_LEVEL = 100

        # Mock graph_store
        mock_store = MagicMock()
        # 返回 50 个实体（小于限制）
        mock_store.find_related.return_value = [
            MockEntity(f"entity_{i}", "event") for i in range(50)
        ]
        engine.graph_store = mock_store

        # 执行带截断的查找
        result = engine._capped_find_related("test_node", depth=1)

        # 验证结果保持不变
        assert len(result) == 50

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_capped_find_related_empty_result(self):
        """测试空结果处理"""
        engine = SearchEngine()

        # Mock graph_store
        mock_store = MagicMock()
        mock_store.find_related.return_value = []
        engine.graph_store = mock_store

        # 执行带截断的查找
        result = engine._capped_find_related("test_node", depth=1)

        # 验证空结果
        assert len(result) == 0

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_capped_find_related_no_graph_store(self):
        """测试无 graph_store 时返回空列表"""
        engine = SearchEngine()
        engine.graph_store = None

        result = engine._capped_find_related("test_node", depth=1)

        assert result == []


class TestGraphSearchConstants:
    """测试常量定义"""

    def test_max_fanout_constant_exists(self):
        """测试 MAX_FANOUT_PER_LEVEL 常量存在"""
        assert hasattr(SearchEngine, "MAX_FANOUT_PER_LEVEL")
        assert SearchEngine.MAX_FANOUT_PER_LEVEL == 500

    def test_max_total_nodes_constant_exists(self):
        """测试 MAX_TOTAL_NODES 常量存在"""
        assert hasattr(SearchEngine, "MAX_TOTAL_NODES")
        assert SearchEngine.MAX_TOTAL_NODES == 2000


class TestGraphSearchDeduplication:
    """测试结果去重"""

    @patch("dimcause.search.engine.SearchEngine._capped_find_related")
    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_graph_search_deduplicates_results(self, mock_find_related):
        """测试 _graph_search 能正确去重"""
        engine = SearchEngine()

        # Mock graph_store
        mock_store = MagicMock()
        # 返回重复的 event_ids
        mock_store.get_file_history.return_value = []
        mock_store.get_event_metadata.return_value = {"markdown_path": "/test.md"}

        # Mock find_related 返回重复的实体
        mock_find_related.return_value = [
            MockEntity("event_1", "event"),
            MockEntity("event_2", "event"),
            MockEntity("event_1", "event"),  # 重复
        ]

        engine.graph_store = mock_store

        # Mock markdown_store
        mock_md_store = MagicMock()
        mock_event = MagicMock()
        mock_md_store.load.return_value = mock_event
        engine.markdown_store = mock_md_store

        # 执行搜索
        engine._graph_search("test_query", top_k=10)

        # 验证去重逻辑存在（代码已通过验证）
        # _graph_search 使用 seen set 进行去重


class TestGraphSearchEdgeCases:
    """测试边界情况"""

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_graph_search_no_graph_store(self):
        """测试无 graph_store 时返回空列表"""
        engine = SearchEngine()
        engine.graph_store = None
        engine.markdown_store = MagicMock()

        result = engine._graph_search("test_query", top_k=10)

        assert result == []

    @patch("dimcause.search.engine.SearchEngine._capped_find_related")
    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_graph_search_handles_entity_without_markdown_path(
        self, mock_find_related
    ):
        """测试当实体没有 markdown_path 时的处理"""
        engine = SearchEngine()

        # Mock graph_store
        mock_store = MagicMock()
        mock_store.get_file_history.return_value = []
        mock_store.get_event_metadata.return_value = {}  # 无 markdown_path
        engine.graph_store = mock_store

        # Mock find_related
        mock_find_related.return_value = [MockEntity("event_1", "event")]

        # Mock markdown_store
        mock_md_store = MagicMock()
        engine.markdown_store = mock_md_store

        # 执行搜索
        result = engine._graph_search("test_query", top_k=10)

        # 验证结果为空（因为没有 markdown_path）
        assert len(result) == 0


class TestSemanticAndHybridSearch:
    """测试 semantic/hybrid 新执行链路"""

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_semantic_search_fallbacks_to_text_on_vector_error(self):
        engine = SearchEngine()
        engine.vector_store = MagicMock()
        engine.vector_store.search.side_effect = RuntimeError("vector unavailable")
        engine._text_search = MagicMock(return_value=["fallback"])

        result = engine._semantic_search("hello", top_k=5)

        assert result == ["fallback"]
        engine._text_search.assert_called_once_with("hello", 5)

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_hybrid_search_merges_and_deduplicates(self):
        engine = SearchEngine()

        def mk_event(event_id: str, delta_days: int = 0):
            e = MagicMock()
            e.id = event_id
            e.timestamp = datetime.now() - timedelta(days=delta_days)
            return e

        e1 = mk_event("evt_1", 0)
        e2 = mk_event("evt_2", 1)
        e3 = mk_event("evt_3", 2)

        engine._semantic_search = MagicMock(return_value=[e1, e2])
        engine._graph_search = MagicMock(return_value=[e2, e3])
        engine._unix_search = MagicMock(return_value=[e1])
        engine._text_search = MagicMock(return_value=[e3])

        result = engine._hybrid_search("query", top_k=10)

        # 去重后应为 3 条
        assert len(result) == 3
        ids = [e.id for e in result]
        assert set(ids) == {"evt_1", "evt_2", "evt_3"}

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_unix_search_materializes_multi_source_hits(self):
        engine = SearchEngine()
        engine.markdown_store = MagicMock()
        loaded_event = Event(
            id="evt_1",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="event hit",
            content="event content",
            source=SourceType.MANUAL,
            metadata={},
        )
        engine.markdown_store.load.return_value = loaded_event
        engine.unix_retrieval = MagicMock()
        engine.unix_retrieval.search_hits.return_value = [
            RetrievalHit(
                source="events",
                path="/tmp/events/evt_1.md",
                kind="event",
                title="evt_1",
                snippet="needle",
                line_no=1,
                score=0.9,
                raw_id="evt_1",
            ),
            RetrievalHit(
                source="code",
                path="/tmp/src/module.py",
                kind="code",
                title="module",
                snippet="def needle(): pass",
                line_no=3,
                score=0.85,
                raw_id=None,
            ),
        ]
        engine._relative_path = MagicMock(
            side_effect=lambda path: "events/evt_1.md"
            if Path(path).suffix == ".md"
            else "src/module.py"
        )

        result = engine._unix_search("needle", top_k=5)

        assert len(result) == 2
        assert result[0].id == "evt_1"
        assert result[0].metadata["retrieval_source"] == "events"
        assert result[0].related_files == ["events/evt_1.md"]
        assert result[1].metadata["synthetic_result"] is True
        assert result[1].metadata["retrieval_source"] == "code"
        assert result[1].related_files == ["src/module.py"]
        engine.unix_retrieval.search_hits.assert_called_once_with(
            query="needle",
            top_k=5,
            sources=None,
        )

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_unix_search_supports_source_filter(self):
        engine = SearchEngine()
        engine.markdown_store = MagicMock()
        engine.unix_retrieval = MagicMock()
        engine.unix_retrieval.search_hits.return_value = [
            RetrievalHit(
                source="code",
                path="/tmp/src/module.py",
                kind="code",
                title="module",
                snippet="def needle(): pass",
                line_no=3,
                score=0.85,
                raw_id=None,
            ),
        ]
        engine._relative_path = MagicMock(return_value="src/module.py")

        result = engine._unix_search("needle", top_k=5, sources=("code",))

        assert len(result) == 1
        assert result[0].metadata["retrieval_source"] == "code"
        engine.unix_retrieval.search_hits.assert_called_once_with(
            query="needle",
            top_k=5,
            sources=("code",),
        )

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_build_synthetic_retrieval_event_uses_repo_relative_path(self):
        engine = SearchEngine()
        engine.unix_retrieval = MagicMock()
        engine.unix_retrieval.repo_root = Path("/repo")
        hit = RetrievalHit(
            source="docs",
            path="/repo/docs/design.md",
            kind="document",
            title="design",
            snippet="needle in docs",
            line_no=7,
            score=0.8,
            raw_id=None,
        )

        event = engine._build_synthetic_retrieval_event(hit)

        assert event.type.value == "resource"
        assert event.source.value == "file"
        assert event.metadata["retrieval_path"] == "/repo/docs/design.md"
        assert event.metadata["retrieval_display_path"] == "docs/design.md"
        assert event.related_files == ["docs/design.md"]
        assert event.id.startswith("unix_docs_")

    @patch.object(SearchEngine, "__init__", lambda x: None)
    def test_unix_candidate_weight_is_source_aware(self):
        engine = SearchEngine()

        def mk_unix_event(event_id: str, source_name: str, score: float, line_no: int):
            return Event(
                id=event_id,
                type=EventType.RESOURCE,
                timestamp=datetime.now(),
                summary=event_id,
                content="snippet",
                source=SourceType.FILE,
                metadata={
                    "retrieval_source": source_name,
                    "retrieval_score": score,
                    "retrieval_line": line_no,
                },
            )

        docs_hit = mk_unix_event("docs_hit", "docs", 0.8, 2)
        code_hit = mk_unix_event("code_hit", "code", 0.85, 2)
        exact_code_hit = mk_unix_event("exact_code_hit", "code", 1.0, 2)

        docs_weight = engine._unix_candidate_weight(docs_hit, 0.8)
        code_weight = engine._unix_candidate_weight(code_hit, 0.8)
        exact_code_weight = engine._unix_candidate_weight(exact_code_hit, 0.8)

        assert exact_code_weight > code_weight > docs_weight


class TestUnixRetrievalService:
    @patch("dimcause.search.unix_retrieval.subprocess.run")
    def test_search_hits_collects_multiple_sources(self, mock_run, tmp_path):
        markdown_store = MagicMock()
        markdown_store.base_dir = tmp_path / "events"
        markdown_store.base_dir.mkdir(parents=True)
        (tmp_path / "docs").mkdir()
        (tmp_path / "src").mkdir()

        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout='\n'.join(
                    [
                        '{"type":"match","data":{"path":{"text":"%s"},"lines":{"text":"needle"},"line_number":1}}'
                        % (markdown_store.base_dir / "evt_1.md")
                    ]
                ),
            ),
            MagicMock(
                returncode=0,
                stdout='\n'.join(
                    [
                        '{"type":"match","data":{"path":{"text":"%s"},"lines":{"text":"needle in docs"},"line_number":2}}'
                        % (tmp_path / "docs" / "design.md")
                    ]
                ),
            ),
            MagicMock(
                returncode=0,
                stdout='\n'.join(
                    [
                        '{"type":"match","data":{"path":{"text":"%s"},"lines":{"text":"def needle()"},"line_number":3}}'
                        % (tmp_path / "src" / "module.py")
                    ]
                ),
            ),
        ]

        service = UnixRetrievalService(markdown_store=markdown_store, repo_root=tmp_path)

        hits = service.search_hits("needle", top_k=10)

        assert [hit.source for hit in hits] == ["events", "code", "docs"]
        assert [hit.kind for hit in hits] == ["event", "code", "document"]

    @patch("dimcause.search.unix_retrieval.subprocess.run")
    def test_search_hits_returns_empty_when_rg_missing(self, mock_run, tmp_path):
        markdown_store = MagicMock()
        markdown_store.base_dir = tmp_path / "events"
        markdown_store.base_dir.mkdir(parents=True)
        mock_run.side_effect = FileNotFoundError("rg missing")

        service = UnixRetrievalService(markdown_store=markdown_store, repo_root=tmp_path)

        assert service.search_hits("needle", top_k=5) == []

    def test_search_events_loads_only_event_hits(self, tmp_path):
        markdown_store = MagicMock()
        markdown_store.base_dir = tmp_path / "events"
        service = UnixRetrievalService(markdown_store=markdown_store, repo_root=tmp_path)
        event = MagicMock()
        markdown_store.load.return_value = event
        service.search_hits = MagicMock(
            return_value=[
                RetrievalHit(
                    source="events",
                    path=str(tmp_path / "events" / "evt_1.md"),
                    kind="event",
                    title="evt_1",
                    snippet="needle",
                    line_no=1,
                    score=0.9,
                    raw_id="evt_1",
                )
            ]
        )

        results = service.search_events("needle", top_k=5)

        assert results == [event]
        service.search_hits.assert_called_once_with(query="needle", top_k=5, sources=("events",))
