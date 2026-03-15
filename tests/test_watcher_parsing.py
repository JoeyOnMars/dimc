"""
DIMCAUSE v0.1 Cursor/Windsurf Watcher 详细测试

测试 Cursor 和 Windsurf Watcher 的解析逻辑
"""

import json
import tempfile
from pathlib import Path


class TestCursorWatcherParsing:
    """测试 CursorWatcher 解析逻辑"""

    def test_parse_empty_content(self):
        """测试解析空内容"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            result = watcher._parse_content("")
            assert result is None

    def test_parse_valid_json(self):
        """测试解析有效 JSON"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps(
                {
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ]
                }
            )

            result = watcher._parse_content(content)

            assert result is not None
            assert "Hello" in result.content
            assert "Hi there!" in result.content

    def test_parse_messages_list(self):
        """测试解析消息列表"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps(
                [
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "Second message"},
                ]
            )

            result = watcher._parse_content(content)

            assert result is not None
            assert result.metadata["message_count"] == 2

    def test_parse_single_message(self):
        """测试解析单条消息"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps({"content": "Single message content"})

            result = watcher._parse_content(content)

            assert result is not None

    def test_parse_with_file_mentions(self):
        """测试解析包含文件路径"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps(
                {"messages": [{"role": "user", "content": "修改 src/main.py 和 config.json"}]}
            )

            result = watcher._parse_content(content)

            assert result is not None
            assert len(result.files_mentioned) >= 1

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = "This is plain text, not JSON"

            result = watcher._parse_content(content)

            assert result is not None
            assert "plain text" in result.content
            assert result.metadata.get("format") == "plain_text"

    def test_should_process_json_only(self):
        """测试只处理 JSON 文件"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            assert watcher._should_process(f"{tmpdir}/test.json") is True
            assert watcher._should_process(f"{tmpdir}/test.txt") is False
            assert watcher._should_process(f"{tmpdir}/test.py") is False

    def test_detect_log_path_fallback(self):
        """测试日志路径检测回退"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        # 不传入路径，使用默认检测
        watcher = CursorWatcher(watch_path=None)

        # 应该有路径
        assert watcher.watch_path is not None

    def test_read_new_content(self):
        """测试读取新内容"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            # 创建测试文件
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"test": "content"}')

            content = watcher._read_new_content(str(test_file))

            assert content == '{"test": "content"}'

    def test_read_new_content_error(self):
        """测试读取不存在的文件"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = watcher._read_new_content("/nonexistent/file.json")

            assert content == ""

    def test_extract_files(self):
        """测试文件提取"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            text = "修改了 main.py, config.json 和 styles.css 文件"
            files = watcher._extract_files(text)

            assert len(files) >= 2

    def test_create_cursor_watcher_factory(self):
        """测试工厂函数"""
        from dimcause.watchers.cursor_watcher import create_cursor_watcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = create_cursor_watcher(path=tmpdir, debounce=0.5)

            assert watcher.name == "cursor"
            assert watcher.debounce_seconds == 0.5


class TestWindsurfWatcherParsing:
    """测试 WindsurfWatcher 解析逻辑"""

    def test_parse_empty_content(self):
        """测试解析空内容"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            result = watcher._parse_content("")
            assert result is None

    def test_parse_valid_jsonl(self):
        """测试解析有效 JSONL"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            # Windsurf 使用 JSONL 格式，每行一个 JSON
            content = json.dumps({"role": "user", "content": "Hello Windsurf"}) + "\n"
            content += json.dumps({"role": "assistant", "content": "Hi!"})

            result = watcher._parse_content(content)

            assert result is not None
            assert "Hello Windsurf" in result.content

    def test_parse_messages_jsonl(self):
        """测试解析 JSONL 消息"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            # JSONL 格式
            content = json.dumps({"role": "user", "text": "First message"}) + "\n"
            content += json.dumps({"role": "assistant", "text": "Second message"})

            result = watcher._parse_content(content)

            assert result is not None

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            content = "Plain text content for Windsurf"

            result = watcher._parse_content(content)

            assert result is not None

    def test_should_process_json_only(self):
        """测试只处理 JSON 文件"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            assert watcher._should_process(f"{tmpdir}/test.json") is True
            assert watcher._should_process(f"{tmpdir}/test.txt") is False

    def test_detect_log_path_fallback(self):
        """测试日志路径检测回退"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        watcher = WindsurfWatcher(watch_path=None)

        assert watcher.watch_path is not None

    def test_read_new_content(self):
        """测试读取新内容"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"windsurf": "content"}')

            content = watcher._read_new_content(str(test_file))

            assert "windsurf" in content

    def test_extract_files(self):
        """测试文件提取"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            text = "编辑 app.ts 和 package.json"
            files = watcher._extract_files(text)

            assert len(files) >= 1

    def test_create_windsurf_watcher_factory(self):
        """测试工厂函数"""
        from dimcause.watchers.windsurf_watcher import create_windsurf_watcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = create_windsurf_watcher(path=tmpdir, debounce=0.5)

            assert watcher.name == "windsurf"


class TestWatcherAutoDetection:
    """测试 Watcher 自动检测"""

    def test_cursor_watcher_possible_paths(self):
        """测试 Cursor 可能的路径"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        assert len(CursorWatcher.POSSIBLE_PATHS) >= 3

    def test_windsurf_watcher_possible_paths(self):
        """测试 Windsurf 可能的路径"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        assert len(WindsurfWatcher.POSSIBLE_PATHS) >= 3


class TestWatcherMessageExtraction:
    """测试消息提取边界情况"""

    def test_cursor_empty_messages(self):
        """测试 Cursor 空消息列表"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps({"messages": []})
            result = watcher._parse_content(content)

            assert result is None

    def test_cursor_message_without_content(self):
        """测试 Cursor 消息没有 content 字段"""
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps(
                {"messages": [{"role": "user", "text": "Using text instead of content"}]}
            )

            result = watcher._parse_content(content)

            assert result is not None
            assert "text instead" in result.content

    def test_windsurf_text_fallback(self):
        """测试 Windsurf text 字段回退"""
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            # JSONL 格式，使用 text 字段
            content = json.dumps({"role": "assistant", "text": "Response text"})

            result = watcher._parse_content(content)

            assert result is not None
            assert "Response text" in result.content


class TestWatcherSourceTypes:
    """测试 Watcher 来源类型"""

    def test_cursor_source_type(self):
        """测试 Cursor 来源类型"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            assert watcher.source == SourceType.CURSOR

    def test_windsurf_source_type(self):
        """测试 Windsurf 来源类型"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.windsurf_watcher import WindsurfWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = WindsurfWatcher(watch_path=tmpdir)

            assert watcher.source == SourceType.WINDSURF

    def test_raw_data_has_correct_source(self):
        """测试 RawData 有正确的来源"""
        from dimcause.core.models import SourceType
        from dimcause.watchers.cursor_watcher import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            content = json.dumps({"messages": [{"role": "user", "content": "test"}]})

            result = watcher._parse_content(content)

            assert result is not None
            assert result.source == SourceType.CURSOR
