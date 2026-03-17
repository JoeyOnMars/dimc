"""
DIMCAUSE v0.1 Daemon 测试

测试后台服务和 Watchers
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def _isolated_daemon_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from dimcause.utils.config import reset_config

    root = tmp_path / "daemon-root"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".logger-config").write_text(
        json.dumps(
            {
                "data_dir": str(root / ".dimcause"),
                "watcher_claude": {
                    "enabled": False,
                    "path": str(root / ".claude" / "history.jsonl"),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DIMCAUSE_ROOT", str(root))
    reset_config()
    yield
    reset_config()


class TestDimcauseDaemon:
    """测试 MAL Daemon"""

    def test_daemon_creation(self):
        """测试 Daemon 创建"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon is not None
        assert daemon._is_running is False

    def test_daemon_status(self):
        """测试 Daemon 状态"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        assert "is_running" in status
        assert "watchers" in status
        assert "event_count" in status
        assert status["is_running"] is False
        assert status["event_count"] == 0

    def test_daemon_config(self):
        """测试 Daemon 配置"""
        from dimcause.core.models import DimcauseConfig, LLMConfig
        from dimcause.daemon import create_daemon

        config = DimcauseConfig(
            data_dir="/tmp/mal-test",
            llm_primary=LLMConfig(provider="ollama", model="test"),
            watcher_claude={"enabled": False, "path": "/tmp/mal-test/claude.jsonl"},
        )

        daemon = create_daemon(config=config)

        assert daemon.config.data_dir == "/tmp/mal-test"
        assert daemon.config.llm_primary.model == "test"

    def test_daemon_has_watchers(self):
        """测试 Daemon 有 Watchers"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        # 至少有 Claude Watcher（如果路径存在）
        assert isinstance(status["watchers"], list)


class TestClaudeWatcher:
    """测试 Claude Watcher"""

    def test_watcher_creation(self):
        """测试 Watcher 创建"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            assert watcher.name == "claude"
            assert watcher.is_running is False

    def test_watcher_callback(self):
        """测试 Watcher 回调注册"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback = Mock()
            watcher.on_new_data(callback)

            assert watcher._callbacks is not None


class TestCursorWatcher:
    """测试 Cursor Watcher"""

    def test_watcher_creation(self):
        """测试 Watcher 创建"""
        from dimcause.watchers import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            assert watcher.name == "cursor"
            assert watcher.is_running is False


class TestWindsurfWatcher:
    """测试 Windsurf Watcher"""

    def test_watcher_creation(self):
        """测试 Watcher 创建"""
        from dimcause.watchers import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            assert watcher.name == "windsurf"
            assert watcher.is_running is False


class TestBaseWatcher:
    """测试 BaseWatcher 基类"""

    def test_base_watcher_abstract(self):
        """测试 BaseWatcher 是抽象类"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.base import BaseWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建子类并实现所有抽象方法
            class TestWatcher(BaseWatcher):
                @property
                def name(self) -> str:
                    return "test"

                def _parse_content(self, content: str):
                    return None

            watcher = TestWatcher(
                watch_path=tmpdir, source=SourceType.CLAUDE_CODE, debounce_seconds=0.1
            )
            assert watcher.name == "test"
            assert watcher.is_running is False


class TestASTAnalyzer:
    """测试 AST 分析器"""

    def test_detect_language(self):
        """测试语言检测"""
        from dimcause.extractors.ast_analyzer import detect_language

        assert detect_language("test.py") == "python"
        assert detect_language("test.js") == "javascript"
        assert detect_language("test.ts") == "typescript"
        assert detect_language("test.unknown") == "unknown"

    def test_extract_functions_python(self):
        """测试提取 Python 函数"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        code = '''
def hello():
    """Hello function"""
    pass

def world(name: str) -> str:
    return f"Hello {name}"
'''
        funcs = analyzer.extract_functions(code, "python", "test.py")

        assert len(funcs) >= 2
        names = [f.name for f in funcs]
        assert "hello" in names
        assert "world" in names

    def test_extract_classes_python(self):
        """测试提取 Python 类"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        code = '''
class MyClass:
    """A test class"""

    def __init__(self):
        pass

    def method(self):
        pass
