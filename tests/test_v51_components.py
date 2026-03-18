"""
DIMCAUSE v0.1 组件测试

测试 Layer 1-4 的核心组件
"""

import os
import tempfile
from datetime import datetime

import pytest


class TestRawDataModel:
    """测试 RawData 数据模型"""

    def test_create_raw_data(self):
        """测试创建 RawData"""
        from dimcause.core.models import RawData, SourceType

        raw = RawData(
            id="claude_20260119_143000",
            source=SourceType.CLAUDE_CODE,
            timestamp=datetime.now(),
            content="Test content",
            metadata={"test": True},
        )

        assert raw.id == "claude_20260119_143000"
        assert raw.source == SourceType.CLAUDE_CODE
        assert raw.content == "Test content"
        assert raw.metadata["test"] is True

    def test_raw_data_files_mentioned(self):
        """测试 files_mentioned 字段"""
        from dimcause.core.models import RawData, SourceType

        raw = RawData(
            id="test_1",
            source=SourceType.CURSOR,
            timestamp=datetime.now(),
            content="Working on auth.py",
            files_mentioned=["auth.py", "login.py"],
        )

        assert len(raw.files_mentioned) == 2
        assert "auth.py" in raw.files_mentioned


class TestEventModel:
    """测试 Event 数据模型"""

    def test_create_event(self):
        """测试创建 Event"""
        from dimcause.core.models import Event, EventType

        event = Event(
            id="evt_001",
            type=EventType.DISCUSSION,  # 使用正确的枚举值
            timestamp=datetime.now(),
            summary="讨论登录功能实现",
            content="详细讨论内容...",
        )

        assert event.id == "evt_001"
        assert event.type == EventType.DISCUSSION
        assert "登录" in event.summary

    def test_event_to_markdown(self):
        """测试 Event 转 Markdown"""
        from dimcause.core.models import Event, EventType

        event = Event(
            id="evt_002",
            type=EventType.CODE_CHANGE,  # 使用正确的枚举值
            timestamp=datetime(2026, 1, 19, 14, 30),
            summary="修复登录 Bug",
            content="修复了空指针问题",
            tags=["bug", "auth"],
        )

        md = event.to_markdown()

        assert "evt_002" in md
        assert "code_change" in md
        assert "修复登录" in md


class TestEntityModel:
    """测试 Entity 数据模型"""

    def test_create_entity(self):
        """测试创建 Entity"""
        from dimcause.core.models import Entity

        entity = Entity(name="auth.py", type="file", context="认证模块")

        assert entity.name == "auth.py"
        assert entity.type == "file"

    def test_entity_hash(self):
        """测试 Entity 哈希"""
        from dimcause.core.models import Entity

        e1 = Entity(name="login", type="function")
        e2 = Entity(name="login", type="function")
        e3 = Entity(name="logout", type="function")

        assert e1 == e2
        assert e1 != e3
        assert hash(e1) == hash(e2)


class TestCodeEntity:
    """测试 CodeEntity 数据模型"""

    def test_create_code_entity(self):
        """测试创建 CodeEntity"""
        from dimcause.core.models import CodeEntity, CodeEntityType

        ce = CodeEntity(
            name="login",
            type=CodeEntityType.FUNCTION,
            file="auth.py",
            line_start=10,
            line_end=25,
            signature="def login(username: str, password: str) -> bool",
        )

        assert ce.name == "login"
        assert ce.type == CodeEntityType.FUNCTION
        assert ce.full_path == "auth.py:login"


class TestMarkdownStore:
    """测试 Markdown 存储"""

    def test_save_and_load(self):
        """测试保存和加载"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            event = Event(
                id="evt_test",
                type=EventType.DISCUSSION,
                timestamp=datetime.now(),
                summary="测试事件",
                content="内容...",
            )

            path = store.save(event)
            assert os.path.exists(path)

            loaded = store.load(path)
            assert loaded is not None
            assert loaded.id == "evt_test"

    def test_list_by_date(self):
        """测试按日期列出"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            # 保存几个事件
            for i in range(3):
                event = Event(
                    id=f"evt_{i}",
                    type=EventType.DISCUSSION,
                    timestamp=datetime.now(),
                    summary=f"事件 {i}",
                    content="...",
                )
                store.save(event)

            # 列出
            start = datetime.now().replace(hour=0, minute=0, second=0)
            end = datetime.now().replace(hour=23, minute=59, second=59)
            files = store.list_by_date(start, end)

            assert len(files) == 3


