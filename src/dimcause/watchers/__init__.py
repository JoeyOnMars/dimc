"""
Dimcause v5.1 Watchers

Layer 1: Ghost Mode - IDE 对话监听
"""

from .base import BaseWatcher
from .claude_watcher import ClaudeWatcher, create_claude_watcher
from .continue_watcher import ContinueWatcher, create_continue_watcher
from .cursor_watcher import CursorWatcher, create_cursor_watcher
from .detector import DetectedTool, build_enable_updates, detect_tools
from .state_watcher import StateWatcher, create_state_watcher
from .windsurf_watcher import WindsurfWatcher, create_windsurf_watcher

__all__ = [
    "BaseWatcher",
    "ClaudeWatcher",
    "ContinueWatcher",
    "CursorWatcher",
    "DetectedTool",
    "StateWatcher",
    "WindsurfWatcher",
    "build_enable_updates",
    "create_claude_watcher",
    "create_continue_watcher",
    "create_cursor_watcher",
    "detect_tools",
    "create_state_watcher",
    "create_windsurf_watcher",
]
