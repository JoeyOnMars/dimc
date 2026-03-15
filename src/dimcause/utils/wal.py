"""
Dimcause Write-Ahead Log (WAL) - 崩溃恢复机制

Critical P0 Implementation: 防止daemon崩溃时数据丢失
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WALEntry:
    """WAL日志条目"""

    id: str  # 事件唯一ID
    timestamp: float  # Unix时间戳
    event_type: str  # pending | completed | failed
    data: Dict[str, Any]  # 事件数据
    retry_count: int = 0


class WriteAheadLog:
    """
    Write-Ahead Log 实现

    工作原理:
    1. 处理前: 先写入WAL(pending状态)
    2. 处理完成: 标记为completed
    3. 崩溃恢复: 重新处理所有pending状态的事件

    文件格式: JSONL (每行一个JSON对象)
    """

    DEFAULT_DIR = ".dimcause"
    LEGACY_DIR = ".mal"
    WAL_FILE = "wal.log"

    @classmethod
    def _resolve_default_wal_path(cls) -> Path:
        """解析默认 WAL 路径，并在首次启动时迁移 legacy .mal 路径。"""
        home = Path.home()
        default_path = home / cls.DEFAULT_DIR / cls.WAL_FILE
        legacy_path = home / cls.LEGACY_DIR / cls.WAL_FILE

        if default_path.exists() or not legacy_path.exists():
            return default_path

        default_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            legacy_path.replace(default_path)
            logger.info("WAL migrated from %s to %s", legacy_path, default_path)
            return default_path
        except OSError as exc:
            logger.warning("WAL migration failed, fallback to legacy path %s: %s", legacy_path, exc)
            return legacy_path

    def __init__(self, wal_path: Optional[str] = None):
        """
        初始化WAL

        Args:
            wal_path: WAL文件路径(默认 ~/.dimcause/wal.log)
        """
        if wal_path is None:
            wal_path = str(self._resolve_default_wal_path())

        self.wal_path = Path(wal_path)
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)

        # 确保文件存在
        if not self.wal_path.exists():
            self.wal_path.touch()

    def append_pending(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        记录待处理事件

        Args:
            event_id: 事件唯一ID
            event_data: 事件数据
        """
        entry = WALEntry(id=event_id, timestamp=time.time(), event_type="pending", data=event_data)

        self._append_entry(entry)
        logger.debug(f"WAL: Recorded pending event {event_id}")

    def mark_completed(self, event_id: str) -> None:
        """
        标记事件为已完成

        Args:
            event_id: 事件ID
        """
        entry = WALEntry(id=event_id, timestamp=time.time(), event_type="completed", data={})

        self._append_entry(entry)
        logger.debug(f"WAL: Marked {event_id} as completed")

    def mark_failed(self, event_id: str, error: str, retry_count: int = 0) -> None:
        """
        标记事件失败

        Args:
            event_id: 事件ID
            error: 错误信息
            retry_count: 重试次数
        """
        entry = WALEntry(
            id=event_id,
            timestamp=time.time(),
            event_type="failed",
            data={"error": error},
            retry_count=retry_count,
        )

        self._append_entry(entry)
        logger.warning(f"WAL: Event {event_id} failed (retry={retry_count}): {error}")

    def _append_entry(self, entry: WALEntry) -> None:
        """追加条目到WAL文件"""
        # 确保上一行以换行符结尾（防止崩溃留下半截 JSON 粘连新行）
        if self.wal_path.exists() and self.wal_path.stat().st_size > 0:
            with open(self.wal_path, "rb") as f:
                f.seek(-1, 2)
                last_byte = f.read(1)
            if last_byte != b"\n":
                with open(self.wal_path, "ab") as f:
                    f.write(b"\n")

        with open(self.wal_path, "a", encoding="utf-8") as f:
            json_line = json.dumps(asdict(entry), default=str)
            f.write(json_line + "\n")
            f.flush()
            os.fsync(f.fileno())  # 强制刷盘

    def recover_pending(self) -> List[WALEntry]:
        """
        恢复未完成的事件

        Returns:
            未完成的事件列表(待重试)
        """
        pending_events = {}  # event_id -> WALEntry
        completed_ids = set()
        failed_ids = set()

        # 读取完整WAL历史
        if not self.wal_path.exists():
            return []

        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    entry = WALEntry(**data)

                    if entry.event_type == "pending":
                        pending_events[entry.id] = entry
                    elif entry.event_type == "completed":
                        completed_ids.add(entry.id)
                    elif entry.event_type == "failed":
                        failed_ids.add(entry.id)

                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"WAL: Failed to parse line: {e}")
                    continue

        # 找出真正待处理的事件
        unfinished = [
            entry
            for event_id, entry in pending_events.items()
            if event_id not in completed_ids and event_id not in failed_ids
        ]

        if unfinished:
            logger.info(f"🔄 WAL: Recovered {len(unfinished)} unfinished events")

        return unfinished

    def compact(self, keep_completed: bool = False) -> int:
        """
        压缩WAL文件(删除已完成的事件)

        Args:
            keep_completed: 是否保留已完成的记录(用于审计)

        Returns:
            删除的条目数量
        """
        pending_events = {}
        completed_ids = set()
        failed_events = {}

        # 读取整个WAL
        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    entry = WALEntry(**data)

                    if entry.event_type == "pending":
                        pending_events[entry.id] = entry
                    elif entry.event_type == "completed":
                        completed_ids.add(entry.id)
                    elif entry.event_type == "failed":
                        failed_events[entry.id] = entry

                except (json.JSONDecodeError, TypeError):
                    continue

        # 重建WAL文件
        backup_path = self.wal_path.with_suffix(".log.bak")
        self.wal_path.rename(backup_path)

        kept_count = 0

        with open(self.wal_path, "w", encoding="utf-8") as f:
            # 保留未完成的pending
            for event_id, entry in pending_events.items():
                if event_id not in completed_ids:
                    f.write(json.dumps(asdict(entry), default=str) + "\n")
                    kept_count += 1

            # 保留failed事件(可能需要人工干预)
            for entry in failed_events.values():
                f.write(json.dumps(asdict(entry), default=str) + "\n")
                kept_count += 1

            # 可选:保留completed记录
            if keep_completed:
                entry = WALEntry(
                    id=event_id, timestamp=time.time(), event_type="completed", data={}
                )
                f.write(json.dumps(asdict(entry), default=str) + "\n")
                kept_count += 1

        # 删除备份
        backup_path.unlink()

        removed = len(pending_events) + len(completed_ids) + len(failed_events) - kept_count
        logger.info(f"WAL: Compacted, removed {removed} entries, kept {kept_count}")

        return removed

    def stats(self) -> Dict[str, int]:
        """获取WAL统计信息"""
        pending = 0
        completed = 0
        failed = 0

        if not self.wal_path.exists():
            return {"pending": 0, "completed": 0, "failed": 0}

        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    event_type = data.get("event_type")
                    if event_type == "pending":
                        pending += 1
                    elif event_type == "completed":
                        completed += 1
                    elif event_type == "failed":
                        failed += 1
                except (json.JSONDecodeError, TypeError):
                    continue

        return {"pending": pending, "completed": completed, "failed": failed}


# 全局WAL实例
_wal_instance = None


def get_wal(wal_path: Optional[str] = None) -> WriteAheadLog:
    """获取全局WAL实例(单例)"""
    global _wal_instance
    if _wal_instance is None:
        _wal_instance = WriteAheadLog(wal_path)
    return _wal_instance
