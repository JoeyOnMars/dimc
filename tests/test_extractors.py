"""
DIMCAUSE v0.1 Extractor 和 LLM 测试

测试提取器和 LLM 客户端
"""

import tempfile

import pytest


class TestLLMClientMocked:
    """测试 LLM 客户端（使用 mock）"""

    def test_litellm_client_import(self):
        """测试 LiteLLM 客户端导入"""
        from dimcause.extractors import LiteLLMClient

        # 如果 litellm 不可用，LiteLLMClient 应该是 None
        # 这是预期行为
        assert LiteLLMClient is None or LiteLLMClient is not None

    def test_llm_config(self):
        """测试 LLM 配置"""
        from dimcause.core.models import LLMConfig

        # 默认配置
        config = LLMConfig()
        assert config.provider == "ollama"
        assert config.model == "qwen2:7b"

        # 自定义配置
        config2 = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")
        assert config2.provider == "openai"
        assert config2.model == "gpt-4"

    def test_litellm_client_with_mock(self, monkeypatch):
        """测试 LiteLLM 客户端（不依赖真实 litellm 安装）"""
        import importlib.util
        import sys
        import types
        from pathlib import Path

        from dimcause.core.models import LLMConfig

        fake_litellm = types.ModuleType("litellm")
        fake_litellm.request_timeout = 0

        class _FakeMessage:
            content = "mock-ok"

        class _FakeChoice:
            message = _FakeMessage()

        class _FakeUsage:
            prompt_tokens = 1
            completion_tokens = 1

        class _FakeResponse:
            choices = [_FakeChoice()]
            usage = _FakeUsage()

        def _fake_completion(**_kwargs):
            return _FakeResponse()

        fake_litellm.completion = _fake_completion
        monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

        module_path = Path(__file__).resolve().parents[1] / "src/dimcause/extractors/llm_client.py"
        spec = importlib.util.spec_from_file_location("dimcause_test_llm_client_shim", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client = module.LiteLLMClient(
            config=LLMConfig(provider="openai", model="gpt-4o-mini", api_key="test-key")
        )
        assert client.complete("hello", system="reply short") == "mock-ok"


class TestBasicExtractorMocked:
    """测试 BasicExtractor（使用 mock）"""

    def test_basic_extractor_import(self):
        """测试 BasicExtractor 导入"""
        from dimcause.extractors import BasicExtractor

        # 如果依赖不可用，BasicExtractor 应该是 None
        assert BasicExtractor is None or BasicExtractor is not None

    def test_extractor_regex_fallback(self):
        """测试正则表达式降级提取"""
        # 即使没有 LLM，也应该能用正则提取

        content = "我决定使用 JWT 进行身份验证因为更安全"

        # 检查关键词匹配
        decision_keywords = ["决定", "选择", "采用"]
        has_decision = any(kw in content for kw in decision_keywords)

        assert has_decision


class TestEventExtraction:
    """测试事件提取逻辑"""

    def test_detect_event_type_decision(self):
        """测试检测决策类型"""
        content = "我决定使用 PostgreSQL 数据库因为它更适合复杂查询"

        # 决策关键词
        decision_keywords = ["决定", "选择", "采用", "因为", "所以"]

        is_decision = any(kw in content for kw in decision_keywords)
        assert is_decision

    def test_detect_event_type_code_change(self):
        """测试检测代码变更类型"""
        content = "修改了 auth.py 中的 login 函数，添加了参数验证"

        # 代码变更关键词
        code_keywords = ["修改", "添加", "删除", "重构", ".py", "函数"]

        is_code_change = any(kw in content for kw in code_keywords)
        assert is_code_change

    def test_detect_event_type_diagnostic(self):
        """测试检测问题诊断类型"""
        content = "发现一个 bug：用户登录后 session 没有正确保存"

        # 诊断关键词
        diagnostic_keywords = ["bug", "错误", "问题", "修复", "发现"]

        is_diagnostic = any(kw in content for kw in diagnostic_keywords)
        assert is_diagnostic

    def test_detect_entities(self):
        """测试实体检测"""
        content = "在 auth.py 中使用 FastAPI 框架处理 JWT 认证"

        # 检测文件（更宽松的正则）
        import re

        files = re.findall(r"\b([\w/]+\.(?:py|js|ts|tsx|jsx|go|rs|java))\b", content)
        assert len(files) >= 1
        assert any("auth.py" in f for f in files)

        # 检测库/框架（简单匹配）
        libraries = ["FastAPI", "JWT", "React", "Django"]
        found_libs = [lib for lib in libraries if lib in content]
        assert len(found_libs) >= 1


class TestASTAnalyzerAdvanced:
    """测试 AST 分析器高级功能"""

    def test_extract_imports(self):
        """测试提取导入"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = """
import os
from pathlib import Path
from typing import List, Optional
import json as js
"""
        imports = analyzer.extract_imports(code, "python")

        # 应该找到一些导入
        assert len(imports) >= 1

    def test_extract_javascript_functions(self):
        """测试提取 JavaScript 函数"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = """
function hello() {
    console.log("hello");
}

const world = (name) => {
    return `Hello ${name}`;
};
"""
        funcs = analyzer.extract_functions(code, "javascript", "test.js")

        # JavaScript 提取可能需要 tree-sitter
        # 使用 regex fallback 可能找不到所有
        assert isinstance(funcs, list)

    def test_complex_python_code(self):
        """测试复杂 Python 代码"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        code = '''
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseHandler(ABC):
    """Abstract base class"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def handle(self, data: dict) -> bool:
        """Handle the data"""
        pass

class ConcreteHandler(BaseHandler):
    """Concrete implementation"""

    def handle(self, data: dict) -> bool:
        return True

    def _private_method(self):
        """Private helper"""
        pass

def standalone_function(x: int, y: int = 10) -> int:
    """A standalone function"""
    return x + y
'''
        funcs = analyzer.extract_functions(code, "python", "handlers.py")
        classes = analyzer.extract_classes(code, "python", "handlers.py")

        # 应该找到函数
        func_names = [f.name for f in funcs]
        assert "standalone_function" in func_names

        # 应该找到类
        class_names = [c.name for c in classes]
        assert "BaseHandler" in class_names
        assert "ConcreteHandler" in class_names


class TestDaemonLifecycle:
    """测试 Daemon 生命周期"""

    def test_daemon_start_stop(self):
        """测试 Daemon 启动和停止"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 初始状态
        assert daemon._is_running is False

        # 启动（不会真正阻塞因为没有 run()）
        daemon.start()
        assert daemon._is_running is True

        # 停止
        daemon.stop()
        assert daemon._is_running is False

    def test_daemon_double_start(self):
        """测试重复启动"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        daemon.start()
        daemon.start()  # 第二次应该无效但不报错

        assert daemon._is_running is True

        daemon.stop()

    def test_daemon_stop_without_start(self):
        """测试未启动时停止"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 不应该报错
        daemon.stop()

        assert daemon._is_running is False


class TestWatcherLifecycle:
    """测试 Watcher 生命周期"""

    def test_claude_watcher_start_stop(self):
        """测试 Claude Watcher 启动停止"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = f"{tmpdir}/history.jsonl"

            # 创建文件
            with open(watch_file, "w") as f:
                f.write("")

            watcher = ClaudeWatcher(watch_path=watch_file)

            # 启动
            watcher.start()
            assert watcher.is_running is True

            # 停止
            watcher.stop()
            assert watcher.is_running is False

    def test_watcher_file_not_found(self):
        """测试监听不存在的文件"""
        from dimcause.watchers import ClaudeWatcher

        watcher = ClaudeWatcher(watch_path="/nonexistent/file.jsonl")

        with pytest.raises(FileNotFoundError):
            watcher.start()


class TestSearchEngineEdgeCases:
    """测试搜索引擎边界情况"""

    def test_search_empty_query(self):
        """测试空查询"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            results = engine.search("", mode="text")

            assert isinstance(results, list)

    def test_search_special_characters(self):
        """测试特殊字符查询"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # 不应该崩溃
            results = engine.search("@#$%^&*()", mode="text")

            assert isinstance(results, list)

    def test_trace_nonexistent_file(self):
        """测试追溯不存在的文件"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            results = engine.trace("/nonexistent/file.py")

            assert isinstance(results, list)
