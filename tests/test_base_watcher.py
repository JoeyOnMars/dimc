"""
DIMCAUSE v0.1 BaseWatcher 深度测试

覆盖 BaseWatcher 事件处理和文件监听
"""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

# 沙箱隔离：当 CI 环境中 DIMCAUSE_SKIP_WATCHER=1 时跳过 watchdog 物理 Observer 测试
_SKIP_WATCHER = os.environ.get("DIMCAUSE_SKIP_WATCHER", "") == "1"
_SKIP_REASON = "跳过 watchdog 物理 Observer 测试（设置 DIMCAUSE_SKIP_WATCHER=1）"


class TestDebounceHandler:
    """测试防抖处理器"""

    def test_debounce_handler_creation(self):
        """测试防抖处理器创建"""
        from dimcause.watchers.base import DebounceHandler

        callback = Mock()
        handler = DebounceHandler(callback=callback, debounce_seconds=1.0)

        assert handler.callback == callback
        assert handler.debounce_seconds == 1.0

    def test_debounce_handler_ignores_directory(self):
        """测试忽略目录事件"""
        from dimcause.watchers.base import DebounceHandler

        callback = Mock()
        handler = DebounceHandler(callback=callback, debounce_seconds=0.1)

        event = MagicMock()
        event.is_directory = True

        handler.on_modified(event)

        callback.assert_not_called()

    def test_debounce_handler_calls_callback(self):
        """测试防抖处理器调用回调"""
        from dimcause.watchers.base import DebounceHandler

        callback = Mock()
        handler = DebounceHandler(callback=callback, debounce_seconds=0.01)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/test/file.txt"

        handler.on_modified(event)

        # 等待线程执行
        time.sleep(0.1)

        callback.assert_called_once_with("/test/file.txt")


class TestBaseWatcherFileChange:
    """测试 BaseWatcher 文件变化处理"""

    def test_on_file_change_with_callback(self):
        """测试文件变化触发回调"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.write_text('{"role": "user", "content": "Hello"}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback = Mock()
            watcher.on_new_data(callback)

            # 模拟文件变化
            watcher._last_position = 0
            watcher._on_file_change(str(watch_file))

            # 回调应该被调用
            assert callback.called

    def test_on_file_change_skip_non_target(self):
        """测试跳过非目标文件"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "target.jsonl"
            other_file = Path(tmpdir) / "other.jsonl"
            watch_file.touch()
            other_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback = Mock()
            watcher.on_new_data(callback)

            # 触发非目标文件
            watcher._on_file_change(str(other_file))

            # 回调不应被调用
            callback.assert_not_called()

    def test_on_file_change_empty_content(self):
        """测试空内容不触发回调"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback = Mock()
            watcher.on_new_data(callback)

            watcher._on_file_change(str(watch_file))

            # 空内容不触发
            callback.assert_not_called()


class TestBaseWatcherReadContent:
    """测试读取内容"""

    def test_read_new_content(self):
        """测试读取新内容"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.write_text('{"line": 1}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))
            watcher._last_position = 0

            content = watcher._read_new_content(str(watch_file))

            assert '{"line": 1}' in content

    @pytest.mark.skipif(_SKIP_WATCHER, reason=_SKIP_REASON)
    def test_read_new_content_incremental(self):
        """测试增量读取"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.write_text('{"line": 1}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))
            watcher.start()

            # 添加新内容
            with open(watch_file, "a") as f:
                f.write('{"line": 2}\n')

            content = watcher._read_new_content(str(watch_file))

            assert '{"line": 2}' in content
            assert '{"line": 1}' not in content

            watcher.stop()

    def test_read_new_content_error(self):
        """测试读取错误处理"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 尝试读取不存在的文件
            content = watcher._read_new_content("/nonexistent/file.jsonl")

            assert content == ""


class TestBaseWatcherShouldProcess:
    """测试应该处理判断"""

    def test_should_process_target_file(self):
        """测试处理目标文件"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            result = watcher._should_process(str(watch_file))

            assert result is True

    def test_should_process_other_file(self):
        """测试不处理其他文件"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "target.jsonl"
            other_file = Path(tmpdir) / "other.jsonl"
            watch_file.touch()
            other_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            result = watcher._should_process(str(other_file))

            assert result is False


class TestBaseWatcherStart:
    """测试启动逻辑"""

    def test_start_file_not_found(self):
        """测试启动时文件不存在"""
        from dimcause.watchers import ClaudeWatcher

        watcher = ClaudeWatcher(watch_path="/nonexistent/path/file.jsonl")

        with pytest.raises(FileNotFoundError):
            watcher.start()

    @pytest.mark.skipif(_SKIP_WATCHER, reason=_SKIP_REASON)
    def test_start_creates_observer(self):
        """测试启动创建观察者"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            watcher.start()

            assert watcher._observer is not None
            assert watcher._is_running is True

            watcher.stop()

    @pytest.mark.skipif(_SKIP_WATCHER, reason=_SKIP_REASON)
    def test_start_directory(self):
        """测试监听目录"""
        from dimcause.watchers import CursorWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = CursorWatcher(watch_path=tmpdir)

            watcher.start()

            assert watcher._is_running is True

            watcher.stop()


class TestBaseWatcherStop:
    """测试停止逻辑"""

    @pytest.mark.skipif(_SKIP_WATCHER, reason=_SKIP_REASON)
    def test_stop_clears_observer(self):
        """测试停止清除观察者"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            watcher.start()
            watcher.stop()

            assert watcher._observer is None
            assert watcher._is_running is False

    def test_stop_without_start(self):
        """测试未启动时停止"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 不应该报错
            watcher.stop()

            assert watcher._is_running is False


class TestBaseWatcherCallbackError:
    """测试回调错误处理"""

    def test_callback_error_doesnt_crash(self):
        """测试回调错误不崩溃"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.write_text('{"role": "user", "content": "Hello"}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 添加会抛错的回调
            def bad_callback(raw):
                raise Exception("Callback error!")

            watcher.on_new_data(bad_callback)

            # 不应该崩溃
            watcher._last_position = 0
            watcher._on_file_change(str(watch_file))

            # Watcher 应该仍然正常
            assert True

    def test_multiple_callbacks_one_fails(self):
        """测试多回调其中一个失败"""
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.write_text('{"role": "user", "content": "Hello"}\n')

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            results = []

            def good_callback(raw):
                results.append("good")

            def bad_callback(raw):
                raise Exception("Bad!")

            watcher.on_new_data(good_callback)
            watcher.on_new_data(bad_callback)
            watcher.on_new_data(good_callback)

            watcher._last_position = 0
            watcher._on_file_change(str(watch_file))

            # 两个好的回调都应该执行（一个在错误前，一个可能在错误后）
            assert "good" in results
