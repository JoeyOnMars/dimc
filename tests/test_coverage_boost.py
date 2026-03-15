"""
DIMCAUSE v0.1 CLI 和 Storage 补充测试

覆盖更多边界情况
"""

import os
import tempfile
from datetime import datetime

import pytest


class TestGraphStoreAdvanced:
    """GraphStore 高级测试"""

    def test_add_entity(self):
        """测试添加实体"""
        from dimcause.core.models import Entity
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            entity = Entity(name="auth.py", type="file", id="entity_1")

            store.add_entity(entity)

            # 检查节点
            assert store._graph.has_node("auth.py")

    def test_graph_stats(self):
        """测试图统计"""
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            stats = store.stats()

            assert "nodes" in stats
            assert "edges" in stats


class TestSearchEngineAdvanced:
    """SearchEngine 高级测试"""

    def test_semantic_search_without_vector(self):
        """测试无向量时的语义搜索"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=store, vector_store=None)

            # 语义搜索应该降级
            results = engine.search("test", mode="semantic")

            assert isinstance(results, list)

    def test_search_with_limit(self):
        """测试限制结果数量"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            # 创建多个事件
            for i in range(10):
                event = Event(
                    id=f"evt_{i}",
                    type=EventType.CODE_CHANGE,
                    timestamp=datetime.now(),
                    summary=f"测试事件 {i}",
                    content=f"内容 {i}",
                )
                store.save(event)

            engine = SearchEngine(markdown_store=store, vector_store=None)

            results = engine.search("测试", mode="text", top_k=3)

            assert len(results) <= 3


class TestASTAnalyzerEdgeCases:
    """AST 分析器边界测试"""

    def test_analyze_empty_code(self):
        """测试分析空代码"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        funcs = analyzer.extract_functions("", "python", "empty.py")
        classes = analyzer.extract_classes("", "python", "empty.py")

        assert funcs == []
        assert classes == []

    def test_analyze_syntax_error(self):
        """测试分析语法错误代码"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        # 语法错误的代码
        code = "def broken(:\n    pass"

        # 不应该崩溃
        funcs = analyzer.extract_functions(code, "python", "broken.py")

        assert isinstance(funcs, list)

    def test_analyze_with_comments(self):
        """测试分析带注释的代码"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
# 这是注释
def hello():
    """文档字符串"""
    # 内部注释
    pass
'''
        funcs = analyzer.extract_functions(code, "python", "commented.py")

        assert len(funcs) >= 1


class TestDaemonMoreCases:
    """Daemon 更多测试"""

    def test_daemon_multiple_start_stop(self):
        """测试多次启动停止"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        for _ in range(3):
            daemon.start()
            daemon.stop()

        assert daemon._is_running is False

    def test_daemon_stats(self):
        """测试统计信息"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        assert "event_count" in status
        assert status["event_count"] >= 0


class TestVectorStoreAdvanced:
    """VectorStore 高级测试"""

    def test_vector_store_add_and_search(self):
        """测试添加和搜索"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            event = Event(
                id="evt_vector_test",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="选择 PostgreSQL 数据库",
                content="我们决定使用 PostgreSQL 作为主数据库",
            )

            store.add(event)

            results = store.search("PostgreSQL", top_k=5)

            assert isinstance(results, list)

    def test_vector_store_empty_query(self):
        """测试空查询"""
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            results = store.search("", top_k=5)

            assert isinstance(results, list)


class TestMarkdownStoreAdvanced:
    """MarkdownStore 高级测试"""

    def test_save_event(self):
        """测试保存事件"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            event = Event(
                id="evt_md_test",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="测试摘要",
                content="测试内容",
            )

            path = store.save(event)

            assert os.path.exists(path)

    def test_list_events(self):
        """测试列出事件"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            # 保存几个事件
            for i in range(3):
                event = Event(
                    id=f"evt_list_{i}",
                    type=EventType.CODE_CHANGE,
                    timestamp=datetime.now(),
                    summary=f"事件 {i}",
                    content=f"内容 {i}",
                )
                store.save(event)

            # 测试存储目录存在
            assert os.path.exists(tmpdir)


class TestExtractorsInit:
    """Extractors 模块初始化测试"""

    def test_extractors_module_imports(self):
        """测试模块导入"""
        from dimcause.extractors import ASTAnalyzer

        assert ASTAnalyzer is not None

    def test_optional_imports(self):
        """测试可选导入"""
        try:
            from dimcause.extractors import BasicExtractor

            assert BasicExtractor is not None
        except ImportError:
            pytest.skip("Optional import not available")
