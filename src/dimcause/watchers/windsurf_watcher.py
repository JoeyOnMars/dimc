"""
WindsurfWatcher - Windsurf IDE 对话监听

监听 Windsurf 的对话历史日志
"""

import json
import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from dimcause.core.models import RawData, SourceType
from dimcause.watchers.base import BaseWatcher


class WindsurfWatcher(BaseWatcher):
    """
    Windsurf IDE 对话监听器

    监听目录: ~/.windsurf/logs/ 或类似路径
    格式: JSON 日志文件
    """

    # 可能的日志路径
    POSSIBLE_PATHS = [
        "~/.windsurf/logs",
        "~/Library/Application Support/Windsurf/logs",
        "~/.config/Windsurf/logs",  # Linux
        "%APPDATA%/Windsurf/logs",  # Windows
        "~/.codeium/windsurf/logs",  # 可能的 Codeium 路径
    ]

    def __init__(self, watch_path: Optional[str] = None, debounce_seconds: float = 1.0):
        # 自动检测日志路径
        if not watch_path:
            watch_path = self._detect_log_path()

        super().__init__(
            watch_path=watch_path, source=SourceType.WINDSURF, debounce_seconds=debounce_seconds
        )

    @property
    def name(self) -> str:
        return "windsurf"

    def _detect_log_path(self) -> str:
        """自动检测 Windsurf 日志路径"""
        for path in self.POSSIBLE_PATHS:
            expanded = os.path.expanduser(os.path.expandvars(path))
            if os.path.exists(expanded):
                return expanded

        # 默认路径
        return os.path.expanduser("~/.windsurf/logs")

    def _should_process(self, file_path: str) -> bool:
        """判断是否应该处理该文件"""
        # 处理 JSON 和 JSONL 文件
        if not (file_path.endswith(".json") or file_path.endswith(".jsonl")):
            return False

        watch_dir = os.path.abspath(self.watch_path)
        file_dir = os.path.abspath(os.path.dirname(file_path))

        return file_dir.startswith(watch_dir)

    def _read_new_content(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Read error: {e}")
            return ""

    def _parse_content(self, content: str) -> Optional[RawData]:
        """
        解析 Windsurf 日志内容

        注意：实际格式需要根据 Windsurf 日志调整
        """
        if not content:
            return None

        messages = []
        files_mentioned = []

        # 尝试 JSONL 格式
        lines = content.strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    role = data.get("role", data.get("type", "unknown"))
                    text = data.get("content", data.get("message", data.get("text", "")))
                    if text:
                        messages.append(f"[{role}]: {text}")
                        files_mentioned.extend(self._extract_files(text))
            except json.JSONDecodeError:
                # 不是 JSON，作为普通文本
                messages.append(line)

        if not messages:
            return None

        return RawData(
            id=f"windsurf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            source=SourceType.WINDSURF,
            timestamp=datetime.now(),
            content="\n\n".join(messages),
            files_mentioned=list(set(files_mentioned)),
            metadata={
                "message_count": len(messages),
                "raw_lines": len(lines),
            },
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
def create_windsurf_watcher(path: Optional[str] = None, debounce: float = 1.0) -> WindsurfWatcher:
    """创建 Windsurf Watcher 实例"""
    return WindsurfWatcher(watch_path=path, debounce_seconds=debounce)