class TestGraphStore:
    """测试知识图谱存储"""

    def test_add_entity_and_relation(self):
        """测试添加实体和关系"""

        from dimcause.core.models import Entity
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            # 如果 networkx 不可用，跳过
            if store._graph is None:
                pytest.skip("networkx not available")

            # Entity.type 是字符串，不是枚举
            entity1 = Entity(name="auth.py", type="file")
            entity2 = Entity(name="login", type="function")

            store.add_entity(entity1)
            store.add_entity(entity2)
            # [TEST_FIX_REASON] add_relation 废除，"contains" 在结构边白名单内，改为 add_structural_relation。
            store.add_structural_relation("auth.py", "login", "contains")

            related = store.find_related("auth.py", depth=1)

            names = [e.name for e in related]
            assert "login" in names

    def test_stats(self):
        """测试统计信息"""

        from dimcause.core.models import Entity
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            store.add_entity(Entity(name="file1", type="file"))
            store.add_entity(Entity(name="file2", type="file"))
            # [TEST_FIX_REASON] add_relation 废除，"imports" 在结构边白名单内，改为 add_structural_relation。
            store.add_structural_relation("file1", "file2", "imports")

            stats = store.stats()

            assert stats["nodes"] == 2
            assert stats["edges"] == 1


class TestSearchEngine:
    """测试搜索引擎"""

    def test_search_text_mode(self):
        """测试文本搜索模式"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)

            # 保存测试数据
            event = Event(
                id="evt_search_test",
                type=EventType.DISCUSSION,
                timestamp=datetime.now(),
                summary="讨论登录功能",
                content="用户认证模块的实现",
            )
            md_store.save(event)

            # 搜索
            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # text 搜索应该找到结果
            results = engine.search("登录", mode="text", top_k=5)

            # 验证找到了匹配结果
            assert len(results) >= 1
            assert any("登录" in r.summary for r in results)

    def test_search_hybrid_mode(self):
        """测试混合搜索模式"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)

            # 保存多个事件
            for i, keyword in enumerate(["认证", "授权", "登录"]):
                event = Event(
                    id=f"evt_{i}",
                    type=EventType.DISCUSSION,
                    timestamp=datetime.now(),
                    summary=f"讨论{keyword}功能",
                    content=f"{keyword}模块的实现细节",
                )
                md_store.save(event)

            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # hybrid 搜索
            results = engine.search("认证", mode="hybrid", top_k=5)

            assert isinstance(results, list)


class TestLLMConfig:
    """测试 LLM 配置"""

    def test_default_config(self):
        """测试默认配置"""
        from dimcause.core.models import LLMConfig

        config = LLMConfig()

        assert config.provider == "ollama"
        assert config.model == "qwen2:7b"
        assert config.temperature == 0.3

    def test_custom_config(self):
        """测试自定义配置"""
        from dimcause.core.models import LLMConfig

        config = LLMConfig(provider="openai", model="gpt-4", api_key="sk-test")

        assert config.provider == "openai"
        assert config.model == "gpt-4"


class TestDimcauseConfig:
    """测试 Dimcause 完整配置"""

    def test_default_dimcause_config(self):
        """测试默认 Dimcause 配置"""
        from dimcause.core.models import DimcauseConfig

        config = DimcauseConfig()

        assert config.data_dir == "~/.dimcause"
        assert config.watcher_claude.enabled is True
        assert config.local_only is True

    def test_privacy_defaults(self):
        """测试隐私默认值"""
        from dimcause.core.models import DimcauseConfig

        config = DimcauseConfig()

        assert config.redact_api_keys is True
        assert config.redact_passwords is True
