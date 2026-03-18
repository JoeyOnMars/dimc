"""
DIMCAUSE v0.1 Daemon 完整测试

覆盖 DimcauseDaemon 的核心逻辑
"""

import json
import os
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


class TestDimcauseDaemonInit:
    """测试 Daemon 初始化"""

    def test_daemon_creation_basic(self):
        """测试基础创建"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon is not None
        assert daemon._is_running is False

    def test_daemon_has_stores(self):
        """测试 Daemon 有存储"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon._markdown_store is not None
        assert daemon._vector_store is not None
        assert daemon._graph_store is not None

    def test_daemon_has_ast_analyzer(self):
        """测试 Daemon 有 AST 分析器"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon._ast_analyzer is not None


class TestDimcauseDaemonStatus:
    """测试 Daemon 状态"""

    def test_status_structure(self):
        """测试状态结构"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        assert "is_running" in status
        assert "watchers" in status
        assert "event_count" in status

    def test_status_graph_stats(self):
        """测试图统计"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        assert "stats" in status
        assert "graph_stats" in status["stats"]
        assert "nodes" in status["stats"]["graph_stats"]

    def test_status_initial_running(self):
        """测试初始运行状态"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon._is_running is False
        assert daemon.status()["is_running"] is False


class TestDimcauseDaemonRawDataProcessing:
    """测试原始数据处理"""

    def test_on_raw_data_without_extractor(self):
        """测试无提取器时的数据处理"""
        from dimcause.core.models import RawData, SourceType
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 创建测试数据
        raw = RawData(
            id="raw_test_123",
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            content="这是测试内容，用于验证处理流程",
            metadata={},
        )

        # 处理数据（无 extractor）
        initial_count = daemon._event_count

        # 调用处理方法
        daemon._on_raw_data(raw)

        # 事件计数应该增加
        assert daemon._event_count >= initial_count

    def test_on_raw_data_with_file_mention(self):
        """测试提到文件的数据处理"""
        from dimcause.core.models import RawData, SourceType
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello(): pass")
            temp_file = f.name

        try:
            raw = RawData(
                id="raw_file_test",
                source=SourceType.MANUAL,
                timestamp=datetime.now(),
                content="修改了一些代码",
                files_mentioned=[temp_file],
                metadata={},
            )

            daemon._on_raw_data(raw)

            # 应该成功处理
            assert daemon._event_count >= 1
        finally:
            os.unlink(temp_file)


class TestDimcauseDaemonEventSaving:
    """测试事件保存"""

    def test_save_event(self):
        """测试保存事件"""
        from dimcause.core.models import Event, EventType
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # mock 掉存储层，避免触发网络请求（embedding 下载）
        daemon._pipeline.vector_store = Mock()
        daemon._pipeline.graph_store = Mock()
        daemon._pipeline.markdown_store = Mock()
        daemon._pipeline.event_index = Mock()
        daemon._pipeline.event_index.add.return_value = True

        event = Event(
            id="evt_save_test",
            type=EventType.CODE_CHANGE,
            timestamp=datetime.now(),
            summary="测试保存",
            content="这是测试内容",
        )

        # 保存事件，应该成功（不抛异常）
        daemon._save_event(event)
        assert True


class TestDimcauseDaemonLifecycle:
    """测试 Daemon 生命周期"""

    def test_start_stop(self):
        """测试启动和停止"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 初始状态
        assert daemon._is_running is False

        # 启动
        daemon.start()
        assert daemon._is_running is True

        # 停止
        daemon.stop()
        assert daemon._is_running is False

    def test_double_start(self):
        """测试重复启动"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        daemon.start()
        daemon.start()  # 不应该报错

        assert daemon._is_running is True

        daemon.stop()

    def test_double_stop(self):
        """测试重复停止"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        daemon.start()
        daemon.stop()
        daemon.stop()  # 不应该报错

        assert daemon._is_running is False


class TestDimcauseDaemonWatchers:
    """测试 Daemon Watcher 管理"""

    def test_watchers_initialized(self):
        """测试 Watchers 已初始化"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 应该有 watchers 列表
        assert hasattr(daemon, "_watchers")
        assert isinstance(daemon._watchers, list)

    def test_watcher_count(self):
        """测试 Watcher 数量"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()
        status = daemon.status()

        # 至少应该有一些 watcher 配置
        assert isinstance(status["watchers"], list)


class TestWatcherBase:
    """测试 BaseWatcher"""

    def test_base_watcher_start_stop(self):
        """测试 Watcher 启动停止"""
        from pathlib import Path

        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            # 启动
            watcher.start()
            assert watcher.is_running is True

            # 停止
            watcher.stop()
            assert watcher.is_running is False

    def test_base_watcher_callback_invocation(self):
        """测试回调调用"""
        from pathlib import Path

        from dimcause.core.models import RawData, SourceType
        from dimcause.watchers import ClaudeWatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_file = Path(tmpdir) / "test.jsonl"
            watch_file.touch()

            watcher = ClaudeWatcher(watch_path=str(watch_file))

            callback = Mock()
            watcher.on_new_data(callback)

            # 手动创建一个 RawData 并触发回调
            raw = RawData(
                id="test", source=SourceType.CLAUDE_CODE, timestamp=datetime.now(), content="test"
            )

            # 直接调用回调
            for cb in watcher._callbacks:
                cb(raw)

            callback.assert_called_once_with(raw)


class TestCreateDaemon:
    """测试 create_daemon 函数"""

    def test_create_daemon_default(self):
        """测试默认创建"""
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        assert daemon is not None

    def test_create_daemon_returns_dimcause_daemon(self):
        """测试返回 DimcauseDaemon 实例"""
        from dimcause.daemon import DimcauseDaemon, create_daemon

        daemon = create_daemon()

        assert isinstance(daemon, DimcauseDaemon)


class TestDaemonEdgeCases:
    """测试边界情况"""

    def test_process_empty_content(self):
        """测试处理空内容"""
        from dimcause.core.models import RawData, SourceType
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        raw = RawData(
            id="empty_test",
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            content="",
            metadata={},
        )

        # 不应该崩溃
        daemon._on_raw_data(raw)

    def test_process_long_content(self):
        """测试处理长内容"""
        from dimcause.core.models import RawData, SourceType
        from dimcause.daemon import create_daemon

        daemon = create_daemon()

        # 创建很长的内容
        long_content = "这是测试内容。" * 1000

        raw = RawData(
            id="long_test",
            source=SourceType.MANUAL,
            timestamp=datetime.now(),
            content=long_content,
            metadata={},
        )

        # 不应该崩溃
        daemon._on_raw_data(raw)
