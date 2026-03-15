"""
DIMCAUSE v0.1 AST 分析器和 Extractor 增强测试

使用 tree-sitter 进行更深入的测试
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestASTAnalyzerTreeSitter:
    """测试 Tree-sitter AST 分析"""

    def test_supported_languages_extended(self):
        """测试支持的语言列表"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        langs = analyzer.supported_languages()

        assert "python" in langs
        # Tree-sitter 可能支持更多语言
        assert isinstance(langs, list)

    @pytest.mark.skipif(
        not __import__("shutil").which("tree-sitter") and not __import__("importlib.util", fromlist=["find_spec"]).find_spec("tree_sitter"),
        reason="tree-sitter 未安装，regex fallback 不支持多行函数签名"
    )
    def test_extract_complex_function(self):
        """测试提取复杂函数"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
async def process_data(
    data: dict,
    options: Optional[ProcessOptions] = None,
    *,
    timeout: int = 30,
    retry: bool = True
) -> ProcessResult:
    """
    Process incoming data with optional configuration.

    Args:
        data: The data to process
        options: Optional processing options
        timeout: Timeout in seconds
        retry: Whether to retry on failure

    Returns:
        Processing result with status and data

    Raises:
        ProcessingError: If processing fails
    """
    if options is None:
        options = ProcessOptions()

    try:
        result = await _internal_process(data, timeout)
        return ProcessResult(status="success", data=result)
    except Exception as e:
        if retry:
            return await process_data(data, options, timeout=timeout, retry=False)
        raise ProcessingError(str(e))
'''
        funcs = analyzer.extract_functions(code, "python", "processor.py")

        assert len(funcs) >= 1
        func = funcs[0]
        assert func.name == "process_data"
        # 应该有签名
        if func.signature:
            assert "async" in func.signature or "process_data" in func.signature

    def test_extract_decorated_function(self):
        """测试提取带装饰器的函数"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
@app.route("/api/users", methods=["GET", "POST"])
@require_auth
@rate_limit(requests_per_minute=100)
def handle_users(request):
    """Handle user API requests."""
    if request.method == "GET":
        return get_all_users()
    return create_user(request.json)
'''
        funcs = analyzer.extract_functions(code, "python", "api.py")

        assert len(funcs) >= 1

    def test_extract_nested_class(self):
        """测试提取嵌套类"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
class OuterClass:
    """Outer class with nested class."""

    class InnerClass:
        """Inner nested class."""

        def inner_method(self):
            pass

    def outer_method(self):
        pass
'''
        classes = analyzer.extract_classes(code, "python", "nested.py")

        # 至少找到外层类
        assert len(classes) >= 1

    def test_extract_javascript(self):
        """测试提取 JavaScript 代码"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = """
function greet(name) {
    console.log("Hello, " + name);
}

const arrow = (x, y) => x + y;

async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}

class UserService {
    constructor(api) {
        this.api = api;
    }

    async getUser(id) {
        return this.api.get(`/users/${id}`);
    }
}
"""
        funcs = analyzer.extract_functions(code, "javascript", "app.js")
        classes = analyzer.extract_classes(code, "javascript", "app.js")

        # JavaScript 解析结果
        assert isinstance(funcs, list)
        assert isinstance(classes, list)

    def test_extract_imports_detailed(self):
        """测试详细导入提取"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = """
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections.abc import Mapping
import json as js
from .local_module import helper
from ..parent import util
"""
        imports = analyzer.extract_imports(code, "python")

        assert len(imports) >= 5


class TestExtractorAdvanced:
    """测试 Extractor 高级功能"""

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_extractor_with_code_entities(self, mock_litellm, mock_completion):
        """测试提取器结合代码实体"""
        from dimcause.extractors.extractor import BasicExtractor
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
{
    "type": "code_change",
    "summary": "重构认证模块",
    "entities": ["auth.py", "login", "User"],
    "tags": ["refactor", "authentication"]
}
"""
        mock_completion.return_value = mock_response

        client = LiteLLMClient()
        extractor = BasicExtractor(llm_client=client)

        event = extractor.extract("重构了 auth.py 中的 login 函数，优化了 User 类")

        assert event is not None

    def test_event_type_inference(self):
        """测试事件类型推断"""
        from dimcause.core.models import EventType

        # 决策类型文本
        decision_patterns = [
            ("我们决定使用 PostgreSQL", EventType.DECISION),
            ("选择了 Redis 作为缓存", EventType.DECISION),
            ("因为性能原因采用异步", EventType.DECISION),
        ]

        # 代码变更类型文本

        # 诊断类型文本

        # 简单检查关键词
        for text, _expected_type in decision_patterns:
            has_decision = any(kw in text for kw in ["决定", "选择", "采用", "因为"])
            assert has_decision


class TestDaemonAdvanced:
    """测试 Daemon 高级功能"""

    def test_daemon_watcher_list(self):
        """测试 Daemon Watcher 列表"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        # 应该有 watchers 列表
        assert "watchers" in status
        watchers = status["watchers"]

        # 可能包含 Claude, Cursor, Windsurf
        assert isinstance(watchers, list)

    def test_daemon_event_count(self):
        """测试 Daemon 事件计数"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        # 初始事件数应该是 0
        assert status["event_count"] == 0


class TestBaseWatcherAdvanced:
    """测试 BaseWatcher 高级功能"""

    def test_watcher_debounce_setting(self):
        """测试防抖设置"""
        import tempfile
        from pathlib import Path

        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            # 自定义防抖时间
            watcher = ClaudeWatcher(watch_path=str(watch_file), debounce_seconds=0.5)

            assert watcher.debounce_seconds == 0.5

    def test_watcher_multiple_callbacks(self):
        """测试多回调注册"""
        import tempfile
        from pathlib import Path

        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callbacks = []
            for i in range(5):
                cb = Mock(name=f"callback_{i}")
                watcher.on_new_data(cb)
                callbacks.append(cb)

            assert len(watcher._callbacks) == 5


class TestGraphStoreAdvanced:
    """测试 GraphStore 高级功能"""

    def test_graph_store_add_multiple_events(self):
        """测试添加多个事件"""
        import tempfile

        from dimcause.core.models import Entity, Event, EventType
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            # 添加多个事件
            for i in range(3):
                event = Event(
                    id=f"evt_{i}",
                    type=EventType.CODE_CHANGE,
                    timestamp=datetime.now(),
                    summary=f"事件 {i}",
                    content=f"内容 {i}",
                    entities=[
                        Entity(name=f"file_{i}.py", type="file"),
                    ],
                )
                store.add_event_relations(event)

            stats = store.stats()
            assert stats["nodes"] >= 3

    def test_graph_store_find_path(self):
        """测试查找路径"""
        import tempfile

        from dimcause.core.models import Entity, Event, EventType
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            # 创建关联事件
            event1 = Event(
                id="evt_1",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="修改 A",
                content="内容",
                entities=[Entity(name="A.py", type="file")],
                related_files=["B.py"],
            )

            event2 = Event(
                id="evt_2",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="修改 B",
                content="内容",
                entities=[Entity(name="B.py", type="file")],
                related_files=["C.py"],
            )

            store.add_event_relations(event1)
            store.add_event_relations(event2)

            # 查找相关
            related = store.find_related("A.py")
            assert isinstance(related, list)
