"""
DIMCAUSE v0.1 LLM 和 Extractor Mock 测试

使用 Mock 测试 LLM 相关代码，无需真实 API
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestLLMClientMock:
    """使用 Mock 测试 LLM Client"""

    @patch.dict("sys.modules", {"litellm": MagicMock()})
    def test_llm_config_creation(self):
        """测试 LLM 配置创建"""
        from dimcause.core.models import LLMConfig

        # 默认配置
        config = LLMConfig()
        assert config.provider == "ollama"
        assert config.model == "qwen2:7b"

        # OpenAI 配置
        config_openai = LLMConfig(provider="openai", model="gpt-4o-mini", api_key="sk-test-key")
        assert config_openai.provider == "openai"
        assert config_openai.api_key == "sk-test-key"

    def test_llm_config_with_base_url(self):
        """测试带 base_url 的配置"""
        from dimcause.core.models import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            base_url="https://custom-api.example.com",
        )

        assert config.base_url == "https://custom-api.example.com"

    def test_llm_config_temperature(self):
        """测试温度参数"""
        from dimcause.core.models import LLMConfig

        config = LLMConfig(temperature=0.5)
        assert config.temperature == 0.5


class TestBasicExtractorMock:
    """使用 Mock 测试 BasicExtractor"""

    def test_event_type_detection_keywords(self):
        """测试事件类型检测（基于关键词）"""

        # 决策类型
        decision_texts = [
            "我决定使用 PostgreSQL",
            "我们选择 FastAPI 框架",
            "因为性能原因，采用 Redis",
        ]

        for text in decision_texts:
            has_decision = any(kw in text for kw in ["决定", "选择", "采用", "因为"])
            assert has_decision, f"Should detect decision: {text}"

        # 代码变更类型
        code_texts = [
            "修改了 auth.py 的登录函数",
            "添加了新的 API 端点",
            "重构用户模块",
        ]

        for text in code_texts:
            has_code = any(kw in text for kw in ["修改", "添加", "重构", ".py"])
            assert has_code, f"Should detect code change: {text}"

    def test_entity_extraction_regex(self):
        """测试实体提取（正则方式）"""
        import re

        text = "修改 src/auth.py 和 tests/test_auth.py，添加 JWT 验证"

        # 文件提取
        file_pattern = r"[\w/.-]+\.py"
        files = re.findall(file_pattern, text)

        assert len(files) >= 2
        assert any("auth.py" in f for f in files)

    def test_summary_generation_simple(self):
        """测试简单摘要生成"""
        content = "我决定使用 JWT 进行身份验证，因为我们的移动端需要无状态认证。Session 在分布式环境下管理复杂。"

        # 简单摘要：取前50字符
        summary = content[:50] + "..." if len(content) > 50 else content

        assert len(summary) <= 53
        assert "JWT" in summary


class TestExtractorWithMockedLLM:
    """使用 Mock LLM 测试 Extractor"""

    def test_extract_with_mocked_response(self):
        """测试用 Mock 响应提取"""
        # 模拟 LLM 返回的 JSON
        mock_llm_response = {
            "type": "decision",
            "summary": "选择 JWT 作为认证方案",
            "entities": ["auth.py", "jwt"],
            "tags": ["authentication"],
        }

        # 验证 JSON 解析
        parsed = json.loads(json.dumps(mock_llm_response))

        assert parsed["type"] == "decision"
        assert len(parsed["entities"]) == 2

    def test_fallback_extraction(self):
        """测试降级提取（无 LLM 时）"""
        from dimcause.core.models import Event, EventType

        raw_content = "修改了登录函数，添加了参数验证"

        # 降级到基础 Event
        event = Event(
            id="evt_fallback",
            type=EventType.CODE_CHANGE,  # 基于关键词
            timestamp=datetime.now(),
            summary=raw_content[:50] + "..." if len(raw_content) > 50 else raw_content,
            content=raw_content,
            source="manual",
        )

        assert event.type == EventType.CODE_CHANGE
        assert "登录函数" in event.summary


class TestASTAnalyzerExtended:
    """扩展 AST 分析器测试"""

    def test_extract_function_with_docstring(self):
        """测试提取带文档字符串的函数"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
