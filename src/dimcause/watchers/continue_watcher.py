"""Continue.dev conversation watcher."""

import json
import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from dimcause.core.models import RawData, SourceType
from dimcause.watchers.base import BaseWatcher


class ContinueWatcher(BaseWatcher):
    """Watch Continue.dev session exports."""

    POSSIBLE_PATHS = [
        "~/.continue/sessions",
        "%USERPROFILE%/.continue/sessions",
    ]

    def __init__(self, watch_path: Optional[str] = None, debounce_seconds: float = 1.0):
        if not watch_path:
            watch_path = self._detect_log_path()

        super().__init__(
            watch_path=watch_path,
            source=SourceType.CONTINUE_DEV,
            debounce_seconds=debounce_seconds,
        )

    @property
    def name(self) -> str:
        return "continue_dev"

    def _detect_log_path(self) -> str:
        for path in self.POSSIBLE_PATHS:
            expanded = os.path.expanduser(os.path.expandvars(path))
            if os.path.exists(expanded):
                return expanded
        return os.path.expanduser("~/.continue/sessions")

    def _should_process(self, file_path: str) -> bool:
        if not (file_path.endswith(".json") or file_path.endswith(".jsonl")):
            return False

        watch_dir = os.path.abspath(self.watch_path)
        file_dir = os.path.abspath(os.path.dirname(file_path))
        return file_dir.startswith(watch_dir)

    def _read_new_content(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _parse_content(self, content: str) -> Optional[RawData]:
        if not content:
            return None

        messages = self._extract_messages(content)
        if not messages:
            return None

        files_mentioned: List[str] = []
        formatted_messages: List[str] = []
        for message in messages:
            role = message.get("role", message.get("type", "unknown"))
            text = message.get("content", message.get("text", message.get("message", "")))
            if not text:
                continue
            formatted_messages.append(f"[{role}]: {text}")
            files_mentioned.extend(self._extract_files(text))

        if not formatted_messages:
            return None

        return RawData(
            id=f"continue_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            source=SourceType.CONTINUE_DEV,
            timestamp=datetime.now(),
            content="\n\n".join(formatted_messages),
            files_mentioned=sorted(set(files_mentioned)),
            metadata={"message_count": len(formatted_messages)},
        )

    def _extract_messages(self, content: str) -> List[dict]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            for key in ("messages", "conversation", "entries"):
                if key in parsed and isinstance(parsed[key], list):
                    return [item for item in parsed[key] if isinstance(item, dict)]
            return [parsed]

        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

        messages: List[dict] = []
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                messages.append(item)
        return messages

    def _extract_files(self, text: str) -> List[str]:
        import re

        pattern = r"[\w./\\-]+\.(py|js|ts|jsx|tsx|md|json|yaml|yml|html|css|go|rs)"
        files = []
        for ext in re.findall(pattern, text, re.IGNORECASE):
            full_pattern = rf"[\w./\\-]+\.{ext}"
            files.extend(re.findall(full_pattern, text, re.IGNORECASE))
        return files


def create_continue_watcher(path: Optional[str] = None, debounce: float = 1.0) -> ContinueWatcher:
    """Create a Continue.dev watcher instance."""
    return ContinueWatcher(watch_path=path, debounce_seconds=debounce)
