"""
DataCollector (L1)

负责从各个数据源采集 Raw Data，作为 Session End 流程的统一数据入口。
遵循 System Context 定义的 L0 -> L1 数据流。
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dimcause.utils.config import get_config


def _local_naive_to_utc(dt: datetime) -> datetime:
    """Convert local naive datetime to UTC-aware datetime."""
    if dt.tzinfo is not None:
        return dt
    # Use current offset approximation
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    offset = now_utc.replace(tzinfo=None) - now_local
    return dt.replace(tzinfo=timezone.utc) + offset


@dataclass
class SessionData:
    """会话原始数据集合 (L1 Object)"""

    session_id: str
    date_str: str

    # Brain Artifacts (L0.5)
    brain_artifacts: Dict[str, str] = field(default_factory=dict)
    brain_metadata: Dict[str, str] = field(default_factory=dict)

    # Raw CHATS (L0 -> L1)
    raw_chat_files: List[Path] = field(default_factory=list)
    external_source_files: List[Path] = field(default_factory=list)

    # Claude Code JSONL Sessions (L0 -> L1)
    claude_code_sessions: List = field(default_factory=list)  # List[ClaudeSession]
    claude_code_markdown: str = ""  # Combined markdown from all matched sessions

    # System Context (L1)
    git_diff: str = ""
    git_log: str = ""
    job_logs: List[str] = field(default_factory=list)


class DataCollector:
    def __init__(
        self,
        session_id: str,
        date_str: str,
        session_start: Optional[datetime] = None,
        session_end: Optional[datetime] = None,
    ):
        self.session_id = session_id
        self.date_str = date_str
        self.session_start = session_start
        self.session_end = session_end
        self.config = get_config()
        self.brain_dir = self.config.brain_dir
        self.root_dir = self.config.root_dir

    def collect_all(self) -> SessionData:
        """采集所有数据"""
        data = SessionData(session_id=self.session_id, date_str=self.date_str)

        # 1. Brain Artifacts
        self._collect_brain_artifacts(data)

        # 2. Raw Chats (配置导出目录 + External)
        self._collect_raw_chats(data)

        # 3. Claude Code JSONL Sessions
        self._collect_claude_code_sessions(data)

        # 4. System Context
        self._collect_git_context(data)
        self._collect_job_logs(data)

        return data

    def _collect_brain_artifacts(self, data: SessionData):
        """采集 Brain 目录下的工件"""
        if not self.brain_dir or not self.brain_dir.exists():
            return

        # 核心工件
        artifacts = ["task.md", "implementation_plan.md", "walkthrough.md"]
        for name in artifacts:
            p = self.brain_dir / name
            if p.exists():
                data.brain_artifacts[name] = p.read_text(encoding="utf-8")

        # Metadata
        for p in self.brain_dir.glob("*.metadata.json"):
            data.brain_metadata[p.name] = p.read_text(encoding="utf-8")

        # System Generated Logs (RFC-004 mention, though not fully parsed yet)
        # 暂时只记录存在性，未来可以解析 steps/output.txt

    def _collect_raw_chats(self, data: SessionData):
        """采集原始对话日志"""
        # 1. 配置的导出目录（默认 ~/Documents/AG_Exports）
        # 匹配规则: 文件修改时间位于会话窗口内，或日期匹配 session date
        export_dir = Path(self.config.export_dir).expanduser()
        if export_dir.exists():
            try:
                s_date = datetime.strptime(self.date_str, "%Y-%m-%d").date()
            except ValueError:
                s_date = None

            for p in export_dir.glob("*.md"):
                mtime_dt = datetime.fromtimestamp(p.stat().st_mtime)

                # Check based on exact time window if available
                if self.session_start and self.session_end:
                    # [session_start - 3600s, session_end + 300s]
                    window_start = self.session_start - timedelta(seconds=3600)
                    window_end = self.session_end + timedelta(seconds=300)
                    if window_start <= mtime_dt <= window_end:
                        data.raw_chat_files.append(p)
                elif s_date:
                    # Fallback to date_str match
                    if mtime_dt.date() == s_date:
                        data.raw_chat_files.append(p)
                else:
                    data.raw_chat_files.append(p)

        # 2. Configured External Sources (e.g., Claude Logs)
        for source_path in self.config.external_sources:
            if not source_path.exists():
                continue

            if source_path.is_file():
                # 单文件直接添加
                data.external_source_files.append(source_path)
            elif source_path.is_dir():
                # 目录则扫描
                # 这里需要更智能的扫描策略，暂时扫描所有最近修改的文件?
                # 或者文件名匹配?
                # Strategy: Filter by session date match
                # Parse date_str "YYYY-MM-DD"
                try:
                    s_date = datetime.strptime(self.date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue  # Invalid date_str, skip heuristic scan

                for p in source_path.glob("*"):
                    if p.is_file() and p.suffix in (".json", ".md"):
                        # Check mtime match session date
                        mtime_date = datetime.fromtimestamp(p.stat().st_mtime).date()
                        if mtime_date == s_date:
                            data.external_source_files.append(p)

    def _collect_claude_code_sessions(self, data: SessionData):
        """采集 Claude Code JSONL 会话"""
        # Define safe defaults for orphan sessions
        end_time = self.session_end or datetime.now()
        # Default back to 72 hours for orphans to catch weekend gaps and multi-day long sessions
        start_time = self.session_start or (end_time - timedelta(hours=72))

        try:
            from dimcause.extractors.claude_code_parser import ClaudeCodeLogParser
            from dimcause.utils.config import get_config

            config = get_config()
            sessions_dir = config.claude_code_sessions_dir

            if not sessions_dir:
                return

            parser = ClaudeCodeLogParser(root_dir=self.root_dir, sessions_dir=sessions_dir)

            # Convert local naive datetime to UTC-aware
            start_utc = _local_naive_to_utc(start_time)
            end_utc = _local_naive_to_utc(end_time)

            sessions = parser.find_sessions(start_utc, end_utc)
            if not sessions:
                return

            data.claude_code_sessions = sessions

            # Convert to markdown (combine all matched sessions)
            parts = []
            for session in sessions:
                md = parser.parse_to_markdown(session, start_time=start_utc, end_time=end_utc)
                if md:
                    parts.append(md)

            data.claude_code_markdown = "\n\n---\n\n".join(parts)

        except Exception as e:
            # Non-fatal: existing raw chat flow continues
            import logging

            logging.getLogger(__name__).warning(f"Claude Code JSONL collection failed: {e}")

    def _collect_git_context(self, data: SessionData):
        """采集 Git 上下文"""
        # Git Diff (Unstaged + Staged)
        try:
            # Unstaged
            diff = subprocess.check_output(["git", "diff"], cwd=self.root_dir, text=True)
            # Staged
            diff_staged = subprocess.check_output(
                ["git", "diff", "--staged"], cwd=self.root_dir, text=True
            )
            data.git_diff = diff + "\n" + diff_staged
        except subprocess.CalledProcessError:
            pass

        # Git Log (Since session start?)
        # 这是一个难点: session start time 在哪里?
        # 可以从 brain dir creation time 推断
        if self.brain_dir:
            start_time = self.brain_dir.stat().st_ctime
            # Format for git --since
            since_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
            try:
                log = subprocess.check_output(
                    ["git", "log", f"--since='{since_str}'", "--pretty=format:%h - %s (%an)"],
                    cwd=self.root_dir,
                    text=True,
                )
                data.git_log = log
            except subprocess.CalledProcessError:
                pass

    def _collect_job_logs(self, data: SessionData):
        """采集 Job Logs"""
        # docs/logs/YYYY/MM-DD/jobs/*/job-end.md
        # 需要解析 date_str: YYYY-MM-DD
        try:
            # date_str 可能是 "2026-02-19"
            year, month, day = self.date_str.split("-")
            # 目录结构 docs/logs/2026/02-19/jobs/
            jobs_dir = self.root_dir / "docs/logs" / year / f"{month}-{day}" / "jobs"

            if jobs_dir.exists():
                for job_dir in jobs_dir.iterdir():
                    if job_dir.is_dir():
                        end_md = job_dir / "job-end.md"
                        if end_md.exists():
                            data.job_logs.append(end_md.read_text(encoding="utf-8"))
        except ValueError:
            pass  # date_str format error