'''
        classes = analyzer.extract_classes(code, "python", "test.py")

        assert len(classes) >= 1
        assert classes[0].name == "MyClass"

    def test_supported_languages(self):
        """测试支持的语言"""
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        langs = analyzer.supported_languages()

        assert "python" in langs
        assert isinstance(langs, list)


class TestVectorStore:
    """测试向量存储"""

    def test_vector_store_creation(self):
        """测试 VectorStore 创建"""
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            # 即使 chromadb 不可用也不应该崩溃
            assert store is not None

    def test_vector_store_search_empty(self):
        """测试空搜索"""
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            results = store.search("test query", top_k=5)

            assert isinstance(results, list)


class TestGraphStore:
    """测试图谱存储"""

    def test_graph_store_creation(self):
        """测试 GraphStore 创建"""
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            assert store is not None

    def test_graph_store_add_event_relations(self):
        """测试添加事件关系"""
        from dimcause.core.models import Entity, Event, EventType
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            # 跳过如果 networkx 不可用
            if store._graph is None:
                pytest.skip("networkx not available")

            event = Event(
                id="evt_test",
                type=EventType.DISCUSSION,
                timestamp=datetime.now(),
                summary="测试事件",
                content="内容",
                entities=[
                    Entity(name="file.py", type="file"),
                    Entity(name="function", type="function"),
                ],
                related_files=["file.py", "other.py"],
            )

            store.add_event_relations(event)

            stats = store.stats()
            assert stats["nodes"] > 0


class TestSearchEngineAdvanced:
    """测试搜索引擎高级功能"""

    def test_trace_function(self):
        """测试函数追溯"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)

            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # trace 应该返回列表
            results = engine.trace("auth.py", function_name="login")

            assert isinstance(results, list)

    def test_search_modes(self):
        """测试不同搜索模式"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)

            # 保存测试数据
            event = Event(
                id="evt_mode_test",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="修改认证模块",
                content="更新了 JWT 验证逻辑",
            )
            md_store.save(event)

            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # 测试各种模式
            text_results = engine.search("认证", mode="text")
            semantic_results = engine.search("认证", mode="semantic")
            hybrid_results = engine.search("认证", mode="hybrid")

            assert isinstance(text_results, list)
            assert isinstance(semantic_results, list)
            assert isinstance(hybrid_results, list)


class TestCLIDaemon:
    """测试 CLI Daemon 命令"""

    def test_daemon_status_command(self):
        """测试 daemon status 命令"""
        from typer.testing import CliRunner

        from dimcause.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["daemon", "status"])

        assert result.exit_code == 0
        assert "Daemon" in result.stdout or "daemon" in result.stdout.lower()

    def test_daemon_help(self):
        """测试 daemon --help"""
        from typer.testing import CliRunner

        from dimcause.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["daemon", "--help"])

        assert result.exit_code == 0


class TestCLISearch:
    """测试 CLI Search 命令"""

    def test_search_help(self):
        """测试 search --help"""
        from typer.testing import CliRunner

        from dimcause.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0

    def test_search_command(self):
        """测试 search 命令"""
        from typer.testing import CliRunner

        from dimcause.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["search", "test query"])

        # 搜索应该执行（可能没有结果）
        assert result.exit_code == 0


class TestEventModel:
    """测试 Event 模型高级功能"""

    def test_event_with_code_entities(self):
        """测试带代码实体的 Event"""
        from dimcause.core.models import CodeEntity, CodeEntityType, Event, EventType

        event = Event(
            id="evt_code",
            type=EventType.CODE_CHANGE,
            timestamp=datetime.now(),
            summary="添加登录函数",
            content="实现了用户登录",
            code_entities=[
                CodeEntity(
                    name="login",
                    type=CodeEntityType.FUNCTION,
                    file="auth.py",
                    line_start=10,
                    line_end=25,
                    signature="def login(username: str, password: str) -> bool",
                )
            ],
        )

        md = event.to_markdown()

        assert "auth.py:login" in md
        assert "function" in md.lower()

    def test_event_with_entities(self):
        """测试带实体的 Event"""
        from dimcause.core.models import Entity, Event, EventType

        event = Event(
            id="evt_entities",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="选择 FastAPI 框架",
            content="决定使用 FastAPI",
            entities=[
                Entity(name="FastAPI", type="library", context="Web 框架"),
                Entity(name="main.py", type="file"),
            ],
        )

        md = event.to_markdown()

        assert "FastAPI" in md
        assert "library" in md.lower()
