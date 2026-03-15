"""
ClaudeWatcher - Claude Code 对话监听

监听 Claude Code 的对话历史日志
"""

import json
from datetime import datetime
from typing import Optional
from uuid import uuid4

from dimcause.core.models import RawData, SourceType
from dimcause.watchers.base import BaseWatcher


class ClaudeWatcher(BaseWatcher):
    """
    Claude Code 对话监听器

    监听文件: ~/.claude/history.jsonl
    格式: JSONL (每行一个 JSON 对象)
    """

    DEFAULT_PATH = "~/.claude/history.jsonl"

    def __init__(self, watch_path: Optional[str] = None, debounce_seconds: float = 1.0):
        super().__init__(
            watch_path=watch_path or self.DEFAULT_PATH,
            source=SourceType.CLAUDE_CODE,
            debounce_seconds=debounce_seconds,
        )

    @property
    def name(self) -> str:
        return "claude"

    def _parse_content(self, content: str) -> Optional[RawData]:
        """
        解析 Claude Code 日志内容

        格式假设（需要根据实际格式调整）:
        {"role": "user", "content": "...", "timestamp": "..."}
        {"role": "assistant", "content": "...", "timestamp": "..."}
        """
        if not content:
            return None

        # 尝试解析 JSONL
        lines = content.strip().split("\n")
        messages = []
        files_mentioned = []

        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                messages.append(data)

                # 提取提到的文件
                msg_content = data.get("content", "")
                files_mentioned.extend(self._extract_files(msg_content))

            except json.JSONDecodeError:
                # 不是 JSON，可能是纯文本
                messages.append({"content": line})

        if not messages:
            return None

        # 合并所有消息内容
        full_content = "\n\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in messages
        )

        return RawData(
            id=f"claude_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            source=SourceType.CLAUDE_CODE,
            timestamp=datetime.now(),
            content=full_content,
            files_mentioned=list(set(files_mentioned)),
            metadata={
                "message_count": len(messages),
                "raw_lines": len(lines),
            },
        )

    def _extract_files(self, text: str) -> list[str]:
        """
        从文本中提取文件路径

        简单实现：识别常见文件扩展名
        """
        import re

        # 匹配常见文件扩展名
        pattern = (
            r"[\w./\\-]+\.(py|js|ts|jsx|tsx|md|json|yaml|yml|toml|html|css|go|rs|java|cpp|c|h)"
        )
        matches = re.findall(pattern, text, re.IGNORECASE)

        # 重新构造完整匹配
        files = []
        for ext in matches:
            full_pattern = rf"[\w./\\-]+\.{ext}"
            full_matches = re.findall(full_pattern, text, re.IGNORECASE)
            files.extend(full_matches)

        return files


# 便捷函数
def create_claude_watcher(path: Optional[str] = None, debounce: float = 1.0) -> ClaudeWatcher:
    """创建 Claude Watcher 实例"""
    return ClaudeWatcher(watch_path=path, debounce_seconds=debounce)
