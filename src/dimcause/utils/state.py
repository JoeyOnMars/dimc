"""
任务状态管理 (Phase 3 & V6.0 Log Refactor)

核心功能:
1. Hexadecimal (16进制) 会话序列管理 (01-FF)
2. 跨午夜会话追踪 (Session Atomicity)
3. 活跃任务状态检测
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from dimcause.utils.config import get_config
from dimcause.utils.lock import with_lock

logger = logging.getLogger(__name__)


def get_root_dir() -> Path:
    """获取项目根目录"""
    return get_config().root_dir


def get_logs_dir() -> Path:
    """获取日志目录"""
    return get_config().logs_dir


def get_agent_dir() -> Path:
    """获取 .agent 目录"""
    return get_config().agent_dir


def _active_job_marker_path() -> Path:
    agent_dir = get_agent_dir()
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir / "active_job.json"


def _load_active_job_marker() -> Optional[dict]:
    marker = _active_job_marker_path()
    if not marker.exists():
        return None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return None


def _clear_active_job_marker() -> None:
    marker = _active_job_marker_path()
    if marker.exists():
        marker.unlink()


def _find_recent_job_dir(job_id: str, days: int = 7) -> Optional[Path]:
    for orphan in check_orphan_jobs(days=days):
        if orphan["id"] == job_id:
            return orphan["path"]
    return None


def check_pending_merge() -> Optional[str]:
    """
    检查是否有待合并的分支

    Returns:
        分支名称，或 None
    """
    pending_file = get_agent_dir() / "pending_merge.txt"
    if pending_file.exists():
        return pending_file.read_text().strip()
    return None


def set_pending_merge(branch_name: str):
    """记录待合并的分支"""
    agent_dir = get_agent_dir()
    agent_dir.mkdir(exist_ok=True)
    pending_file = agent_dir / "pending_merge.txt"
    pending_file.write_text(branch_name)


def clear_pending_merge():
    """清除待合并标记"""
    pending_file = get_agent_dir() / "pending_merge.txt"
    if pending_file.exists():
        pending_file.unlink()


def check_orphan_jobs(days: int = 3) -> List[dict]:
    """
    检查最近 N 天内未关闭的 Job
    """
    orphans = []
    logs_dir = get_logs_dir()
    cutoff_date = datetime.now() - timedelta(days=days)

    for year_dir in sorted(logs_dir.glob("20*"), reverse=True):
        if not year_dir.is_dir():
            continue
        for day_dir in sorted(year_dir.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue

            # Check date
            try:
                dir_date = datetime.strptime(f"{year_dir.name}-{day_dir.name}", "%Y-%m-%d")
                if dir_date < cutoff_date:
                    continue
            except (ValueError, OSError):
                continue

            jobs_dir = day_dir / "jobs"
            if not jobs_dir.exists():
                continue

            for job_dir in jobs_dir.iterdir():
                if not job_dir.is_dir():
                    continue
                job_id = job_dir.name

                start_file = job_dir / "job-start.md"
                end_file = job_dir / "job-end.md"

                if start_file.exists() and not end_file.exists():
                    orphans.append(
                        {
                            "id": job_id,
                            "date": f"{year_dir.name}-{day_dir.name}",
                            "path": job_dir,
                            "start_time": datetime.fromtimestamp(start_file.stat().st_mtime),
                        }
                    )

    return orphans


def get_active_job() -> Optional[Tuple[str, Path]]:
    """
    获取当前活跃的 Job ID 和路径 (从今天向前回溯 7 天)

    Returns:
        (job_id, job_dir_path) 或 None
    """
    marker_payload = _load_active_job_marker()
    if marker_payload:
        job_id = marker_payload.get("job_id")
        job_path = marker_payload.get("job_path")
        if isinstance(job_id, str) and isinstance(job_path, str):
            job_dir = Path(job_path)
            start_file = job_dir / "job-start.md"
            end_file = job_dir / "job-end.md"
            if job_dir.exists() and start_file.exists() and not end_file.exists():
                return (job_id, job_dir)
        _clear_active_job_marker()

    orphans = check_orphan_jobs(days=7)
    if orphans:
        # Return the most recent started job
        orphans.sort(key=lambda x: x["start_time"], reverse=True)
        return (orphans[0]["id"], orphans[0]["path"])
    return None


def record_job_start(job_id: str):
    """
    记录显式活跃 Job 状态，避免只靠 orphan 扫描推断。
    """
    marker_path = _active_job_marker_path()
    job_dir = _find_recent_job_dir(job_id) or (get_today_dir() / "jobs" / job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    with with_lock("active-job-marker", timeout=5):
        marker_path.write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "job_path": str(job_dir),
                    "updated_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def record_job_end():
    """
    清理显式活跃 Job 状态；目录层面仍由 job-end.md 作为真理源。
    """
    with with_lock("active-job-marker", timeout=5):
        _clear_active_job_marker()


def _is_hex_seq(s: str) -> bool:
    """检查是否为 2位 HEX 序列 (00-FF)"""
    return bool(re.match(r"^[0-9A-F]{2}$", s))


def get_next_hex_seq(day_dir: Path) -> str:
    """
    获取指定日期的下一个 HEX 序列号 (01 -> 02 ... 09 -> 0A ... FF)

    Args:
        day_dir: 日志日期目录

    Returns:
        2位大写 HEX 字符串 (如 "0B")
    """
    if not day_dir.exists():
        return "01"

    max_seq = 0
    # 扫描所有 XX-start.md
    for f in day_dir.glob("??-start.md"):
        seq_str = f.name[:2]
        if _is_hex_seq(seq_str):
            try:
                seq_val = int(seq_str, 16)
                if seq_val > max_seq:
                    max_seq = seq_val
            except ValueError:
                continue

    next_seq = max_seq + 1
    if next_seq > 255:
        raise ValueError("Day session limit (255) reached!")

    return f"{next_seq:02X}"


# --- Session Management ---


@dataclass
class ActiveSession:
    """活跃会话信息"""

    date_path: Path  # 会话归属的日期目录 (e.g. logs/2026/02-14)
    seq: str  # 序列号 (e.g. "0A")
    start_file: Path  # 启动文件路径
    start_time: datetime  # 启动时间
    agent: str = "unknown"  # Agent Identity

    @property
    def end_file(self) -> Path:
        """对应的结束文件路径 (同目录)"""
        return self.date_path / f"{self.seq}-end.md"

    @property
    def summary(self) -> str:
        """从结束文件提取摘要"""
        if not self.end_file.exists():
            return "Active (No End Log)"

        try:
            content = self.end_file.read_text(encoding="utf-8")
            # 1. Try frontmatter description
            match = re.search(r"^description:\s*[\"']?(.+?)[\"']?$", content, re.MULTILINE)
            if match and match.group(1).strip():
                return match.group(1).strip()

            # 2. Try ## Summary / ## 会话总结 section
            match = re.search(
                r"^##\s*(Summary|会话总结|Today's Summary).*?\n(.*?)(?=\n##|\Z)",
                content,
                re.DOTALL | re.MULTILINE | re.IGNORECASE,
            )
            if match:
                summary_text = match.group(2).strip()
                return (summary_text[:50] + "...") if len(summary_text) > 50 else summary_text

        except Exception:
            pass
        return "No summary"


def _extract_agent(file_path: Path) -> str:
    """从文件 Frontmatter 提取 agent"""
    try:
        content = file_path.read_text(encoding="utf-8")
        match = re.search(r"^agent:\s*[\"']?([^\"'\n]+)[\"']?", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return "unknown"


def ensure_today_dir() -> Path:
    """确保今日目录存在并返回路径（兼容旧 API）"""
    today = get_today_dir()
    today.mkdir(parents=True, exist_ok=True)
    return today


def get_today_dir() -> Path:
    """获取今天的日志目录 (物理时间)"""
    config = get_config()
    try:
        # 尝试使用配置的时区
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    return get_logs_dir() / now.strftime("%Y") / now.strftime("%m-%d")


def get_active_session(lookback_days: int = 7) -> Optional[ActiveSession]:
    """
    查找当前活跃的 Session (Source of Truth)

    逻辑:
    1. 扫描最近 N 天的日志目录
    2. 寻找有 'XX-start.md' 但没有对应 'XX-end.md' 的会话
    3. 返回最近的一个

    Args:
        lookback_days: 回溯天数 (默认2天，足够覆盖跨午夜)
    """
    logs_dir = get_logs_dir()
    cutoff_date = datetime.now() - timedelta(days=lookback_days)

    candidates: List[ActiveSession] = []

    # 遍历年份 (通常就今年和去年)
    for year_dir in sorted(logs_dir.glob("20*"), reverse=True):
        if not year_dir.is_dir():
            continue

        # 遍历日期 (最近的在前)
        for day_dir in sorted(year_dir.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue

            # 快速日期过滤
            try:
                dir_date = datetime.strptime(f"{year_dir.name}-{day_dir.name}", "%Y-%m-%d")
                if dir_date < cutoff_date:
                    continue
            except ValueError:
                continue

            # 扫描该日期的所有会话
            for start_file in day_dir.glob("??-start.md"):
                seq = start_file.name[:2]
                if not _is_hex_seq(seq):
                    continue

                end_file = day_dir / f"{seq}-end.md"

                if not end_file.exists():
                    # 这是一个未闭合的会话
                    candidates.append(
                        ActiveSession(
                            date_path=day_dir,
                            seq=seq,
                            start_file=start_file,
                            start_time=datetime.fromtimestamp(start_file.stat().st_mtime),
                            agent=_extract_agent(start_file),
                        )
                    )

    if not candidates:
        return None

    # 返回开始时间最近的一个 (Last Started)
    # 理论上应该只有一个活跃，但如果有多个 orphan，取最新的那个继续
    candidates.sort(key=lambda x: x.start_time, reverse=True)
    return candidates[0]


def get_last_session(lookback_days: int = 3) -> Optional[ActiveSession]:
    """
    获取最近的一个会话 (无论是否活跃)
    用于 session-start 恢复上下文
    """
    sessions = get_all_recent_sessions(lookback_days)
    return sessions[0] if sessions else None


def get_all_recent_sessions(lookback_days: int = 3) -> List[ActiveSession]:
    """
    获取最近的所有会话 (Multi-Agent Context)

    Returns:
        按时间倒序排列的 session 列表
    """
    logs_dir = get_logs_dir()
    cutoff_date = datetime.now() - timedelta(days=lookback_days)

    candidates: List[ActiveSession] = []

    for year_dir in sorted(logs_dir.glob("20*"), reverse=True):
        if not year_dir.is_dir():
            continue
        for day_dir in sorted(year_dir.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue
            try:
                dir_date = datetime.strptime(f"{year_dir.name}-{day_dir.name}", "%Y-%m-%d")
                if dir_date < cutoff_date:
                    continue
            except (ValueError, OSError):
                continue

            for start_file in day_dir.glob("??-start.md"):
                seq = start_file.name[:2]
                if not _is_hex_seq(seq):
                    continue
                candidates.append(
                    ActiveSession(
                        date_path=day_dir,
                        seq=seq,
                        start_file=start_file,
                        start_time=datetime.fromtimestamp(start_file.stat().st_mtime),
                        agent=_extract_agent(start_file),
                    )
                )

    candidates.sort(key=lambda x: x.start_time, reverse=True)
    return candidates


# --- Helper for Paths ---


def record_session_end_timestamp(session_id: str, end_dt: datetime) -> None:
    """
    记录 Session 的结束时间戳，用于两阶段 dimc down (RFC-001)
    """
    try:
        year, month, day, seq = session_id.split("-")
        session_dir = get_logs_dir() / year / f"{month}-{day}"
    except ValueError:
        return

    if not session_dir.exists():
        return

    lock_name = f"session-lock-{session_id}"
    with with_lock(lock_name, timeout=5):
        timestamp_file = session_dir / f"{seq}-end_timestamp.txt"
        timestamp_file.write_text(end_dt.isoformat(), encoding="utf-8")


def get_session_end_timestamp(session_id: str) -> Optional[datetime]:
    """
    获取由 Phase 1 记录的 Session 结束时间戳
    """
    try:
        year, month, day, seq = session_id.split("-")
        session_dir = get_logs_dir() / year / f"{month}-{day}"
    except ValueError:
        return None

    timestamp_file = session_dir / f"{seq}-end_timestamp.txt"
    if timestamp_file.exists():
        try:
            return datetime.fromisoformat(timestamp_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return None


def get_session_start_timestamp(session_id: str) -> Optional[datetime]:
    """
    获取 Session 的启动时间戳
    """
    try:
        year, month, day, seq = session_id.split("-")
        session_dir = get_logs_dir() / year / f"{month}-{day}"
    except ValueError:
        return None

    start_file = session_dir / f"{seq}-start.md"
    if start_file.exists():
        return datetime.fromtimestamp(start_file.stat().st_mtime)
    return None


def resolve_session_path(kind: str = "start") -> Tuple[Path, str]:
    """
    决定当前操作应该针对哪个文件路径

    Args:
        kind: 'start' | 'end'

    Returns:
        (target_file_path, seq_id)

    Raises:
        ValueError: 如果是 end 但找不到活跃会话
    """
    if kind == "start":
        # Start 总是针对"今天"
        today_dir = get_today_dir()
        if not today_dir.exists():
            today_dir.mkdir(parents=True)

        # Atomic Session Creation (RFC-002)
        # Lock scope: daily directory to prevent race condition on seq generation
        # today_dir is logs/YYYY/MM-DD
        date_str = f"{today_dir.parent.name}-{today_dir.name}"
        lock_name = f"session-creation-{date_str}"

        with with_lock(lock_name, timeout=5):
            seq = get_next_hex_seq(today_dir)
            target_file = today_dir / f"{seq}-start.md"

            # Reserve the file immediately to claim the ID
            if not target_file.exists():
                target_file.touch()

            return target_file, seq

    elif kind == "end":
        # Strategy A: Check for an explicitly OPEN session first (Ideal case)
        session = get_active_session()
        if session:
            return session.end_file, session.seq

        # Strategy B: Session Continuity (Late Night / Re-run Scenario)
        # User might run `dimc down` multiple times, or across midnight.
        # If no open session, look for the *latest started* session in recent history (lookback=2 days).
        # We prefer "yesterday's last session" over "creating a new orphan session for today".
        last_session = get_last_session(lookback_days=2)
        if last_session:
            # Evaluate age and date-boundary
            start_age = datetime.now() - last_session.start_time
            today_dir = get_today_dir()
            is_same_day = last_session.date_path == today_dir

            # Prevent date-mismatch: Only reuse if it's from the same exact day directory
            # or if we are firmly designing a cross-midnight carry-over (not recommended for strict isolation).
            # We enforce same-day to ensure `end.md` lands in the matching `YYYY/MM-DD/` folder.
            if start_age < timedelta(hours=16) and is_same_day:
                logger.info(
                    f"Session Continuity: Reusing recent session {last_session.seq} (Started {start_age} ago)"
                )
                return last_session.end_file, last_session.seq

        # Strategy C: Safe Fallback (Brand new day, no recent context)
        # Verify if TODAY actually has a start file?
        today_dir = get_today_dir()
        if not today_dir.exists():
            today_dir.mkdir(parents=True)

        # If we are here, it means:
        # 1. No open session.
        # 2. No recent session (<16h).
        # 3. So we probably should create a new one for today.

        # But wait, if today has NO start files, creating an end file is "orphan".
        # Check if today has any starts
        has_starts = any(today_dir.glob("??-start.md"))

        if not has_starts:
            # If today has no starts, and we didn't find a recent session from yesterday...
            # This is a weird state for `dimc down`.
            # But we must generate *something*.
            logger.warning("No active/recent session found. Creating new orphan end log for today.")

        seq = get_next_hex_seq(today_dir)
        return today_dir / f"{seq}-end.md", seq

    else:
        raise ValueError(f"Unknown kind: {kind}")