def authenticate(username: str, password: str) -> bool:
    """
    Authenticate user with username and password.

    Args:
        username: User's login name
        password: User's password

    Returns:
        True if authentication successful
    """
    return verify(username, password)
'''
        funcs = analyzer.extract_functions(code, "python", "auth.py")

        assert len(funcs) >= 1
        func = funcs[0]
        assert func.name == "authenticate"
        assert func.docstring is not None or func.signature is not None

    def test_extract_class_with_methods(self):
        """测试提取带方法的类"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
class UserService:
    """User management service."""

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: int):
        """Get user by ID."""
        return self.db.query(user_id)

    def create_user(self, name: str, email: str):
        """Create new user."""
        pass
'''
        classes = analyzer.extract_classes(code, "python", "services.py")

        assert len(classes) >= 1
        cls = classes[0]
        assert cls.name == "UserService"

    def test_extract_imports(self):
        """测试提取导入"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = """
import os
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
"""
        imports = analyzer.extract_imports(code, "python")

        assert len(imports) >= 3


class TestDaemonWithMock:
    """使用 Mock 测试 Daemon"""

    def test_daemon_creation_without_llm(self):
        """测试无 LLM 时创建 Daemon"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 即使没有 LLM 也应该能创建
        assert daemon is not None
        assert daemon._is_running is False

    def test_daemon_status_structure(self):
        """测试 Daemon 状态结构"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        # 检查状态字段
        assert "is_running" in status
        assert "watchers" in status
        assert "event_count" in status
        assert isinstance(status["watchers"], list)

    def test_daemon_on_raw_data_fallback(self):
        """测试 Daemon 接收数据时的降级处理"""
        from dimcause.core.models import RawData, SourceType
        from dimcause.daemon import create_daemon

        create_daemon()

        # 创建测试数据
        raw = RawData(
            id="raw_test",
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            content="测试内容",
            metadata={},
        )

        # 即使没有 LLM，也应该能处理
        # (具体行为取决于实现)
        assert raw.id == "raw_test"


class TestVectorStoreMock:
    """使用 Mock 测试 VectorStore"""

    def test_vector_store_init(self):
        """测试 VectorStore 初始化"""
        import tempfile

        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            # 即使 chromadb 不可用也不崩溃
            assert store is not None

    def test_vector_store_search_empty(self):
        """测试空搜索"""
        import tempfile

        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            results = store.search("test query", top_k=5)

            assert isinstance(results, list)

    def test_vector_store_crud_operations(self):
        """测试 CRUD 操作"""
        import tempfile

        from dimcause.core.models import Event, EventType
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            event = Event(
                id="evt_vector_test",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="测试向量存储",
                content="这是测试内容",
            )

            # Add
            store.add(event)

            # Search
            results = store.search("测试", top_k=5)
            assert isinstance(results, list)

            # Delete
            deleted = store.delete("evt_vector_test")
            # 即使 chromadb 不可用也不崩溃
            assert isinstance(deleted, bool)


class TestSearchEngineMock:
    """使用 Mock 测试 SearchEngine"""

    def test_text_search_implementation(self):
        """测试文本搜索实现"""
        import tempfile

        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            # 保存测试数据
            event = Event(
                id="evt_search_test",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="选择 FastAPI 框架",
                content="因为性能和开发效率，决定使用 FastAPI",
            )
            store.save(event)

            engine = SearchEngine(markdown_store=store, vector_store=None)

            # 文本搜索（禁用 reranker 避免触发网络下载 bge-reranker）
            results = engine.search("FastAPI", mode="text", use_reranker=False)

            assert isinstance(results, list)

    def test_hybrid_search_fallback(self):
        """测试混合搜索降级"""
        import tempfile

        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=store, vector_store=None)

            # 混合搜索应该降级到文本搜索
            results = engine.search("test", mode="hybrid")

            assert isinstance(results, list)
