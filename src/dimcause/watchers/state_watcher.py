"""
StateWatcher - 代码状态变化监听

通过轮询 Git HEAD 变化，把代码状态变化转成 RawData 送入现有 pipeline。
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dimcause.core.models import RawData, SourceType
from dimcause.utils.git import GitRepo
from dimcause.watchers.base import BaseWatcher

logger = logging.getLogger(__name__)


class StateDriver:
    """Base class for state monitoring drivers."""

    def check(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class CodeStateDriver(StateDriver):
    """Driver to monitor code changes via Git HEAD."""

    MAX_DIFF_LINES = 80
    MAX_DIFF_CHARS = 4000

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.repo = GitRepo(project_path)
        self.last_head = self.repo.get_head_commit()
        self.last_status = tuple(sorted(self.repo.get_status()))

    def _extract_changed_files(self, status_lines: List[str]) -> List[str]:
        files: List[str] = []
        for line in status_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if " -> " in stripped:
                files.append(stripped.split(" -> ", 1)[1])
                continue
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                files.append(parts[1])
        return files

    def _truncate_diff_excerpt(self, diff_text: str) -> Dict[str, Any]:
        text = diff_text.strip()
        if not text:
            return {"diff_excerpt": "", "diff_truncated": False}

        lines = text.splitlines()
        truncated = False
        if len(lines) > self.MAX_DIFF_LINES:
            lines = lines[: self.MAX_DIFF_LINES]
            truncated = True

        excerpt = "\n".join(lines).strip()
        if len(excerpt) > self.MAX_DIFF_CHARS:
            excerpt = excerpt[: self.MAX_DIFF_CHARS].rstrip()
            truncated = True

        if truncated:
            excerpt = f"{excerpt}\n... [truncated]"

        return {"diff_excerpt": excerpt, "diff_truncated": truncated}

    def check(self) -> List[Dict[str, Any]]:
        changes = []
        current_head = self.repo.get_head_commit()
        current_status = tuple(sorted(self.repo.get_status()))

        if current_head and current_head != self.last_head:
            commit_info = self.repo.get_commit_info(current_head)
            if self.last_head:
                files_changed = self.repo.get_changed_files(self.last_head, current_head)
                diff_text = self.repo.get_diff_range(self.last_head, current_head)
            else:
                files_changed = self.repo.get_commit_files(current_head)
                diff_text = self.repo.get_diff(current_head)
            changes.append(
                {
                    "type": "code_state_change",
                    "source": "git",
                    "summary": commit_info.get("message", "No message"),
                    "details": {
                        "previous_commit": self.last_head,
                        "commit": current_head,
                        "files_changed": files_changed,
                        **commit_info,
                        **self._truncate_diff_excerpt(diff_text),
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.last_head = current_head

        if current_status != self.last_status:
            files_changed = self._extract_changed_files(list(current_status))
            changes.append(
                {
                    "type": "working_tree_change",
                    "source": "git",
                    "summary": (
                        f"Working tree changed ({len(files_changed)} files)"
                        if files_changed
                        else "Working tree is clean"
                    ),
                    "details": {
                        "status_lines": list(current_status),
                        "files_changed": files_changed,
                        **self._truncate_diff_excerpt(self.repo.get_working_tree_diff()),
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.last_status = current_status

        return changes


class StateWatcher(BaseWatcher):
    """
    Polling-based code state watcher.

    Unlike file watchers, this watcher polls Git state and emits RawData when HEAD changes.
    """

    def __init__(self, project_path: Optional[str] = None, interval_seconds: float = 10.0):
        resolved_path = str(Path(project_path or ".").expanduser())
        super().__init__(
            watch_path=resolved_path,
            source=SourceType.FILE,
            debounce_seconds=interval_seconds,
        )
        self.project_path = resolved_path
        self.interval_seconds = interval_seconds
        self.driver = CodeStateDriver(self.project_path)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def name(self) -> str:
        return "state"

    def start(self) -> None:
        if self._is_running:
            return

        project_root = Path(self.project_path)
        if not project_root.exists():
            raise FileNotFoundError(f"Project path not found: {self.project_path}")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="StateWatcher",
            daemon=True,
        )
        self._thread.start()
        self._is_running = True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.interval_seconds + 1.0)
        self._thread = None
        self._is_running = False

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                for change in self.driver.check():
                    raw_data = self._change_to_raw_data(change)
                    for callback in self._callbacks:
                        callback(raw_data)
            except Exception as exc:
                logger.error("StateWatcher polling failed: %s", exc)

            self._stop_event.wait(self.interval_seconds)

    def _change_to_raw_data(self, change: Dict[str, Any]) -> RawData:
        details = change.get("details", {})
        files_mentioned = details.get("files_changed", [])
        if not isinstance(files_mentioned, list):
            files_mentioned = []

        return RawData(
            id=f"state_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            source=SourceType.FILE,
            timestamp=datetime.now(),
            content=change.get("summary", "Code state changed"),
            files_mentioned=files_mentioned,
            project_path=self.project_path,
            metadata={
                "state_change_type": change.get("type", "code_state_change"),
                **details,
            },
        )

    def _parse_content(self, content: str):
        """Unused for polling watcher; required by BaseWatcher."""
        return None


def create_state_watcher(
    project_path: Optional[str] = None, interval_seconds: float = 10.0
) -> StateWatcher:
    return StateWatcher(project_path=project_path, interval_seconds=interval_seconds)
