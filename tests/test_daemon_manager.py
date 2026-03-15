from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from dimcause.core.models import DimcauseConfig, RawData, SourceType
from dimcause.daemon.manager import DaemonManager
from dimcause.watchers.base import BaseWatcher


class MockWatcher(BaseWatcher):
    def __init__(self, name="mock"):
        super().__init__(watch_path="/tmp/mock", source=SourceType.MANUAL)
        self._name = name

    @property
    def name(self):
        return self._name

    def _parse_content(self, content):
        return None


def test_manager_initialization():
    config = DimcauseConfig()
    # Disable default watchers to test empty initialization
    config.watcher_claude.enabled = False

    manager = DaemonManager(config)
    assert manager._watchers == []
    assert manager._pipeline is not None


def test_register_watcher():
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    manager = DaemonManager(config)
    watcher = MockWatcher("test_watcher")

    manager.register_watcher(watcher)
    assert len(manager._watchers) == 1
    assert manager._watchers[0] == watcher


def test_register_duplicate_watcher():
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    manager = DaemonManager(config)
    watcher1 = MockWatcher("test_watcher")
    watcher2 = MockWatcher("test_watcher")  # Same name and path

    manager.register_watcher(watcher1)
    manager.register_watcher(watcher2)

    # Should ignore duplicate (based on name and path)
    assert len(manager._watchers) == 1


def test_pipeline_callback_invocation():
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    manager = DaemonManager(config)
    manager._pipeline = MagicMock()

    raw_data = RawData(
        id="test", source=SourceType.MANUAL, content="test", timestamp=datetime.now()
    )

    # Simulate callback
    manager._on_raw_data(raw_data)

    manager._pipeline.process.assert_called_once_with(raw_data)


def test_pipeline_error_handling():
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    manager = DaemonManager(config)
    manager._pipeline = MagicMock()
    manager._pipeline.process.side_effect = Exception("Pipeline failed")

    raw_data = RawData(
        id="test", source=SourceType.MANUAL, content="test", timestamp=datetime.now()
    )

    # Should not raise exception (it's caught and logged)
    try:
        manager._on_raw_data(raw_data)
    except Exception:
        pytest.fail("Manager raised exception on pipeline error")


def test_start_stop_empty():
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    manager = DaemonManager(config)
    manager.start()
    assert manager._is_running is True

    manager.stop()
    assert manager._is_running is False


@patch("dimcause.daemon.manager.ClaudeWatcher")
def test_init_watchers_from_config(MockClaude):
    config = DimcauseConfig()
    config.watcher_claude.enabled = True
    config.watcher_claude.path = "/tmp/claude"

    # Mock instance
    mock_instance = MockClaude.return_value
    mock_instance.name = "claude"
    mock_instance.watch_path = "/tmp/claude"

    manager = DaemonManager(config)

    # Verify ClaudeWatcher was initialized and registered
    MockClaude.assert_called_once()
    assert len(manager._watchers) == 1


@patch("dimcause.daemon.manager.ContinueWatcher")
def test_init_continue_watcher_from_config(MockContinue):
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    config.watcher_continue_dev = MagicMock(
        enabled=True,
        path="/tmp/continue",
        debounce_seconds=1.0,
    )

    mock_instance = MockContinue.return_value
    mock_instance.name = "continue_dev"
    mock_instance.watch_path = "/tmp/continue"

    manager = DaemonManager(config)

    MockContinue.assert_called_once()
    assert any(w.name == "continue_dev" for w in manager._watchers)


@patch("dimcause.daemon.manager.StateWatcher")
def test_init_state_watcher_from_config(MockStateWatcher):
    config = DimcauseConfig()
    config.watcher_claude.enabled = False
    config.watcher_state = MagicMock(
        enabled=True,
        path="/tmp/project",
        debounce_seconds=5.0,
    )

    mock_instance = MockStateWatcher.return_value
    mock_instance.name = "state"
    mock_instance.watch_path = "/tmp/project"

    manager = DaemonManager(config)

    MockStateWatcher.assert_called_once_with(
        project_path="/tmp/project",
        interval_seconds=5.0,
    )
    assert any(w.name == "state" for w in manager._watchers)
