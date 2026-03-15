"""
CursorWatcher - Cursor IDE 对话监听

监听 Cursor 的对话历史日志
"""

import json
import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from dimcause.core.models import RawData, SourceType
from dimcause.watchers.base import BaseWatcher


class CursorWatcher(BaseWatcher):
    """
    Cursor IDE 对话监听器

    监听目录: ~/.cursor/logs/ 或 ~/Library/Application Support/Cursor/logs/
    格式: JSON 日志文件
    """

    # 可能的日志路径
    POSSIBLE_PATHS = [
        "~/.cursor/logs",
        "~/Library/Application Support/Cursor/logs",
        "~/.config/Cursor/logs",  # Linux
        "%APPDATA%/Cursor/logs",  # Windows
    ]

    def __init__(self, watch_path: Optional[str] = None, debounce_seconds: float = 1.0):
        # 自动检测日志路径
        if not watch_path:
            watch_path = self._detect_log_path()

        super().__init__(
            watch_path=watch_path, source=SourceType.CURSOR, debounce_seconds=debounce_seconds
        )

        self._processed_files: set = set()

    @property
    def name(self) -> str:
        return "cursor"

    def _detect_log_path(self) -> str:
        """自动检测 Cursor 日志路径"""
        for path in self.POSSIBLE_PATHS:
            expanded = os.path.expanduser(os.path.expandvars(path))
            if os.path.exists(expanded):
                return expanded

        # 默认路径
        return os.path.expanduser("~/.cursor/logs")

    def _should_process(self, file_path: str) -> bool:
        """判断是否应该处理该文件"""
        # 处理目录下的所有 JSON 文件
        if not file_path.endswith(".json"):
            return False

        # 检查是否在监听目录下
        watch_dir = os.path.abspath(self.watch_path)
        file_dir = os.path.abspath(os.path.dirname(file_path))

        return file_dir.startswith(watch_dir)

    def _read_new_content(self, file_path: str) -> str:
        """读取文件内容"""
        # Cursor 可能使用增量日志，需要读取整个文件
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Read error: {e}")
            return ""

    def _parse_content(self, content: str) -> Optional[RawData]:
        """
        解析 Cursor 日志内容

        注意：实际格式需要根据 Cursor 日志调整
        """
        if not content:
            return None

        try:
            # 尝试解析 JSON
            data = json.loads(content)

            # 提取对话内容
            messages = []
            files_mentioned = []

            # Cursor 格式可能是这样（需要根据实际调整）
            if isinstance(data, dict):
                if "messages" in data:
                    messages = data["messages"]
                elif "content" in data:
                    messages = [data]
            elif isinstance(data, list):
                messages = data

            # 合并消息
            full_content = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    text = msg.get("content", msg.get("text", ""))
                    full_content.append(f"[{role}]: {text}")

                    # 提取提到的文件
                    if text:
                        files_mentioned.extend(self._extract_files(text))

            if not full_content:
                return None

            return RawData(
                id=f"cursor_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
                source=SourceType.CURSOR,
                timestamp=datetime.now(),
                content="\n\n".join(full_content),
                files_mentioned=list(set(files_mentioned)),
                metadata={
                    "message_count": len(messages),
                },
            )

        except json.JSONDecodeError:
            # 如果不是 JSON，尝试作为纯文本处理
            return RawData(
                id=f"cursor_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
                source=SourceType.CURSOR,
                timestamp=datetime.now(),
                content=content,
                metadata={"format": "plain_text"},
            )

    def _extract_files(self, text: str) -> List[str]:
        """从文本中提取文件路径"""
        import re

        pattern = r"[\w./\\-]+\.(py|js|ts|jsx|tsx|md|json|yaml|yml|html|css|go|rs)"
        files = []
        for ext in re.findall(pattern, text, re.IGNORECASE):
            full_pattern = rf"[\w./\\-]+\.{ext}"
            files.extend(re.findall(full_pattern, text, re.IGNORECASE))
        return files


# 便捷函数
def create_cursor_watcher(path: Optional[str] = None, debounce: float = 1.0) -> CursorWatcher:
    """创建 Cursor Watcher 实例"""
    return CursorWatcher(watch_path=path, debounce_seconds=debounce)
