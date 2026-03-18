"""
DIMCAUSE v0.1 Watcher 详细测试

测试 Watcher 的解析和处理逻辑
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest


class TestClaudeWatcherParsing:
    """测试 ClaudeWatcher 解析逻辑"""

    def test_parse_empty_content(self):
        """测试解析空内容"""
        from dimcause.watchers.claude_watcher import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            result = watcher._parse_content("")
            assert result is None

            result = watcher._parse_content("   ")
            assert result is None

    def test_parse_valid_jsonl(self):
        """测试解析有效 JSONL"""
        from dimcause.watchers.claude_watcher import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            content = json.dumps({"role": "user", "content": "Hello"}) + "\n"
            content += json.dumps({"role": "assistant", "content": "Hi there!"})

            result = watcher._parse_content(content)

            assert result is not None
            assert "Hello" in result.content
            assert "Hi there!" in result.content
            assert result.metadata["message_count"] == 2

    def test_parse_with_file_mentions(self):
        """测试解析包含文件路径的内容"""
        from dimcause.watchers.claude_watcher import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            content = json.dumps(
                {"role": "user", "content": "请修改 src/auth.py 和 tests/test_auth.py"}
            )

            result = watcher._parse_content(content)

            assert result is not None
            assert len(result.files_mentioned) >= 1

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        from dimcause.watchers.claude_watcher import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 无效 JSON 应该被当作纯文本处理
            content = "This is not JSON\nNeither is this"

            result = watcher._parse_content(content)

            assert result is not None
            assert "This is not JSON" in result.content

    def test_extract_files(self):
        """测试文件提取"""
        from dimcause.watchers.claude_watcher import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            text = "修改了 main.py, config.json 和 styles.css 文件"
            files = watcher._extract_files(text)

            assert len(files) >= 2

    def test_create_claude_watcher_factory(self):
        """测试工厂函数"""
        from dimcause.watchers.claude_watcher import create_claude_watcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = create_claude_watcher(path=str(watch_file), debounce=0.5)

            assert watcher.name == "claude"
            assert watcher.debounce_seconds == 0.5


class TestCursorWatcherParsing:
    """测试 CursorWatcher 解析逻辑"""

    def test_cursor_watcher_name(self):
        """测试 Cursor Watcher 名称"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            assert watcher.name == "cursor"

    def test_cursor_watcher_source(self):
        """测试 Cursor Watcher 来源"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            assert watcher.source == SourceType.CURSOR


class TestWindsurfWatcherParsing:
    """测试 WindsurfWatcher 解析逻辑"""

    def test_windsurf_watcher_name(self):
        """测试 Windsurf Watcher 名称"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            assert watcher.name == "windsurf"

    def test_windsurf_watcher_source(self):
        """测试 Windsurf Watcher 来源"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            assert watcher.source == SourceType.WINDSURF


class TestBaseWatcherBehavior:
    """测试 BaseWatcher 行为"""

    def test_double_stop(self):
        """测试重复停止"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 启动再停止
            watcher.start()
            watcher.stop()

            # 再次停止不应该报错
            watcher.stop()

            assert watcher.is_running is False

    def test_callback_registration(self):
        """测试回调注册"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback1 = Mock()
            callback2 = Mock()

            watcher.on_new_data(callback1)
            watcher.on_new_data(callback2)

            assert len(watcher._callbacks) == 2

    def test_file_position_tracking(self):
        """测试文件位置跟踪"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.write_text('{"role": "user", "content": "initial"}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))
            watcher.start()

            # 应该从文件末尾开始
            assert watcher._last_position > 0

            watcher.stop()


class TestWatcherIntegration:
    """测试 Watcher 集成"""

    def test_watcher_module_exports(self):
        """测试模块导出"""
        from dimcause.watchers import BaseWatcher, ClaudeWatcher, CursorWatcher, WindsurfWatcher

        assert ClaudeWatcher is not None
        assert CursorWatcher is not None
        assert WindsurfWatcher is not None
        assert BaseWatcher is not None

    def test_all_watchers_have_name(self):
        """测试所有 Watcher 都有名称"""
        from dimcause.watchers import ClaudeWatcher, CursorWatcher, WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "history.jsonl"
            watch_file.touch()

            watchers = [
                ClaudeWatcher(watch_path=str(watch_file)),
                CursorWatcher(watch_path=tmpdir),
                WindsurfWatcher(watch_path=tmpdir),
            ]

            for watcher in watchers:
                assert isinstance(watcher.name, str)
                assert len(watcher.name) > 0


class TestStorageEdgeCases:
    """测试存储边界情况"""

    def test_markdown_store_missing_dir(self):
        """测试 MarkdownStore 自动创建目录"""
        from dimcause.core.models import Event, EventType
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            # 使用不存在的子目录
            store = MarkdownStore(base_dir=f"{tmpdir}/nested/deep/events")

            event = Event(
                id="evt_test",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="测试",
                content="内容",
            )

            path = store.save(event)

            assert Path(path).exists()

    def test_graph_store_find_related_empty(self):
        """测试 GraphStore 空图查询"""
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            # 查询不存在的实体
            results = store.find_related("nonexistent")

            assert isinstance(results, list)
            assert len(results) == 0

    def test_vector_store_delete(self):
        """测试 VectorStore 删除"""
        from dimcause.storage.vector_store import VectorStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            # 删除操作不应该报错
            result = store.delete("nonexistent_id")

            # 结果应该是 bool 类型
            assert isinstance(result, bool)


class TestSearchEngineIntegration:
    """测试搜索引擎集成"""

    def test_search_basic(self):
        """测试基础搜索"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            md_store = MarkdownStore(base_dir=tmpdir)

            # 保存事件
            event = Event(
                id="evt_date_test",
                type=EventType.CODE_CHANGE,
                timestamp=datetime.now(),
                summary="日期测试",
                content="测试日期范围搜索",
            )
            md_store.save(event)

            engine = SearchEngine(markdown_store=md_store, vector_store=None)

            # 基础搜索
            results = engine.search("日期测试", mode="text")

            assert isinstance(results, list)


class TestConfigIntegration:
    """测试配置集成"""

    def test_dimcause_config_defaults(self):
        """测试 DimcauseConfig 默认值"""
        from dimcause.core.models import DimcauseConfig

        config = DimcauseConfig()

        assert config.data_dir is not None
        assert config.llm_primary is not None

    def test_watcher_config_with_path(self):
        """测试 WatcherConfig 需要 path"""
        from dimcause.core.models import WatcherConfig

        config = WatcherConfig(path="/tmp/test")

        assert config.enabled is True
        assert config.debounce_seconds > 0

    def test_llm_config(self):
        """测试 LLM 配置"""
        from dimcause.core.models import LLMConfig

        config = LLMConfig()

        assert config.provider is not None
        assert config.model is not None
