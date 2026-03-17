"""
Dimcause V0.9 Orchestrator - 任务调度与状态管理

核心职责: 读取状态 → 发现不一致 → 调度任务 → 验证完成
"""

import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

from dimcause.runtime.contracts import Run
from dimcause.scheduler.run_bridge import scheduler_task_runtime_to_run
from dimcause.scheduler.status_files import (
    MODERN_STATUS_FILE as MODERN_STATUS_PATH,
)
from dimcause.scheduler.status_files import (
    extract_modern_progress_rows,
    resolve_status_file,
)
from dimcause.utils.lock import with_lock

# 配置日志
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""

    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BLOCKED = "Blocked"


class TaskPriority(Enum):
    """任务优先级 (数值越小优先级越高)"""

    P0 = 0  # 立即执行
    P1 = 1  # 次优先
    P2 = 2  # 可延后
    P3 = 3  # 低优先级


@dataclass
class TaskInfo:
    """任务信息"""

    id: str  # D1, T1, H1, S3
    name: str  # Deep Decision Replay
    cli: str  # mal why
    status: TaskStatus = TaskStatus.PLANNED
    priority: TaskPriority = TaskPriority.P2
    agent_task_path: Optional[Path] = None
    blockers: List[str] = field(default_factory=list)
    acceptance_criteria: str = ""


@dataclass
class Job:
    """调度任务单元"""

    name: str
    interval: float  # 秒
    func: Callable
    last_run: Optional[float] = None
    run_count: int = 0
    error_count: int = 0


class Orchestrator:
    """
    Dimcause V6 任务调度器

    核心使命: 自动化实现 mal-agent-loop.md 的"读取→规划→执行→验证→记录"循环
    """

    STATUS_FILE = MODERN_STATUS_PATH
    AGENT_TASKS_DIR = ".agent/agent-tasks"
    RUNTIME_STATE_FILE = ".agent/scheduler_state.json"
    TASK_PACKET_DIR = Path("tmp/coordination/task_packets")
    TASK_BOARD_FILE = Path("tmp/coordination/task_board.md")
    TASK_FILE_HINTS = {
        "dimc scheduler": [
            "src/dimcause/scheduler/orchestrator.py",
            "src/dimcause/scheduler/runner.py",
            "src/dimcause/scheduler/loop.py",
            "src/dimcause/cli.py",
            "docs/STATUS.md",
        ],
        "dimc search": [
            "src/dimcause/search/engine.py",
            "src/dimcause/search/unix_retrieval.py",
            "src/dimcause/cli.py",
            "tests/search/test_engine.py",
        ],
        "dimc why": [
            "src/dimcause/core/history.py",
            "src/dimcause/brain/analyzer.py",
            "src/dimcause/cli.py",
            "tests/test_cli_history.py",
        ],
        "dimc detect": [
            "src/dimcause/watchers/detector.py",
            "src/dimcause/utils/config.py",
            "src/dimcause/cli.py",
            "tests/test_cli_detect.py",
        ],
        "dimc mcp": [
            "src/dimcause/protocols/mcp_server.py",
            "src/dimcause/cli.py",
        ],
    }

    def __init__(self, project_root: Path = None):
        self.root = project_root or Path.cwd()
        self._state: Dict = {}
        self._tasks: List[TaskInfo] = []
        # 后台调度相关属性 (V6.x)
        self._jobs: Dict[str, Job] = {}
        self._running = False
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

    def _runtime_state_path(self) -> Path:
        path = self.root / self.RUNTIME_STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _task_packet_dir_path(self) -> Path:
        path = self.root / self.TASK_PACKET_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _job_logs_root(self) -> Path:
        now = datetime.now()
        path = self.root / "docs" / "logs" / now.strftime("%Y") / now.strftime("%m-%d") / "jobs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_job_dir(self, job_id: str) -> Path:
        active_job = self.get_active_job()
        if active_job and active_job[0] == job_id:
            job_dir = active_job[1]
            job_dir.mkdir(parents=True, exist_ok=True)
            return job_dir

        existing = sorted(self.root.glob(f"docs/logs/20*/??-??/jobs/{job_id}"))
        if existing:
            existing[-1].mkdir(parents=True, exist_ok=True)
            return existing[-1]

        job_dir = self._job_logs_root() / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _task_workspace_slug(self, task_id: str) -> str:
        ascii_part = re.sub(r"[^a-z0-9]+", "-", task_id.lower()).strip("-")
        digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:8]
        if not ascii_part:
            ascii_part = "task"
        return f"scheduler-{ascii_part[:24]}-{digest}"

    def _task_branch_name(self, task_id: str, work_class: str = "product") -> str:
        ascii_part = re.sub(r"[^a-z0-9]+", "-", task_id.lower()).strip("-")
        digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:8]
        if not ascii_part:
            ascii_part = "task"
        prefix = {
            "product": "codex/task-",
            "ops": "codex/ops-",
            "rescue": "codex/rescue-",
            "rfc": "codex/rfc-",
        }.get(work_class, "codex/task-")
        return f"{prefix}{ascii_part[:24]}-{digest}"

    def _find_worktree_for_branch(self, branch_name: str) -> Optional[Path]:
        from dimcause.utils.git import run_git

        code, out, _ = run_git("worktree", "list", "--porcelain", cwd=self.root)
        if code != 0 or not out:
            return None

        current_path: Optional[Path] = None
        for line in out.splitlines():
            if line.startswith("worktree "):
                current_path = Path(line.removeprefix("worktree ").strip())
                continue
            if line.startswith("branch "):
                branch_ref = line.removeprefix("branch ").strip()
                if branch_ref == f"refs/heads/{branch_name}" and current_path is not None:
                    return current_path
        return None

    def provision_task_workspace(
        self, task_id: str, base_ref: str = "main", work_class: str = "product"
    ) -> Dict[str, str]:
        from dimcause.utils.git import run_git

        slug = self._task_workspace_slug(task_id)
        branch_name = self._task_branch_name(task_id, work_class=work_class)
        existing = self._find_worktree_for_branch(branch_name)
        if existing is not None:
            return {"branch": branch_name, "worktree": str(existing)}

        worktree_root = Path("/tmp") / "dimc-worktrees"
        worktree_root.mkdir(parents=True, exist_ok=True)
        worktree_path = worktree_root / slug
        if worktree_path.exists():
            raise RuntimeError(f"Provision target already exists: {worktree_path}")

        code, _, err = run_git(
            "worktree",
            "add",
            str(worktree_path),
            "-b",
            branch_name,
            base_ref,
            cwd=self.root,
        )
        if code != 0:
            raise RuntimeError(f"Failed to provision worktree for {task_id}: {err}")

        return {"branch": branch_name, "worktree": str(worktree_path)}

    def task_board_path(self) -> Path:
        path = self.root / self.TASK_BOARD_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def load_runtime_state(self) -> Dict:
        path = self._runtime_state_path()
        if not path.exists():
            return {"tasks": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"tasks": {}}
        if not isinstance(data, dict):
            return {"tasks": {}}
        tasks = data.get("tasks")
        if not isinstance(tasks, dict):
            data["tasks"] = {}
        return data

    def _save_runtime_state(self, state: Dict) -> None:
        path = self._runtime_state_path()
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _current_branch(self) -> str:
        try:
            from dimcause.utils.git import run_git

            code, out, _ = run_git("branch", "--show-current", cwd=self.root)
            return out.strip() if code == 0 and out.strip() else "unknown"
        except Exception:
            return "unknown"

    def get_task_runtime(self, task_id: str) -> Optional[Dict]:
        state = self.load_runtime_state()
        task_state = state.get("tasks", {}).get(task_id)
        return task_state if isinstance(task_state, dict) else None

    def get_task_run(self, task_id: str) -> Optional[Run]:
        runtime = self.get_task_runtime(task_id)
        if runtime is None:
            return None
        return scheduler_task_runtime_to_run(
            task_id=task_id,
            runtime=runtime,
            project_root=self.root,
        )

    def inspect_task_runtime(self, task_id: str) -> Dict[str, object]:
        runtime = self.get_task_runtime(task_id)
        if runtime is None:
            raise RuntimeError(f"No runtime state found for task: {task_id}")

        path_fields = (
            "context_file",
            "task_packet_file",
            "task_board_file",
            "job_dir",
            "worktree",
            "session_dir",
            "session_file",
            "session_readme",
            "durable_session_file",
            "session_preflight_script",
            "session_launch_script",
            "session_codex_run_script",
            "session_codex_output_file",
            "session_launch_log",
        )
        artifacts: List[Dict[str, object]] = []
        for artifact_name in path_fields:
            value = runtime.get(artifact_name)
            if not isinstance(value, str) or not value.strip():
                continue
            path = Path(value)
            artifacts.append(
                {
                    "name": artifact_name,
                    "path": str(path),
                    "exists": path.exists(),
                }
            )

        pid_value = runtime.get("session_launch_pid")
        launch_running = self._is_process_alive(pid_value)
        run = self.get_task_run(task_id)

        return {
            "task_id": task_id,
            "runtime": dict(runtime),
            "run": run.model_dump(mode="json") if run is not None else None,
            "artifacts": artifacts,
            "launch_running": launch_running,
        }

    def _ref_exists(self, ref: str) -> bool:
        from dimcause.utils.git import run_git

        normalized = ref.strip()
        if not normalized:
            return False
        code, _, _ = run_git("rev-parse", "--verify", "--quiet", normalized, cwd=self.root)
        return code == 0

    def _tracked_worktree_is_clean(self) -> bool:
        from dimcause.utils.git import run_git

        code, out, _ = run_git("status", "--short", "--untracked-files=no", cwd=self.root)
        return code == 0 and not out.strip()

    def _ahead_behind_counts(self, base_ref: str, branch: str) -> Optional[Dict[str, int]]:
        from dimcause.utils.git import run_git

        if not self._ref_exists(base_ref) or not self._ref_exists(branch):
            return None
        code, out, _ = run_git(
            "rev-list", "--left-right", "--count", f"{base_ref}...{branch}", cwd=self.root
        )
        if code != 0 or not out.strip():
            return None
        parts = out.split()
        if len(parts) != 2:
            return None
        return {"base_only": int(parts[0]), "branch_only": int(parts[1])}

    @staticmethod
    def _frontmatter_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def summarize_task_closeout(
        self,
        task_id: str,
        *,
        base_ref: str = "main",
        allow_implementation: bool = False,
    ) -> Dict[str, object]:
        task_card = self.load_task_card(task_id)
        if "error" in task_card:
            raise RuntimeError(str(task_card["error"]))

        runtime = self.get_task_runtime(task_id) or {}
        launch_running = False
        artifacts: List[Dict[str, object]] = []
        if runtime:
            inspection = self.inspect_task_runtime(task_id)
            launch_running = bool(inspection.get("launch_running"))
            raw_artifacts = inspection.get("artifacts")
            if isinstance(raw_artifacts, list):
                artifacts = [artifact for artifact in raw_artifacts if isinstance(artifact, dict)]

        task_class = str(task_card.get("task_class") or "").strip().lower() or "implementation"
        cli_hint = str(task_card.get("cli_hint") or "-").strip() or "-"
        branch = str(runtime.get("branch") or "").strip()
        report_path = Path(str(runtime["report_path"])) if runtime.get("report_path") else None
        report_exists = bool(report_path and report_path.exists())
        pr_ready_report = str(runtime.get("pr_ready_report") or "").strip()
        pr_ready_present = bool(pr_ready_report)
        low_risk_by_class = task_class in {"docs", "governance", "test"}
        explicit_auto_closeout = self._frontmatter_bool(task_card.get("auto_closeout"))
        closeout_policy = "auto" if (low_risk_by_class or explicit_auto_closeout) else "manual"
        ahead_behind = self._ahead_behind_counts(base_ref, branch) if branch else None

        blocking_reasons: List[str] = []
        if not runtime:
            blocking_reasons.append("missing_runtime_state")
        if str(runtime.get("status") or "") != "done":
            blocking_reasons.append("runtime_status_not_done")
        if launch_running:
            blocking_reasons.append("launch_still_running")
        if not branch:
            blocking_reasons.append("missing_branch")
        elif not self._ref_exists(branch):
            blocking_reasons.append("missing_branch_ref")
        if not self._ref_exists(base_ref):
            blocking_reasons.append("missing_base_ref")
        if self._current_branch() != base_ref:
            blocking_reasons.append("current_branch_not_base_ref")
        if not self._tracked_worktree_is_clean():
            blocking_reasons.append("tracked_worktree_not_clean")
        if not pr_ready_present:
            blocking_reasons.append("missing_pr_ready_report")
        if ahead_behind is None:
            blocking_reasons.append("missing_ahead_behind")
        else:
            if ahead_behind["base_only"] != 0:
                blocking_reasons.append("base_ref_ahead_of_task_branch")
            if ahead_behind["branch_only"] <= 0:
                blocking_reasons.append("task_branch_has_no_new_commits")
        if closeout_policy != "auto" and not allow_implementation:
            blocking_reasons.append("task_class_not_low_risk")

        return {
            "task_id": task_id,
            "title": str(task_card.get("name") or task_id),
            "task_class": task_class,
            "cli_hint": cli_hint,
            "base_ref": base_ref,
            "current_branch": self._current_branch(),
            "runtime_status": str(runtime.get("status") or "missing"),
            "branch": branch or None,
            "job_id": runtime.get("job_id"),
            "worktree": runtime.get("worktree"),
            "report_path": str(report_path) if report_path else None,
            "report_exists": report_exists,
            "pr_ready_present": pr_ready_present,
            "artifacts": artifacts,
            "launch_running": launch_running,
            "closeout_policy": closeout_policy,
            "allow_implementation": allow_implementation,
            "ahead_behind": ahead_behind,
            "eligible": not blocking_reasons,
            "blocking_reasons": blocking_reasons,
        }

    def auto_closeout_task(
        self,
        task_id: str,
        *,
        base_ref: str = "main",
        allow_implementation: bool = False,
    ) -> Dict[str, object]:
        from dimcause.utils.git import run_git

        summary = self.summarize_task_closeout(
            task_id,
            base_ref=base_ref,
            allow_implementation=allow_implementation,
        )
        blocking_reasons = cast(List[str], summary.get("blocking_reasons", []))
        if blocking_reasons:
            raise RuntimeError("task closeout blocked: " + ", ".join(blocking_reasons))

        branch = str(summary["branch"])
        code, _, err = run_git("merge", "--ff-only", branch, cwd=self.root)
        if code != 0:
            raise RuntimeError(f"ff-only merge failed: {err or branch}")

        head_code, head_out, head_err = run_git("rev-parse", "HEAD", cwd=self.root)
        if head_code != 0 or not head_out.strip():
            raise RuntimeError(f"failed to resolve merged HEAD: {head_err or 'unknown error'}")
        merged_commit = head_out.strip()
        now = datetime.now().isoformat()

        runtime = self.get_task_runtime(task_id) or {}
        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            runtime_tasks = state.setdefault("tasks", {})
            existing = runtime_tasks.get(task_id)
            if not isinstance(existing, dict):
                existing = dict(runtime)
                runtime_tasks[task_id] = existing
            existing.update(
                {
                    "closeout_status": "merged",
                    "closeout_base_ref": base_ref,
                    "closeout_branch": branch,
                    "closeout_commit": merged_commit,
                    "closeout_at": now,
                    "updated_at": now,
                }
            )
            self._save_runtime_state(state)
            self.update_task_board_entry(
                task_id=task_id,
                title=str(summary.get("title") or task_id),
                owner=str(existing.get("job_id", "scheduler")),
                branch=str(existing.get("branch") or branch),
                worktree=str(existing.get("worktree") or self.root),
                status="merged",
                blocked_by="-",
                pr_ready="yes",
            )

        job_dir_value = runtime.get("job_dir")
        if isinstance(job_dir_value, str) and job_dir_value.strip():
            job_dir = Path(job_dir_value)
            if job_dir.exists():
                closeout_body = "\n".join(
                    [
                        f"- task: {task_id}",
                        f"- base_ref: {base_ref}",
                        f"- merged_branch: {branch}",
                        f"- merged_commit: {merged_commit}",
                        f"- closed_at: {now}",
                    ]
                )
                self._write_text(job_dir / "closeout.md", closeout_body)

        return {
            **summary,
            "closeout_status": "merged",
            "merged_commit": merged_commit,
            "closed_at": now,
        }

    def record_task_started(
        self,
        task_id: str,
        job_id: str,
        context_file: Path,
        task_packet_file: Optional[Path] = None,
        task_board_file: Optional[Path] = None,
        job_dir: Optional[Path] = None,
        branch: Optional[str] = None,
        worktree: Optional[str] = None,
        session_dir: Optional[Path] = None,
        session_file: Optional[Path] = None,
        session_readme: Optional[Path] = None,
        durable_session_file: Optional[Path] = None,
        session_preflight_script: Optional[Path] = None,
        session_launch_script: Optional[Path] = None,
        session_codex_run_script: Optional[Path] = None,
        session_codex_output_file: Optional[Path] = None,
        session_launch_command: Optional[str] = None,
        session_launch_pid: Optional[int] = None,
        session_launch_log: Optional[Path] = None,
    ) -> Dict:
        with with_lock("scheduler-runtime-state", timeout=5):
            now = datetime.now().isoformat()
            state = self.load_runtime_state()
            resolved_branch = branch or self._current_branch()
            resolved_worktree = worktree or str(self.root)
            state.setdefault("tasks", {})[task_id] = {
                "status": "running",
                "job_id": job_id,
                "branch": resolved_branch,
                "context_file": str(context_file),
                "task_packet_file": str(task_packet_file) if task_packet_file else None,
                "task_board_file": str(task_board_file) if task_board_file else None,
                "job_dir": str(job_dir) if job_dir else None,
                "worktree": resolved_worktree,
                "session_dir": str(session_dir) if session_dir else None,
                "session_file": str(session_file) if session_file else None,
                "session_readme": str(session_readme) if session_readme else None,
                "durable_session_file": str(durable_session_file) if durable_session_file else None,
                "session_preflight_script": str(session_preflight_script)
                if session_preflight_script
                else None,
                "session_launch_script": str(session_launch_script)
                if session_launch_script
                else None,
                "session_codex_run_script": str(session_codex_run_script)
                if session_codex_run_script
                else None,
                "session_codex_output_file": str(session_codex_output_file)
                if session_codex_output_file
                else None,
                "session_launch_command": session_launch_command,
                "session_launch_pid": session_launch_pid,
                "session_launch_log": str(session_launch_log) if session_launch_log else None,
                "started_at": now,
                "updated_at": now,
            }
            self._save_runtime_state(state)
            self.update_task_board_entry(
                task_id=task_id,
                title=self._get_task_title(task_id),
                owner=job_id,
                branch=resolved_branch,
                worktree=resolved_worktree,
                status="running",
                blocked_by="-",
                pr_ready="no",
            )
            return state["tasks"][task_id]

    def _task_evidence_meta(
        self,
        *,
        task_id: str,
        job_id: str,
        job_dir: Path,
        context_file: Optional[Path],
        runtime_task_packet: Optional[Path],
        evidence_task_packet: Optional[Path],
        status: str,
        branch: Optional[str] = None,
        worktree: Optional[str] = None,
        report_path: Optional[Path] = None,
        pr_ready_path: Optional[Path] = None,
        failure_reason: Optional[str] = None,
        session_dir: Optional[Path] = None,
        session_file: Optional[Path] = None,
        session_readme: Optional[Path] = None,
        durable_session_file: Optional[Path] = None,
        session_preflight_script: Optional[Path] = None,
        session_launch_script: Optional[Path] = None,
        session_codex_run_script: Optional[Path] = None,
        session_codex_output_file: Optional[Path] = None,
        session_launch_command: Optional[str] = None,
        session_launch_pid: Optional[int] = None,
        session_launch_log: Optional[Path] = None,
        session_stop_signal: Optional[str] = None,
        session_stop_requested_at: Optional[str] = None,
        session_stop_reason: Optional[str] = None,
        session_reconciled_at: Optional[str] = None,
        session_reconcile_reason: Optional[str] = None,
    ) -> Dict[str, object]:
        return {
            "task_id": task_id,
            "job_id": job_id,
            "job_dir": str(job_dir),
            "status": status,
            "branch": branch or self._current_branch(),
            "worktree": worktree or str(self.root),
            "task_name": self._get_task_title(task_id),
            "context_file": str(context_file) if context_file else None,
            "runtime_task_packet": str(runtime_task_packet) if runtime_task_packet else None,
            "evidence_task_packet": str(evidence_task_packet) if evidence_task_packet else None,
            "task_start_event_id": self._task_event_id(job_id, "start"),
            "task_result_event_id": self._task_event_id(job_id, "result"),
            "report_path": str(report_path) if report_path else None,
            "pr_ready_path": str(pr_ready_path) if pr_ready_path else None,
            "failure_reason": failure_reason,
            "session_dir": str(session_dir) if session_dir else None,
            "session_file": str(session_file) if session_file else None,
            "session_readme": str(session_readme) if session_readme else None,
            "durable_session_file": str(durable_session_file) if durable_session_file else None,
            "session_preflight_script": str(session_preflight_script)
            if session_preflight_script
            else None,
            "session_launch_script": str(session_launch_script) if session_launch_script else None,
            "session_codex_run_script": str(session_codex_run_script)
            if session_codex_run_script
            else None,
            "session_codex_output_file": str(session_codex_output_file)
            if session_codex_output_file
            else None,
            "session_launch_command": session_launch_command,
            "session_launch_pid": session_launch_pid,
            "session_launch_log": str(session_launch_log) if session_launch_log else None,
            "session_stop_signal": session_stop_signal,
            "session_stop_requested_at": session_stop_requested_at,
            "session_stop_reason": session_stop_reason,
            "session_reconciled_at": session_reconciled_at,
            "session_reconcile_reason": session_reconcile_reason,
            "updated_at": datetime.now().isoformat(),
        }

    def _write_json(self, path: Path, payload: Dict[str, object]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def _write_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _task_event_id(job_id: str, phase: str) -> str:
        sanitized = re.sub(r"[^\w.-]+", "-", job_id.strip().lower()).strip("-")
        return f"scheduler-task-{phase}-{sanitized}"

    def _task_related_files(self, task_id: str) -> List[str]:
        task_card = self.load_task_card(task_id)
        related_files = task_card.get("related_files") if isinstance(task_card, dict) else []
        if isinstance(related_files, list):
            return [str(item) for item in related_files if isinstance(item, str)]
        return []

    def _scheduler_data_dir(self) -> Path:
        try:
            from dimcause.utils.config import get_config

            data_dir = Path(get_config().data_dir).expanduser()
        except Exception:
            data_dir = Path.home() / ".dimcause"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def _sync_task_event_to_knowledge(self, event, markdown_path: Path) -> bool:
        try:
            from dimcause.core.event_index import EventIndex
            from dimcause.storage.vector_store import VectorStore

            data_dir = self._scheduler_data_dir()
            index = EventIndex(db_path=str(data_dir / "index.db"))
            added = index.add(event, str(markdown_path))
            if not added:
                logger.warning("Scheduler task event index add failed: %s", event.id)
                return False

            try:
                vector_store = VectorStore(
                    persist_dir=str(data_dir / "chroma"),
                    db_path=str(data_dir / "index.db"),
                )
                vector_store.add(event)
                vector_store.release_model()
            except Exception as exc:
                logger.warning("Scheduler task event vector sync failed: %s", exc)
            return True
        except Exception as exc:
            logger.warning("Scheduler task event sync failed: %s", exc)
            return False

    def _link_task_lifecycle_events(
        self,
        *,
        source_event_id: str,
        target_event_id: str,
        outcome: str,
    ) -> None:
        try:
            from dimcause.core.event_index import EventIndex
            from dimcause.reasoning.causal import CausalLink

            data_dir = self._scheduler_data_dir()
            index = EventIndex(db_path=str(data_dir / "index.db"))
            index.upsert_links(
                source_event_id,
                [
                    CausalLink(
                        source=source_event_id,
                        target=target_event_id,
                        relation="leads_to",
                        weight=1.0,
                        metadata={"scheduler_task": True, "outcome": outcome},
                    )
                ],
            )
        except Exception as exc:
            logger.warning("Scheduler task lifecycle link sync failed: %s", exc)

    def _build_task_start_event(
        self,
        *,
        task_id: str,
        job_id: str,
        context_file: Path,
        task_packet_file: Path,
        branch: Optional[str],
        worktree: Optional[str],
        evidence_dir: Path,
    ):
        from dimcause.core.models import Event, EventType, SourceType

        title = self._get_task_title(task_id)
        packet_body = task_packet_file.read_text(encoding="utf-8")
        return Event(
            id=self._task_event_id(job_id, "start"),
            type=EventType.TASK,
            timestamp=datetime.now(),
            summary=f"Task Packet: {task_id} - {title}",
            content=packet_body,
            related_files=self._task_related_files(task_id),
            related_event_ids=[],
            source=SourceType.MANUAL,
            metadata={
                "job_id": job_id,
                "task_id": task_id,
                "status": "running",
                "artifact_type": "task_start",
                "generated_by": "scheduler",
                "branch": branch or self._current_branch(),
                "worktree": worktree or str(self.root),
                "evidence_dir": str(evidence_dir),
                "context_file": str(context_file),
                "task_packet_runtime_path": str(task_packet_file),
            },
        )

    def _build_task_result_event(
        self,
        *,
        task_id: str,
        job_id: str,
        status: str,
        body: str,
        evidence_dir: Path,
        report_path: Optional[Path] = None,
        pr_ready_path: Optional[Path] = None,
        failure_reason: Optional[str] = None,
    ):
        from dimcause.core.models import Event, EventType, SourceType

        title = self._get_task_title(task_id)
        return Event(
            id=self._task_event_id(job_id, "result"),
            type=EventType.TASK,
            timestamp=datetime.now(),
            summary=f"Task Result: {task_id} - {title}",
            content=body,
            related_files=self._task_related_files(task_id),
            related_event_ids=[self._task_event_id(job_id, "start")],
            source=SourceType.MANUAL,
            metadata={
                "job_id": job_id,
                "task_id": task_id,
                "status": status,
                "artifact_type": "task_result",
                "generated_by": "scheduler",
                "evidence_dir": str(evidence_dir),
                "report_path": str(report_path) if report_path else None,
                "pr_ready_path": str(pr_ready_path) if pr_ready_path else None,
                "failure_reason": failure_reason,
            },
        )

    def persist_task_evidence_on_start(
        self,
        *,
        task_id: str,
        job_id: str,
        context_file: Path,
        task_packet_file: Path,
        branch: Optional[str] = None,
        worktree: Optional[str] = None,
        job_dir: Optional[Path] = None,
        session_dir: Optional[Path] = None,
        session_file: Optional[Path] = None,
        session_readme: Optional[Path] = None,
        durable_session_file: Optional[Path] = None,
        session_preflight_script: Optional[Path] = None,
        session_launch_script: Optional[Path] = None,
        session_codex_run_script: Optional[Path] = None,
        session_codex_output_file: Optional[Path] = None,
        session_launch_command: Optional[str] = None,
        session_launch_pid: Optional[int] = None,
        session_launch_log: Optional[Path] = None,
    ) -> Path:
        job_dir = job_dir or self.resolve_job_dir(job_id)
        durable_task_packet = job_dir / "task-packet.md"
        start_event = self._build_task_start_event(
            task_id=task_id,
            job_id=job_id,
            context_file=context_file,
            task_packet_file=task_packet_file,
            branch=branch,
            worktree=worktree,
            evidence_dir=job_dir,
        )
        self._write_text(durable_task_packet, start_event.to_markdown())
        self._sync_task_event_to_knowledge(start_event, durable_task_packet)
        meta = self._task_evidence_meta(
            task_id=task_id,
            job_id=job_id,
            job_dir=job_dir,
            context_file=context_file,
            runtime_task_packet=task_packet_file,
            evidence_task_packet=durable_task_packet,
            status="running",
            branch=branch,
            worktree=worktree,
            session_dir=session_dir,
            session_file=session_file,
            session_readme=session_readme,
            durable_session_file=durable_session_file,
            session_preflight_script=session_preflight_script,
            session_launch_script=session_launch_script,
            session_codex_run_script=session_codex_run_script,
            session_codex_output_file=session_codex_output_file,
            session_launch_command=session_launch_command,
            session_launch_pid=session_launch_pid,
            session_launch_log=session_launch_log,
        )
        self._write_json(job_dir / "meta.json", meta)
        return job_dir

    def materialize_task_session_bundle(
        self,
        *,
        task_id: str,
        job_id: str,
        job_dir: Path,
        context_file: Path,
        task_packet_file: Path,
        branch: str,
        worktree: str,
        work_class: str = "product",
    ) -> Dict[str, Path]:
        session_dir = Path(worktree) / ".agent" / "sessions" / job_id
        session_dir.mkdir(parents=True, exist_ok=True)

        context_copy = self._write_text(
            session_dir / "context.md",
            context_file.read_text(encoding="utf-8"),
        )
        task_packet_copy = self._write_text(
            session_dir / "task-packet.md",
            task_packet_file.read_text(encoding="utf-8"),
        )
        session_readme = self._write_text(
            session_dir / "README.md",
            "\n".join(
                [
                    f"# Scheduler Session: {task_id}",
                    "",
                    "- purpose: isolated execution bundle for a single task run",
                    f"- task_id: {task_id}",
                    f"- job_id: {job_id}",
                    f"- branch: {branch}",
                    f"- worktree: {worktree}",
                    f"- work_class: {work_class}",
                    "",
                    "## Files",
                    "- `context.md`: prompt/context snapshot for the assigned agent",
                    "- `task-packet.md`: scope, allowed files, required checks, PR_READY contract",
                    "- `session.json`: machine-readable session manifest",
                    "- `preflight.sh`: explicit pre-write / pre-launch guard",
                    "- `codex-run.sh`: invoke Codex CLI against the frozen `context.md`",
                    "",
                    "## Why This Exists",
                    "- keep each assigned agent in an isolated execution space",
                    "- leave a durable, replayable record of what the agent received",
                    "- make handoff, audit, retrieval, and causal reconstruction possible",
                    "",
                    "## Canonical Evidence",
                    f"- durable evidence dir: {job_dir}",
                    f"- durable session manifest: {job_dir / 'session.json'}",
                    f"- preflight script: {session_dir / 'preflight.sh'}",
                    f"- launch script: {session_dir / 'launch.sh'}",
                    f"- codex run script: {session_dir / 'codex-run.sh'}",
                ]
            ),
        )
        preflight_script = self._write_text(
            session_dir / "preflight.sh",
            "\n".join(
                [
                    "#!/usr/bin/env zsh",
                    "set -euo pipefail",
                    f'SESSION_DIR="{session_dir}"',
                    f'WORKTREE="{worktree}"',
                    f'BRANCH="{branch}"',
                    f'WORK_CLASS="{work_class}"',
                    f'REPO_ROOT="{self.root}"',
                    'PYTHON_BIN="$REPO_ROOT/.venv/bin/python"',
                    'PREFLIGHT_SCRIPT="$WORKTREE/scripts/preflight_guard.py"',
                    'TASK_PACKET="$SESSION_DIR/task-packet.md"',
                    'if [[ ! -x "$PYTHON_BIN" ]]; then',
                    '  echo "Missing repo virtualenv python: $PYTHON_BIN" >&2',
                    "  exit 1",
                    "fi",
                    'if [[ ! -f "$PREFLIGHT_SCRIPT" ]]; then',
                    '  echo "Missing preflight guard: $PREFLIGHT_SCRIPT" >&2',
                    "  exit 1",
                    "fi",
                    'exec "$PYTHON_BIN" "$PREFLIGHT_SCRIPT" --work-class "$WORK_CLASS" --branch "$BRANCH" --task-packet "$TASK_PACKET"',
                ]
            ),
        )
        preflight_script.chmod(0o755)
        codex_output_file = session_dir / "codex-last.md"
        codex_run_script = self._write_text(
            session_dir / "codex-run.sh",
            "\n".join(
                [
                    "#!/usr/bin/env zsh",
                    "set -euo pipefail",
                    f'SESSION_DIR="{session_dir}"',
                    f'WORKTREE="{worktree}"',
                    f'OUTPUT_FILE="{codex_output_file}"',
                    'if [[ ! -f "$SESSION_DIR/context.md" ]]; then',
                    '  echo "Missing scheduler context: $SESSION_DIR/context.md" >&2',
                    "  exit 1",
                    "fi",
                    'exec codex exec --full-auto -C "$WORKTREE" -o "$OUTPUT_FILE" "$@" - < "$SESSION_DIR/context.md"',
                ]
            ),
        )
        codex_run_script.chmod(0o755)
        launch_script = self._write_text(
            session_dir / "launch.sh",
            "\n".join(
                [
                    "#!/usr/bin/env zsh",
                    "set -euo pipefail",
                    f'SESSION_DIR="{session_dir}"',
                    f'WORKTREE="{worktree}"',
                    f'PREFLIGHT_SCRIPT="{preflight_script}"',
                    "if [[ $# -eq 0 ]]; then",
                    '  echo "Scheduler session bundle ready."',
                    '  echo "worktree: $WORKTREE"',
                    '  echo "session_dir: $SESSION_DIR"',
                    '  echo "task_packet: $SESSION_DIR/task-packet.md"',
                    '  echo "context: $SESSION_DIR/context.md"',
                    '  echo "preflight: $PREFLIGHT_SCRIPT"',
                    '  echo "codex_run: $SESSION_DIR/codex-run.sh"',
                    '  echo "usage: launch.sh <command> [args...]"',
                    '  echo "example: launch.sh $SESSION_DIR/codex-run.sh"',
                    "  exit 0",
                    "fi",
                    'cd "$WORKTREE"',
                    '"$PREFLIGHT_SCRIPT"',
                    'exec "$@"',
                ]
            ),
        )
        launch_script.chmod(0o755)
        session_payload: Dict[str, object] = {
            "task_id": task_id,
            "job_id": job_id,
            "branch": branch,
            "worktree": worktree,
            "work_class": work_class,
            "repo_root": str(self.root),
            "job_dir": str(job_dir),
            "context_file": str(context_copy),
            "task_packet_file": str(task_packet_copy),
            "preflight_script": str(preflight_script),
            "launch_script": str(launch_script),
            "codex_run_script": str(codex_run_script),
            "codex_output_file": str(codex_output_file),
            "generated_at": datetime.now().isoformat(),
        }
        session_file = self._write_json(session_dir / "session.json", session_payload)
        durable_session_file = self._write_json(job_dir / "session.json", session_payload)
        return {
            "session_dir": session_dir,
            "session_file": session_file,
            "session_readme": session_readme,
            "durable_session_file": durable_session_file,
            "session_preflight_script": preflight_script,
            "session_launch_script": launch_script,
            "session_codex_run_script": codex_run_script,
            "session_codex_output_file": codex_output_file,
        }

    def update_task_session_launch(
        self,
        *,
        session_file: Optional[Path],
        durable_session_file: Optional[Path],
        command: str,
        pid: int,
        log_file: Path,
    ) -> None:
        for path in (session_file, durable_session_file):
            if path is None or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            payload.update(
                {
                    "launch_command": command,
                    "launch_pid": pid,
                    "launch_log": str(log_file),
                    "launch_updated_at": datetime.now().isoformat(),
                }
            )
            self._write_json(path, payload)

    def update_task_evidence_launch(
        self,
        *,
        job_dir: Path,
        command: str,
        pid: int,
        log_file: Path,
    ) -> None:
        meta_path = job_dir / "meta.json"
        payload: Dict[str, object]
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except Exception:
            payload = {}
        payload.update(
            {
                "session_launch_command": command,
                "session_launch_pid": pid,
                "session_launch_log": str(log_file),
                "updated_at": datetime.now().isoformat(),
            }
        )
        self._write_json(meta_path, payload)

    def update_task_session_stop(
        self,
        *,
        session_file: Optional[Path],
        durable_session_file: Optional[Path],
        stop_signal: str,
        requested_at: str,
        reason: str,
    ) -> None:
        for path in (session_file, durable_session_file):
            if path is None or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            payload.update(
                {
                    "stop_signal": stop_signal,
                    "stop_requested_at": requested_at,
                    "stop_reason": reason,
                    "stop_updated_at": datetime.now().isoformat(),
                }
            )
            self._write_json(path, payload)

    def update_task_evidence_stop(
        self,
        *,
        job_dir: Path,
        stop_signal: str,
        requested_at: str,
        reason: str,
    ) -> None:
        meta_path = job_dir / "meta.json"
        payload: Dict[str, object]
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except Exception:
            payload = {}
        payload.update(
            {
                "session_stop_signal": stop_signal,
                "session_stop_requested_at": requested_at,
                "session_stop_reason": reason,
                "updated_at": datetime.now().isoformat(),
            }
        )
        self._write_json(meta_path, payload)

    def update_task_session_resume(
        self,
        *,
        session_file: Optional[Path],
        durable_session_file: Optional[Path],
        resumed_at: str,
    ) -> None:
        for path in (session_file, durable_session_file):
            if path is None or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            payload["resume_count"] = int(payload.get("resume_count") or 0) + 1
            payload["last_resumed_at"] = resumed_at
            self._write_json(path, payload)

    def update_task_evidence_resume(
        self,
        *,
        job_dir: Path,
        resumed_at: str,
    ) -> None:
        meta_path = job_dir / "meta.json"
        payload: Dict[str, object]
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except Exception:
            payload = {}
        payload["resume_count"] = int(payload.get("resume_count") or 0) + 1
        payload["last_resumed_at"] = resumed_at
        payload["updated_at"] = resumed_at
        self._write_json(meta_path, payload)

    def update_task_session_reconcile(
        self,
        *,
        session_file: Optional[Path],
        durable_session_file: Optional[Path],
        reconciled_at: str,
        reason: str,
    ) -> None:
        for path in (session_file, durable_session_file):
            if path is None or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            payload.update(
                {
                    "reconciled_at": reconciled_at,
                    "reconcile_reason": reason,
                    "reconcile_updated_at": datetime.now().isoformat(),
                }
            )
            self._write_json(path, payload)

    def update_task_evidence_reconcile(
        self,
        *,
        job_dir: Path,
        reconciled_at: str,
        reason: str,
    ) -> None:
        meta_path = job_dir / "meta.json"
        payload: Dict[str, object]
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except Exception:
            payload = {}
        payload.update(
            {
                "session_reconciled_at": reconciled_at,
                "session_reconcile_reason": reason,
                "updated_at": datetime.now().isoformat(),
            }
        )
        self._write_json(meta_path, payload)

    def _write_job_end_artifact(
        self,
        *,
        task_id: str,
        job_id: str,
        job_dir: Path,
        status: str,
        result_body: str,
        report_path: Optional[Path] = None,
        pr_ready_path: Optional[Path] = None,
        failure_reason: Optional[str] = None,
    ) -> Path:
        result_event = self._build_task_result_event(
            task_id=task_id,
            job_id=job_id,
            status=status,
            body=result_body,
            evidence_dir=job_dir,
            report_path=report_path,
            pr_ready_path=pr_ready_path,
            failure_reason=failure_reason,
        )
        job_end_path = self._write_text(job_dir / "job-end.md", result_event.to_markdown())
        self._sync_task_event_to_knowledge(result_event, job_end_path)
        self._link_task_lifecycle_events(
            source_event_id=self._task_event_id(job_id, "start"),
            target_event_id=result_event.id,
            outcome=status,
        )
        return job_end_path

    def persist_task_evidence_on_completion(
        self,
        *,
        task_id: str,
        pr_ready_report: str,
        report_path: Optional[Path] = None,
    ) -> Optional[Path]:
        runtime = self.get_task_runtime(task_id)
        if not runtime:
            return None

        job_id = str(runtime.get("job_id") or f"{task_id.strip().lower()}-auto")
        raw_job_dir = runtime.get("job_dir")
        job_dir = (
            Path(raw_job_dir)
            if isinstance(raw_job_dir, str) and raw_job_dir
            else self.resolve_job_dir(job_id)
        )
        durable_report = None
        if report_path and report_path.exists():
            durable_report = job_dir / "check-report.json"
            shutil.copyfile(report_path, durable_report)
        pr_ready_path = self._write_text(job_dir / "pr-ready.md", pr_ready_report)
        self._write_job_end_artifact(
            task_id=task_id,
            job_id=job_id,
            job_dir=job_dir,
            status="done",
            result_body="\n".join(
                [
                    "- verification: pass",
                    f"- pr_ready: {pr_ready_path.name}",
                    f"- check_report: {durable_report.name if durable_report else '-'}",
                ]
            ),
            report_path=durable_report,
            pr_ready_path=pr_ready_path,
        )
        meta_path = job_dir / "meta.json"
        existing_meta: Dict[str, object] = {}
        if meta_path.exists():
            try:
                loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing_meta = loaded
            except Exception:
                existing_meta = {}
        updated_meta = {
            **existing_meta,
            **self._task_evidence_meta(
                task_id=task_id,
                job_id=job_id,
                job_dir=job_dir,
                context_file=Path(str(runtime["context_file"]))
                if runtime.get("context_file")
                else None,
                runtime_task_packet=Path(str(runtime["task_packet_file"]))
                if runtime.get("task_packet_file")
                else None,
                evidence_task_packet=job_dir / "task-packet.md"
                if (job_dir / "task-packet.md").exists()
                else None,
                status="done",
                branch=str(runtime.get("branch") or self._current_branch()),
                worktree=str(runtime.get("worktree") or self.root),
                report_path=durable_report,
                pr_ready_path=pr_ready_path,
                session_dir=Path(str(runtime["session_dir"]))
                if runtime.get("session_dir")
                else None,
                session_file=Path(str(runtime["session_file"]))
                if runtime.get("session_file")
                else None,
                session_readme=Path(str(runtime["session_readme"]))
                if runtime.get("session_readme")
                else None,
                durable_session_file=Path(str(runtime["durable_session_file"]))
                if runtime.get("durable_session_file")
                else None,
                session_launch_script=Path(str(runtime["session_launch_script"]))
                if runtime.get("session_launch_script")
                else None,
                session_launch_command=str(runtime.get("session_launch_command"))
                if runtime.get("session_launch_command")
                else None,
                session_launch_pid=int(runtime["session_launch_pid"])
                if runtime.get("session_launch_pid") is not None
                else None,
                session_launch_log=Path(str(runtime["session_launch_log"]))
                if runtime.get("session_launch_log")
                else None,
                session_reconciled_at=str(runtime.get("session_reconciled_at"))
                if runtime.get("session_reconciled_at")
                else None,
                session_reconcile_reason=str(runtime.get("session_reconcile_reason"))
                if runtime.get("session_reconcile_reason")
                else None,
            ),
            "completed_at": datetime.now().isoformat(),
        }
        self._write_json(meta_path, updated_meta)

        try:
            from dimcause.utils.state import record_job_end

            record_job_end()
        except Exception:
            pass

        return job_dir

    def persist_task_evidence_on_failure(self, *, task_id: str, reason: str) -> Optional[Path]:
        runtime = self.get_task_runtime(task_id)
        if not runtime:
            return None

        job_id = str(runtime.get("job_id") or f"{task_id.strip().lower()}-auto")
        raw_job_dir = runtime.get("job_dir")
        job_dir = (
            Path(raw_job_dir)
            if isinstance(raw_job_dir, str) and raw_job_dir
            else self.resolve_job_dir(job_id)
        )
        self._write_job_end_artifact(
            task_id=task_id,
            job_id=job_id,
            job_dir=job_dir,
            status="failed",
            result_body="\n".join(
                [
                    "- verification: failed",
                    f"- reason: {reason}",
                ]
            ),
            failure_reason=reason,
        )
        meta_path = job_dir / "meta.json"
        existing_meta: Dict[str, object] = {}
        if meta_path.exists():
            try:
                loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing_meta = loaded
            except Exception:
                existing_meta = {}
        updated_meta = {
            **existing_meta,
            **self._task_evidence_meta(
                task_id=task_id,
                job_id=job_id,
                job_dir=job_dir,
                context_file=Path(str(runtime["context_file"]))
                if runtime.get("context_file")
                else None,
                runtime_task_packet=Path(str(runtime["task_packet_file"]))
                if runtime.get("task_packet_file")
                else None,
                evidence_task_packet=job_dir / "task-packet.md"
                if (job_dir / "task-packet.md").exists()
                else None,
                status="failed",
                branch=str(runtime.get("branch") or self._current_branch()),
                worktree=str(runtime.get("worktree") or self.root),
                failure_reason=reason,
                session_dir=Path(str(runtime["session_dir"]))
                if runtime.get("session_dir")
                else None,
                session_file=Path(str(runtime["session_file"]))
                if runtime.get("session_file")
                else None,
                session_readme=Path(str(runtime["session_readme"]))
                if runtime.get("session_readme")
                else None,
                durable_session_file=Path(str(runtime["durable_session_file"]))
                if runtime.get("durable_session_file")
                else None,
                session_launch_script=Path(str(runtime["session_launch_script"]))
                if runtime.get("session_launch_script")
                else None,
                session_launch_command=str(runtime.get("session_launch_command"))
                if runtime.get("session_launch_command")
                else None,
                session_launch_pid=int(runtime["session_launch_pid"])
                if runtime.get("session_launch_pid") is not None
                else None,
                session_launch_log=Path(str(runtime["session_launch_log"]))
                if runtime.get("session_launch_log")
                else None,
                session_stop_signal=str(runtime.get("session_stop_signal"))
                if runtime.get("session_stop_signal")
                else None,
                session_stop_requested_at=str(runtime.get("session_stop_requested_at"))
                if runtime.get("session_stop_requested_at")
                else None,
                session_stop_reason=str(runtime.get("session_stop_reason"))
                if runtime.get("session_stop_reason")
                else None,
                session_reconciled_at=str(runtime.get("session_reconciled_at"))
                if runtime.get("session_reconciled_at")
                else None,
                session_reconcile_reason=str(runtime.get("session_reconcile_reason"))
                if runtime.get("session_reconcile_reason")
                else None,
            ),
            "failed_at": datetime.now().isoformat(),
        }
        self._write_json(meta_path, updated_meta)

        try:
            from dimcause.utils.state import record_job_end

            record_job_end()
        except Exception:
            pass

        return job_dir

    def record_task_completed(
        self,
        task_id: str,
        pr_ready_report: str,
        report_path: Optional[Path] = None,
    ) -> Dict:
        with with_lock("scheduler-runtime-state", timeout=5):
            now = datetime.now().isoformat()
            state = self.load_runtime_state()
            previous = state.setdefault("tasks", {}).get(task_id, {})
            branch = str(previous.get("branch") or self._current_branch())
            state["tasks"][task_id] = {
                **previous,
                "status": "done",
                "branch": branch,
                "completed_at": now,
                "updated_at": now,
                "pr_ready_report": pr_ready_report,
                "report_path": str(report_path) if report_path else None,
            }
            self._save_runtime_state(state)
            self.persist_task_evidence_on_completion(
                task_id=task_id,
                pr_ready_report=pr_ready_report,
                report_path=report_path,
            )
            self.update_task_board_entry(
                task_id=task_id,
                title=self._get_task_title(task_id),
                owner=str(previous.get("job_id", "scheduler")),
                branch=branch,
                worktree=str(previous.get("worktree", self.root)),
                status="done",
                blocked_by="-",
                pr_ready="yes",
            )
            return state["tasks"][task_id]

    def record_task_failed(self, task_id: str, reason: str) -> Dict:
        with with_lock("scheduler-runtime-state", timeout=5):
            now = datetime.now().isoformat()
            state = self.load_runtime_state()
            previous = state.setdefault("tasks", {}).get(task_id, {})
            branch = str(previous.get("branch") or self._current_branch())
            state["tasks"][task_id] = {
                **previous,
                "status": "failed",
                "branch": branch,
                "failed_at": now,
                "failure_reason": reason,
                "updated_at": now,
            }
            self._save_runtime_state(state)
            self.persist_task_evidence_on_failure(task_id=task_id, reason=reason)
            self.update_task_board_entry(
                task_id=task_id,
                title=self._get_task_title(task_id),
                owner=str(previous.get("job_id", "scheduler")),
                branch=branch,
                worktree=str(previous.get("worktree", self.root)),
                status="failed",
                blocked_by=reason,
                pr_ready="no",
            )
            return state["tasks"][task_id]

    def stop_task_launch(
        self,
        task_id: str,
        *,
        reason: str,
        force: bool = False,
    ) -> Dict[str, object]:
        runtime = self.get_task_runtime(task_id)
        if not runtime:
            raise RuntimeError(f"No runtime state found for task: {task_id}")
        if runtime.get("status") != "running":
            raise RuntimeError(f"Task is not running: {task_id}")

        stop_signal = signal.SIGKILL if force else signal.SIGTERM
        stop_signal_name = "SIGKILL" if force else "SIGTERM"
        pid_value = runtime.get("session_launch_pid")
        requested_at = datetime.now().isoformat()
        signal_sent = False
        launch_was_running = self._is_process_alive(pid_value)

        if launch_was_running:
            os.kill(int(pid_value), stop_signal)
            signal_sent = True
            time.sleep(0.2)
            if self._is_process_alive(pid_value):
                raise RuntimeError(
                    f"Launch PID still running after {stop_signal_name}; retry with --force"
                )

        session_file = Path(str(runtime["session_file"])) if runtime.get("session_file") else None
        durable_session_file = (
            Path(str(runtime["durable_session_file"]))
            if runtime.get("durable_session_file")
            else None
        )
        job_dir = Path(str(runtime["job_dir"])) if runtime.get("job_dir") else None
        launch_log = (
            Path(str(runtime["session_launch_log"])) if runtime.get("session_launch_log") else None
        )

        if launch_log is not None:
            launch_log.parent.mkdir(parents=True, exist_ok=True)
            with launch_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"# stop requested at: {requested_at} signal={stop_signal_name} reason={reason}\n"
                )

        if session_file or durable_session_file:
            self.update_task_session_stop(
                session_file=session_file,
                durable_session_file=durable_session_file,
                stop_signal=stop_signal_name,
                requested_at=requested_at,
                reason=reason,
            )
        if job_dir is not None:
            self.update_task_evidence_stop(
                job_dir=job_dir,
                stop_signal=stop_signal_name,
                requested_at=requested_at,
                reason=reason,
            )

        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            previous = state.setdefault("tasks", {}).get(task_id, {})
            if isinstance(previous, dict):
                previous["session_stop_signal"] = stop_signal_name
                previous["session_stop_requested_at"] = requested_at
                previous["session_stop_reason"] = reason
                previous["updated_at"] = requested_at
                self._save_runtime_state(state)

        failed_runtime = self.record_task_failed(task_id, reason)
        return {
            "task_id": task_id,
            "status": failed_runtime.get("status"),
            "failure_reason": failed_runtime.get("failure_reason"),
            "stop_signal": stop_signal_name,
            "signal_sent": signal_sent,
            "launch_was_running": launch_was_running,
            "launch_pid": pid_value,
        }

    def resume_task_launch(
        self,
        task_id: str,
        *,
        launch: Optional[str] = None,
    ) -> Dict[str, object]:
        runtime = self.get_task_runtime(task_id)
        if not runtime:
            raise RuntimeError(f"No runtime state found for task: {task_id}")

        status = str(runtime.get("status") or "")
        if status == "done":
            raise RuntimeError(f"Task already completed: {task_id}")

        current_pid = runtime.get("session_launch_pid")
        if self._is_process_alive(current_pid):
            raise RuntimeError(f"Task launch already running: {task_id}")

        launch_script = (
            Path(str(runtime["session_launch_script"]))
            if runtime.get("session_launch_script")
            else None
        )
        if launch_script is None or not launch_script.exists():
            raise RuntimeError(f"Missing launch script for task: {task_id}")

        worktree = Path(str(runtime["worktree"])) if runtime.get("worktree") else None
        if worktree is None or not worktree.exists():
            raise RuntimeError(f"Missing worktree for task: {task_id}")

        command = (
            launch.strip() if launch else str(runtime.get("session_launch_command") or "").strip()
        )
        if not command:
            raise RuntimeError(f"No launch command recorded for task: {task_id}")

        session_dir = (
            Path(str(runtime["session_dir"]))
            if runtime.get("session_dir")
            else launch_script.parent
        )
        launch_log = (
            Path(str(runtime["session_launch_log"]))
            if runtime.get("session_launch_log")
            else session_dir / "launch.log"
        )
        resumed_at = datetime.now().isoformat()

        launch_log.parent.mkdir(parents=True, exist_ok=True)
        with launch_log.open("a", encoding="utf-8") as handle:
            handle.write(f"# resumed at: {resumed_at} command: {command}\n")
        with launch_log.open("a", encoding="utf-8") as handle:
            process = subprocess.Popen(
                [str(launch_script), *shlex.split(command)],
                cwd=self.root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )

        session_file = Path(str(runtime["session_file"])) if runtime.get("session_file") else None
        durable_session_file = (
            Path(str(runtime["durable_session_file"]))
            if runtime.get("durable_session_file")
            else None
        )
        job_dir = Path(str(runtime["job_dir"])) if runtime.get("job_dir") else None

        self.update_task_session_launch(
            session_file=session_file,
            durable_session_file=durable_session_file,
            command=command,
            pid=process.pid,
            log_file=launch_log,
        )
        self.update_task_session_resume(
            session_file=session_file,
            durable_session_file=durable_session_file,
            resumed_at=resumed_at,
        )
        if job_dir is not None:
            self.update_task_evidence_launch(
                job_dir=job_dir,
                command=command,
                pid=process.pid,
                log_file=launch_log,
            )
            self.update_task_evidence_resume(
                job_dir=job_dir,
                resumed_at=resumed_at,
            )

        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            previous = state.setdefault("tasks", {}).get(task_id, {})
            if not isinstance(previous, dict):
                previous = {}
                state.setdefault("tasks", {})[task_id] = previous

            resume_count = int(previous.get("resume_count") or 0) + 1
            previous.update(
                {
                    "status": "running",
                    "updated_at": resumed_at,
                    "resumed_at": resumed_at,
                    "resume_count": resume_count,
                    "session_launch_command": command,
                    "session_launch_pid": process.pid,
                    "session_launch_log": str(launch_log),
                    "failure_reason": None,
                }
            )
            self._save_runtime_state(state)
            self.update_task_board_entry(
                task_id=task_id,
                title=self._get_task_title(task_id),
                owner=str(previous.get("job_id", "scheduler")),
                branch=str(previous.get("branch") or self._current_branch()),
                worktree=str(previous.get("worktree") or self.root),
                status="running",
                blocked_by="-",
                pr_ready="no",
            )

        return {
            "task_id": task_id,
            "status": "running",
            "launch_command": command,
            "launch_pid": process.pid,
            "launch_log": str(launch_log),
            "resumed_at": resumed_at,
            "resume_count": resume_count,
        }

    def reconcile_running_tasks(
        self,
        *,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        summary: Dict[str, object] = {
            "dry_run": dry_run,
            "reconciled": 0,
            "skipped": 0,
            "tasks": [],
        }
        tasks_output = cast(List[Dict[str, object]], summary["tasks"])
        candidates: List[Dict[str, object]] = []
        active_job = self.get_active_job()
        active_job_id = active_job[0] if active_job else None

        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            runtime_tasks = state.setdefault("tasks", {})
            if not isinstance(runtime_tasks, dict):
                runtime_tasks = {}
                state["tasks"] = runtime_tasks

            for task_id in sorted(runtime_tasks):
                runtime = runtime_tasks.get(task_id)
                if not isinstance(runtime, dict):
                    continue
                if str(runtime.get("status") or "") != "running":
                    continue

                job_id = str(runtime.get("job_id") or "")
                pid_value = runtime.get("session_launch_pid")
                result: Dict[str, object] = {
                    "task_id": task_id,
                    "status": "running",
                    "job_id": job_id or None,
                    "launch_pid": pid_value,
                    "action": "skipped",
                    "reason": "",
                }

                if pid_value is None:
                    result["reason"] = (
                        "active_job_without_launch_pid_kept"
                        if active_job_id and job_id == active_job_id
                        else "running_without_launch_pid_review_required"
                    )
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                if self._is_process_alive(pid_value):
                    result["reason"] = "launch_pid_running"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                result["action"] = "would_reconcile" if dry_run else "reconciled"
                result["reason"] = "launch_pid_not_running"
                summary["reconciled"] = int(summary["reconciled"]) + 1
                tasks_output.append(result)

                if not dry_run:
                    candidates.append(
                        {
                            "task_id": task_id,
                            "job_dir": runtime.get("job_dir"),
                            "session_file": runtime.get("session_file"),
                            "durable_session_file": runtime.get("durable_session_file"),
                            "session_launch_log": runtime.get("session_launch_log"),
                            "launch_pid": pid_value,
                        }
                    )

        if dry_run:
            return summary

        for candidate in candidates:
            task_id = str(candidate["task_id"])
            launch_pid = candidate.get("launch_pid")
            reconciled_at = datetime.now().isoformat()
            reconcile_reason = "launch_pid_not_running"
            failure_reason = f"launch exited before scheduler completion (pid {launch_pid})"

            with with_lock("scheduler-runtime-state", timeout=5):
                state = self.load_runtime_state()
                runtime = state.setdefault("tasks", {}).get(task_id)
                if not isinstance(runtime, dict) or str(runtime.get("status") or "") != "running":
                    continue
                runtime["session_reconciled_at"] = reconciled_at
                runtime["session_reconcile_reason"] = reconcile_reason
                runtime["updated_at"] = reconciled_at
                self._save_runtime_state(state)

            session_file = (
                Path(str(candidate["session_file"])) if candidate.get("session_file") else None
            )
            durable_session_file = (
                Path(str(candidate["durable_session_file"]))
                if candidate.get("durable_session_file")
                else None
            )
            job_dir = Path(str(candidate["job_dir"])) if candidate.get("job_dir") else None
            launch_log = (
                Path(str(candidate["session_launch_log"]))
                if candidate.get("session_launch_log")
                else None
            )

            if launch_log is not None:
                launch_log.parent.mkdir(parents=True, exist_ok=True)
                with launch_log.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "# reconciled at: "
                        f"{reconciled_at} reason={reconcile_reason} failure={failure_reason}\n"
                    )

            if session_file or durable_session_file:
                self.update_task_session_reconcile(
                    session_file=session_file,
                    durable_session_file=durable_session_file,
                    reconciled_at=reconciled_at,
                    reason=reconcile_reason,
                )
            if job_dir is not None:
                self.update_task_evidence_reconcile(
                    job_dir=job_dir,
                    reconciled_at=reconciled_at,
                    reason=reconcile_reason,
                )

            self.record_task_failed(task_id, failure_reason)

        return summary

    @staticmethod
    def _is_process_alive(pid: object) -> bool:
        if pid is None:
            return False
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except (TypeError, ValueError, OSError):
            return False
        return True

    @staticmethod
    def _archive_runtime_workspace_fields(runtime: Dict[str, Any]) -> None:
        for field_name in (
            "worktree",
            "session_dir",
            "session_file",
            "session_readme",
            "session_launch_script",
            "session_launch_pid",
            "session_launch_log",
        ):
            value = runtime.get(field_name)
            if value is not None:
                runtime[f"archived_{field_name}"] = value
            runtime[field_name] = None

    @staticmethod
    def _is_scheduler_tmp_worktree(worktree: Path) -> bool:
        root = (Path("/tmp") / "dimc-worktrees").resolve()
        candidate = worktree.expanduser().resolve(strict=False)
        return candidate == root or root in candidate.parents

    def _is_branch_merged_into(self, branch: str, base_ref: str) -> bool:
        from dimcause.utils.git import run_git

        normalized = branch.strip()
        if not normalized:
            return False

        code, _, _ = run_git("rev-parse", "--verify", "--quiet", normalized, cwd=self.root)
        if code != 0:
            return False

        code, _, _ = run_git("merge-base", "--is-ancestor", normalized, base_ref, cwd=self.root)
        return code == 0

    def cleanup_task_workspaces(
        self,
        *,
        include_failed: bool = False,
        dry_run: bool = False,
        base_ref: str = "main",
    ) -> Dict[str, object]:
        from dimcause.utils.git import run_git

        now = datetime.now().isoformat()
        summary: Dict[str, object] = {
            "dry_run": dry_run,
            "include_failed": include_failed,
            "base_ref": base_ref,
            "cleaned": 0,
            "skipped": 0,
            "errors": 0,
            "tasks": [],
        }
        tasks_output = cast(List[Dict[str, object]], summary["tasks"])
        active_job = self.get_active_job()
        active_job_id = active_job[0] if active_job else None

        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            runtime_tasks = state.setdefault("tasks", {})
            if not isinstance(runtime_tasks, dict):
                runtime_tasks = {}
                state["tasks"] = runtime_tasks

            for task_id in sorted(runtime_tasks):
                runtime = runtime_tasks.get(task_id)
                if not isinstance(runtime, dict):
                    continue

                status = str(runtime.get("status") or "")
                if status not in ("done", "failed"):
                    continue

                result: Dict[str, object] = {
                    "task_id": task_id,
                    "status": status,
                    "job_id": runtime.get("job_id"),
                    "branch": runtime.get("branch"),
                    "worktree": runtime.get("worktree"),
                    "action": "skipped",
                    "reason": "",
                    "worktree_removed": False,
                    "branch_deleted": False,
                }

                def _mark_skipped(
                    *,
                    reason: str,
                    result_ref: Dict[str, object],
                    runtime_ref: Dict[str, Any],
                ) -> None:
                    result_ref["action"] = "skipped"
                    result_ref["reason"] = reason
                    summary["skipped"] = int(summary["skipped"]) + 1
                    if not dry_run:
                        runtime_ref["cleanup_status"] = "skipped"
                        runtime_ref["cleanup_reason"] = reason
                        runtime_ref["cleanup_at"] = now
                        runtime_ref["cleanup_base_ref"] = base_ref

                if status == "failed" and not include_failed:
                    _mark_skipped(
                        reason="failed_task_kept_for_review",
                        result_ref=result,
                        runtime_ref=runtime,
                    )
                    tasks_output.append(result)
                    continue

                if active_job_id and runtime.get("job_id") == active_job_id:
                    _mark_skipped(
                        reason="active_job_running", result_ref=result, runtime_ref=runtime
                    )
                    tasks_output.append(result)
                    continue

                if self._is_process_alive(runtime.get("session_launch_pid")):
                    _mark_skipped(
                        reason="launch_pid_running", result_ref=result, runtime_ref=runtime
                    )
                    tasks_output.append(result)
                    continue

                raw_worktree = runtime.get("worktree")
                if not isinstance(raw_worktree, str) or not raw_worktree.strip():
                    _mark_skipped(reason="missing_worktree", result_ref=result, runtime_ref=runtime)
                    tasks_output.append(result)
                    continue

                worktree_path = Path(raw_worktree)
                if not self._is_scheduler_tmp_worktree(worktree_path):
                    _mark_skipped(
                        reason="worktree_not_in_tmp_pool",
                        result_ref=result,
                        runtime_ref=runtime,
                    )
                    tasks_output.append(result)
                    continue

                branch_name = str(runtime.get("branch") or "").strip()
                branch_merged = self._is_branch_merged_into(branch_name, base_ref)
                branch_is_current = branch_name == self._current_branch()

                if worktree_path.exists():
                    if dry_run:
                        result["worktree_removed"] = True
                    else:
                        code, _, err = run_git(
                            "worktree", "remove", str(worktree_path), cwd=self.root
                        )
                        if code != 0:
                            _mark_skipped(
                                reason=f"worktree_remove_failed: {err or 'unknown error'}",
                                result_ref=result,
                                runtime_ref=runtime,
                            )
                            summary["errors"] = int(summary["errors"]) + 1
                            tasks_output.append(result)
                            continue
                        result["worktree_removed"] = True

                if branch_name and branch_merged and not branch_is_current:
                    if dry_run:
                        result["branch_deleted"] = True
                    else:
                        code, _, err = run_git("branch", "-D", branch_name, cwd=self.root)
                        if code == 0:
                            result["branch_deleted"] = True
                        else:
                            result["reason"] = f"branch_delete_failed: {err or 'unknown error'}"
                            summary["errors"] = int(summary["errors"]) + 1

                result["action"] = "would_clean" if dry_run else "cleaned"
                if not result["reason"]:
                    if branch_is_current and branch_name:
                        result["reason"] = "branch_is_current_kept"
                    elif branch_name and not branch_merged:
                        result["reason"] = "branch_not_merged_kept"
                    else:
                        result["reason"] = "ok"
                summary["cleaned"] = int(summary["cleaned"]) + 1

                if not dry_run:
                    self._archive_runtime_workspace_fields(runtime)
                    runtime["cleanup_status"] = "cleaned"
                    runtime["cleanup_reason"] = str(result["reason"])
                    runtime["cleanup_at"] = now
                    runtime["cleanup_base_ref"] = base_ref
                    runtime["cleanup_branch_deleted"] = bool(result["branch_deleted"])
                    runtime["cleanup_worktree_removed"] = bool(result["worktree_removed"])

                tasks_output.append(result)

            if not dry_run:
                self._save_runtime_state(state)

        return summary

    @staticmethod
    def _parse_runtime_timestamp(value: object) -> Optional[datetime]:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    def _runtime_retention_timestamp(self, runtime: Dict[str, Any]) -> Optional[datetime]:
        for key in ("cleanup_at", "completed_at", "failed_at", "updated_at", "started_at"):
            parsed = self._parse_runtime_timestamp(runtime.get(key))
            if parsed is not None:
                return parsed
        return None

    def prune_runtime_tasks(
        self,
        *,
        include_failed: bool = False,
        retain_days: int = 14,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        if retain_days < 0:
            raise ValueError(f"retain_days must be >= 0, got {retain_days}")

        now = datetime.now()
        summary: Dict[str, object] = {
            "dry_run": dry_run,
            "include_failed": include_failed,
            "retain_days": retain_days,
            "pruned": 0,
            "skipped": 0,
            "tasks": [],
        }
        tasks_output = cast(List[Dict[str, object]], summary["tasks"])
        active_job = self.get_active_job()
        active_job_id = active_job[0] if active_job else None

        with with_lock("scheduler-runtime-state", timeout=5):
            state = self.load_runtime_state()
            runtime_tasks = state.setdefault("tasks", {})
            if not isinstance(runtime_tasks, dict):
                runtime_tasks = {}
                state["tasks"] = runtime_tasks

            for task_id in sorted(runtime_tasks):
                runtime = runtime_tasks.get(task_id)
                if not isinstance(runtime, dict):
                    continue

                status = str(runtime.get("status") or "")
                if status not in ("done", "failed"):
                    continue

                result: Dict[str, object] = {
                    "task_id": task_id,
                    "status": status,
                    "job_id": runtime.get("job_id"),
                    "action": "skipped",
                    "reason": "",
                }

                if status == "failed" and not include_failed:
                    result["reason"] = "failed_task_kept_for_review"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                if active_job_id and runtime.get("job_id") == active_job_id:
                    result["reason"] = "active_job_running"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                if self._is_process_alive(runtime.get("session_launch_pid")):
                    result["reason"] = "launch_pid_running"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                if runtime.get("worktree") or runtime.get("session_dir"):
                    result["reason"] = "workspace_not_cleaned"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                timestamp = self._runtime_retention_timestamp(runtime)
                if timestamp is None:
                    result["reason"] = "missing_retention_timestamp"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                age_days = (now - timestamp).total_seconds() / 86400.0
                result["age_days"] = round(age_days, 3)
                if age_days < retain_days:
                    result["reason"] = "within_retention_window"
                    summary["skipped"] = int(summary["skipped"]) + 1
                    tasks_output.append(result)
                    continue

                result["action"] = "would_prune" if dry_run else "pruned"
                result["reason"] = "ok"
                summary["pruned"] = int(summary["pruned"]) + 1
                tasks_output.append(result)

                if not dry_run:
                    runtime_tasks.pop(task_id, None)

            if not dry_run:
                self._save_runtime_state(state)

        return summary

    def _apply_runtime_state(self) -> None:
        runtime_tasks = self.load_runtime_state().get("tasks", {})
        if not isinstance(runtime_tasks, dict):
            return

        for task_id, runtime in runtime_tasks.items():
            if not isinstance(runtime, dict):
                continue
            task = self._state.get("tasks", {}).get(task_id)
            if task is None:
                continue
            runtime_status = runtime.get("status")
            if runtime_status == "running":
                task.status = TaskStatus.IN_PROGRESS
            elif runtime_status == "done":
                task.status = TaskStatus.DONE
            elif runtime_status == "failed":
                task.status = TaskStatus.BLOCKED

    def register_job(self, job_name: str, interval: float, func: Callable) -> None:
        """
        注册一个定时任务

        Args:
            job_name: 任务名称
            interval: 执行间隔（秒）
            func: 要执行的函数
        """
        if interval <= 0:
            raise ValueError(f"interval 必须大于 0，当前值: {interval}")

        self._jobs[job_name] = Job(
            name=job_name,
            interval=interval,
            func=func,
        )
        logger.info(f"Registered job: {job_name} (interval={interval}s)")

    def start(self) -> None:
        """启动调度循环（后台线程）"""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        if not self._jobs:
            logger.warning("No jobs registered, nothing to run")
            return

        self._running = True
        self._stop_event.clear()

        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="Orchestrator-Scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        logger.info(f"Orchestrator started with {len(self._jobs)} job(s)")

    def stop(self) -> None:
        """停止调度循环"""
        if not self._running:
            logger.warning("Orchestrator not running")
            return

        logger.info("Stopping Orchestrator...")
        self._running = False
        self._stop_event.set()

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5.0)

        logger.info("Orchestrator stopped")

    def _scheduler_loop(self) -> None:
        """调度循环（在后台线程中运行）"""
        logger.info("Scheduler loop started")

        while self._running and not self._stop_event.is_set():
            now = time.time()

            for job in self._jobs.values():
                if not self._running or self._stop_event.is_set():
                    break

                next_run = (job.last_run or 0) + job.interval

                if now >= next_run:
                    self._execute_job(job)

            time.sleep(0.1)

        logger.info("Scheduler loop exited")

    def _execute_job(self, job: Job) -> None:
        """执行单个任务（带异常捕获）"""
        job.last_run = time.time()
        job.run_count += 1

        try:
            logger.info(f"Executing job: {job.name}")
            job.func()
            logger.info(f"Job completed: {job.name}")
        except Exception as e:
            job.error_count += 1
            logger.error(f"Job failed: {job.name}, error: {e}")

    def get_jobs_status(self) -> Dict:
        """获取所有任务的状态"""
        return {
            name: {
                "interval": job.interval,
                "run_count": job.run_count,
                "error_count": job.error_count,
                "last_run": job.last_run,
            }
            for name, job in self._jobs.items()
        }

    def get_active_job(self):
        """读取当前活跃 job（如果存在）。"""
        from dimcause.utils.state import get_active_job

        return get_active_job()

    @property
    def is_running(self) -> bool:
        """检查调度器是否在运行"""
        return self._running

    def load_state(self) -> Dict:
        """
        加载项目状态

        读取顺序 (信息流优先级):
        1. docs/STATUS.md → V6.1 任务表
        2. agent-tasks/*.md → 任务细节 (覆盖 STATUS)

        Returns: 合并后的状态字典
        """
        status_path = self._resolve_status_file()
        if status_path is None:
            return {"error": f"Status file not found: {self.root / self.STATUS_FILE}"}

        # 解析 STATUS 文件
        content = status_path.read_text(encoding="utf-8")
        self._state = self._parse_status_file(content)

        # 加载 agent-tasks (覆盖 STATUS)
        self._load_agent_tasks()
        self._apply_runtime_state()

        return self._state

    def _parse_status_file(self, content: str) -> Dict:
        """Parse the modern V6 progress table from docs/STATUS.md."""
        return {"tasks": self._parse_modern_status_tasks(content)}

    def _parse_modern_status_tasks(self, content: str) -> Dict[str, TaskInfo]:
        tasks: Dict[str, TaskInfo] = {}
        for task_id, name, status_text in extract_modern_progress_rows(content):
            status = self._parse_status_text(status_text)
            if status is None:
                continue
            normalized_id = self._normalize_task_id(task_id)
            tasks[normalized_id] = TaskInfo(
                id=normalized_id,
                name=name.strip(),
                cli=self._infer_cli(normalized_id, name),
                status=status,
                priority=self._infer_priority(normalized_id, name),
            )
        return tasks

    def _resolve_status_file(self) -> Optional[Path]:
        return resolve_status_file(self.root)

    def _parse_status_text(self, status_text: str) -> Optional[TaskStatus]:
        normalized = status_text.strip()
        if any(token in normalized for token in ("🔄", "In Progress", "部分完成", "进行中")):
            return TaskStatus.IN_PROGRESS
        if any(token in normalized for token in ("⛔", "Blocked", "阻塞")):
            return TaskStatus.BLOCKED
        if any(
            token in normalized
            for token in ("✅", "Done", "已完成", "已验证", "已实现", "基本修复")
        ):
            return TaskStatus.DONE
        if any(token in normalized for token in ("📋", "📝", "待", "已创建", "Planned")):
            return TaskStatus.PLANNED
        return None

    def _normalize_task_id(self, task_id: str) -> str:
        return re.sub(r"\s+", " ", task_id.strip())

    def _infer_cli(self, task_id: str, name: str) -> str:
        haystack = f"{task_id} {name}".lower()
        if "search" in haystack or "检索" in haystack:
            return "dimc search"
        if "why" in haystack or "解释" in haystack or "因果" in haystack:
            return "dimc why"
        if "scheduler" in haystack or "调度" in haystack:
            return "dimc scheduler"
        if "detect" in haystack or "探测" in haystack:
            return "dimc detect"
        if "mcp" in haystack:
            return "dimc mcp"
        return "-"

    def _infer_priority(
        self, task_id: str, name: str, raw_priority: Optional[str] = None
    ) -> TaskPriority:
        if raw_priority:
            normalized = raw_priority.strip().upper()
            if normalized in TaskPriority.__members__:
                return TaskPriority[normalized]

        haystack = f"{task_id} {name}".upper()
        for label in ("P0", "P1", "P2", "P3"):
            if re.search(rf"(?<![A-Z0-9]){label}(?![A-Z0-9])", haystack):
                return TaskPriority[label]

        return TaskPriority.P2

    def _load_agent_tasks(self):
        """加载 agent-tasks 目录下的任务卡"""
        agent_tasks_dir = self.root / self.AGENT_TASKS_DIR
        if not agent_tasks_dir.exists():
            return

        for md_file in agent_tasks_dir.glob("agent_*.md"):
            # 从文件名提取任务 token (e.g., agent_d1_... -> d1)
            match = re.match(r"agent_([^_]+)_", md_file.name)
            if match:
                token = self._task_id_file_token(match.group(1))
                content = md_file.read_text(encoding="utf-8")
                frontmatter = self._parse_frontmatter(content)
                matched_task_id = None
                for task_id in self._state.get("tasks", {}):
                    if self._task_id_file_token(task_id) == token:
                        matched_task_id = task_id
                        break
                if matched_task_id in self._state.get("tasks", {}):
                    self._state["tasks"][matched_task_id].agent_task_path = md_file
                    priority = self._infer_priority(
                        matched_task_id,
                        self._state["tasks"][matched_task_id].name,
                        frontmatter.get("priority"),
                    )
                    self._state["tasks"][matched_task_id].priority = priority
                    continue

                standalone_task_id = self._extract_task_id_from_task_card(
                    content, fallback=match.group(1)
                )
                standalone_title = self._extract_title(content)
                standalone_status = self._parse_task_card_status(frontmatter.get("status"))
                standalone_priority = self._infer_priority(
                    standalone_task_id,
                    standalone_title,
                    frontmatter.get("priority"),
                )
                self._state.setdefault("tasks", {})[standalone_task_id] = TaskInfo(
                    id=standalone_task_id,
                    name=standalone_title,
                    cli=self._infer_cli(standalone_task_id, standalone_title),
                    status=standalone_status,
                    priority=standalone_priority,
                    agent_task_path=md_file,
                )

    def _extract_task_id_from_task_card(self, content: str, *, fallback: str) -> str:
        match = re.search(r"^#\s+Agent Task\s+([^:]+):", content, re.MULTILINE)
        if match:
            return self._normalize_task_id(match.group(1))
        return self._normalize_task_id(fallback)

    def _parse_task_card_status(self, raw_status: Optional[str]) -> TaskStatus:
        normalized = (raw_status or "").strip()
        if not normalized:
            return TaskStatus.PLANNED

        lowered = normalized.lower()
        if lowered in {"open", "todo", "planned"}:
            return TaskStatus.PLANNED
        if lowered in {"in progress", "running", "doing"}:
            return TaskStatus.IN_PROGRESS
        if lowered in {"done", "completed", "closed"}:
            return TaskStatus.DONE
        if lowered in {"blocked", "failed"}:
            return TaskStatus.BLOCKED

        parsed = self._parse_status_text(normalized)
        return parsed or TaskStatus.PLANNED

    @staticmethod
    def _format_task_board_cell(value: str) -> str:
        sanitized = value.replace("|", "/").replace("\n", " ").strip()
        return sanitized or "-"

    def _default_task_board_lines(self) -> List[str]:
        return [
            "# Task Board",
            "",
            "| task_id | title | owner | branch | worktree | status | blocked_by | pr_ready |",
            "|:---|:---|:---|:---|:---|:---|:---|:---|",
        ]

    def update_task_board_entry(
        self,
        *,
        task_id: str,
        title: str,
        owner: str,
        branch: str,
        worktree: str,
        status: str,
        blocked_by: str,
        pr_ready: str,
    ) -> Path:
        path = self.task_board_path()
        rows: Dict[str, List[str]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if (
                    not line.startswith("|")
                    or line.startswith("| task_id")
                    or line.startswith("|:---")
                ):
                    continue
                columns = [part.strip() for part in line.strip().strip("|").split("|")]
                if len(columns) != 8:
                    continue
                rows[columns[0]] = columns

        rows[task_id] = [
            self._format_task_board_cell(task_id),
            self._format_task_board_cell(title),
            self._format_task_board_cell(owner),
            self._format_task_board_cell(branch),
            self._format_task_board_cell(worktree),
            self._format_task_board_cell(status),
            self._format_task_board_cell(blocked_by),
            self._format_task_board_cell(pr_ready),
        ]

        lines = self._default_task_board_lines()
        for row_task_id in sorted(rows):
            row = rows[row_task_id]
            lines.append(f"| {' | '.join(row)} |")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _infer_required_checks(self, related_files: List[str]) -> List[str]:
        test_files = [file_path for file_path in related_files if file_path.startswith("tests/")]
        checks: List[str] = []
        if test_files:
            checks.append("pytest " + " ".join(test_files) + " -q")
        checks.append("scripts/check.zsh --report-file tmp/check-report.json")
        return checks

    def _task_packet_file_name(self, task_id: str) -> str:
        sanitized = re.sub(r"[^\w.-]+", "_", task_id.strip())
        return f"{sanitized}.md"

    def materialize_task_packet(
        self,
        task_id: str,
        *,
        job_id: str,
        branch: Optional[str] = None,
        worktree: Optional[str] = None,
    ) -> Path:
        task_card = self.load_task_card(task_id)
        if "error" in task_card:
            raise FileNotFoundError(task_card["error"])

        related_files = task_card.get("related_files") or []
        required_checks = self._infer_required_checks(related_files)
        packet_path = self._task_packet_dir_path() / self._task_packet_file_name(task_id)
        packet_lines = [
            "# Task Packet",
            "",
            "## 1. Task Identity",
            f"- `task_id`: {task_card['id']}",
            f"- `title`: {task_card['name']}",
            f"- `owner`: {job_id}",
            f"- `priority`: {task_card.get('priority', 'P2')}",
            "- `status`: running",
            "- `protected_doc_override`: false",
            "- `user_approval_note`: ",
            "- `design_change_reason`: ",
            "",
            "## 2. Goal",
            task_card.get("description", "").strip() or "- 由 scheduler 合成的任务目标",
            "",
            "## 3. Out Of Scope",
            "- 不得扩大任务范围。",
            "- 不得顺手修改受保护设计文档。",
            "",
            "## 4. Allowed Files",
            "```text",
        ]

        if related_files:
            packet_lines.extend(f"- {file_path}" for file_path in related_files)
        else:
            packet_lines.append("- (to be narrowed before launch)")

        packet_lines.extend(
            [
                "```",
                "",
                "## 5. Forbidden Files",
                "```text",
                "- docs/PROJECT_ARCHITECTURE.md",
                "- docs/STORAGE_ARCHITECTURE.md",
                "- docs/V6.0/DEV_ONTOLOGY.md",
                "```",
                "",
                "## 6. Protected Design Doc Override",
                "- `protected_doc_override`: false",
                "- `user_approval_note`: ",
                "- `design_change_reason`: ",
                "",
                "## 7. Required Checks",
                "```bash",
                *required_checks,
                "```",
                "",
                "## 8. Delivery Contract",
                task_card.get("deliverables", "").strip()
                or "- 代码/文档变更 + 验证结果 + [PR_READY]",
                "",
                "## 9. Branch / Worktree / Session",
                f"- branch: {branch or self._current_branch()}",
                f"- worktree: {worktree or str(self.root)}",
                f"- session: {job_id}",
                "",
                "## 10. Acceptance Criteria",
                task_card.get("acceptance_criteria", "").strip() or "- 变更范围与任务目标一致",
                "",
                "## 11. Related Files",
            ]
        )

        if related_files:
            packet_lines.extend(f"- {file_path}" for file_path in related_files)
        else:
            packet_lines.append("- (none inferred)")

        packet_lines.extend(
            [
                "",
                "## 12. Internal Agent Context Transfer",
                "- 已完成：",
                "- 未完成：",
                "- 当前卡点：",
                "- 下一步建议：",
                "",
                "## 13. PR_READY Contract",
                "- files",
                "- whitelist",
                "- protected_docs",
                "- checks",
                "- risks",
                "",
                f"_Generated by scheduler at {self._now()}_",
            ]
        )

        packet_path.write_text("\n".join(packet_lines) + "\n", encoding="utf-8")
        return packet_path

    def _get_task_title(self, task_id: str) -> str:
        if not self._state:
            self.load_state()
        normalized_id = self._normalize_task_id(task_id)
        task = self._state.get("tasks", {}).get(normalized_id)
        if task:
            return task.name
        task_card = self.load_task_card(normalized_id)
        if "error" not in task_card:
            title = str(task_card.get("name", "")).strip()
            if title:
                return title
        return normalized_id

    def discover_tasks(self, scope: str = "v5.2") -> List[TaskInfo]:
        """
        发现当前可执行任务

        返回按优先级排序的任务列表 (P0 优先)
        """
        if not self._state:
            self.load_state()

        tasks = list(self._state.get("tasks", {}).values())

        # 过滤: 只返回非 Done 的任务
        active_tasks = [t for t in tasks if t.status != TaskStatus.DONE]

        # 排序: P0 > P1 > P2, In Progress > Planned > Blocked
        def sort_key(t: TaskInfo):
            status_order = {
                TaskStatus.IN_PROGRESS: 0,
                TaskStatus.PLANNED: 1,
                TaskStatus.BLOCKED: 2,
                TaskStatus.DONE: 3,
            }
            return (t.priority.value, status_order.get(t.status, 99))

        return sorted(active_tasks, key=sort_key)

    def get_next_task(self) -> Optional[TaskInfo]:
        """获取下一个应该执行的任务"""
        tasks = self.discover_tasks()
        if not tasks:
            return None

        # 返回优先级最高且非 Blocked 的任务
        for task in tasks:
            if task.status != TaskStatus.BLOCKED:
                return task

        return None

    def plan(self) -> str:
        """
        生成任务计划

        输出格式:
        ## 📋 Dimcause Scheduler Plan

        ### 🎯 下一个任务
        - [H2] Hybrid Timeline (P0, In Progress)

        ### 📊 任务列表
        | ID | 名称 | 优先级 | 状态 |
        ...
        """
        tasks = self.discover_tasks()
        next_task = self.get_next_task()

        lines = [
            "## 📋 Dimcause Scheduler Plan",
            "",
            f"**扫描时间**: {self._now()}",
            "",
        ]

        if next_task:
            lines.extend(
                [
                    "### 🎯 下一个任务",
                    f"- **[{next_task.id}]** {next_task.name} ({next_task.priority.name}, {getattr(next_task.status, 'value', str(next_task.status))})",
                ]
            )
            if next_task.cli and next_task.cli != "-":
                lines.append(f"- CLI: `{next_task.cli}`")
            if next_task.agent_task_path:
                lines.append(f"- 任务卡: `{next_task.agent_task_path.relative_to(self.root)}`")
            lines.append("")
        else:
            lines.extend(
                [
                    "### ✅ 没有待执行任务",
                    "",
                ]
            )

        lines.extend(
            [
                "### 📊 任务列表",
                "",
                "| ID | 名称 | 优先级 | 状态 |",
                "|:---|:---|:---|:---|",
            ]
        )

        for task in tasks:
            status_icon = {
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.PLANNED: "📋",
                TaskStatus.BLOCKED: "⛔",
                TaskStatus.DONE: "✅",
            }.get(task.status, "❓")
            lines.append(
                f"| {task.id} | {task.name} | {task.priority.name} | {status_icon} {getattr(task.status, 'value', str(task.status))} |"
            )

        return "\n".join(lines)

    def _now(self) -> str:
        """返回当前时间字符串"""

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _task_id_file_token(task_id: str) -> str:
        token = re.sub(r"[^a-z0-9]+", "-", task_id.strip().lower()).strip("-")
        return token or "task"

    @staticmethod
    def _title_file_slug(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
        return slug[:48] or "task"

    @staticmethod
    def _normalize_markdown_block(text: str) -> str:
        normalized = text.strip()
        return normalized if normalized else "- 待补充"

    @staticmethod
    def _normalize_bullet_lines(items: Optional[List[str]], fallback: List[str]) -> List[str]:
        normalized = [item.strip() for item in (items or []) if item and item.strip()]
        source = normalized or fallback
        return [f"- {item}" for item in source]

    def _infer_task_card_class(
        self,
        task_id: str,
        title: str,
        goal: str,
        related_files: Optional[List[str]] = None,
    ) -> str:
        haystack = " ".join([task_id, title, goal, *(related_files or [])]).lower()
        if any(
            token in haystack
            for token in ("readme", "文档", "草案", "proposal", "index", "索引", "profile", "架构")
        ):
            return "docs"
        if any(token in haystack for token in ("pytest", "测试", "回归", "test_", "tests/")):
            return "test"
        if any(
            token in haystack
            for token in (
                "scheduler",
                "调度",
                "governance",
                "治理",
                "coordination",
                "worktree",
                "branch",
                "gate",
                "preflight",
                "pr_ready",
                "task packet",
                "自动化",
            )
        ):
            return "governance"
        return "implementation"

    def _default_task_card_sections(
        self,
        task_class: str,
        *,
        cli_hint: str,
    ) -> Dict[str, List[str]]:
        if task_class == "docs":
            return {
                "deliverables": [
                    "完成与目标直接对应的最小文档更新",
                    "统一直接相关文档中的术语、边界或入口表述",
                    "准备 `dimc scheduler complete` 所需的交付信息",
                ],
                "acceptance": [
                    "正文口径与当前正式结论一致",
                    "相关旧术语、旧引用或旧入口残留已复扫",
                    "变更范围与文档目标一致",
                ],
                "steps": [
                    "先核对当前正式口径和直接相关文档",
                    "只修改与任务直接相关的文档",
                    "完成后复扫旧术语、旧入口和旧引用",
                ],
                "out_of_scope": [
                    "不得顺手扩写无关设计文档",
                    "不得把文档任务升级成跨层重写",
                    "不得改写与本任务无关的产品结论",
                ],
            }
        if task_class == "test":
            return {
                "deliverables": [
                    "补齐与目标直接相关的最小测试或验证",
                    "覆盖本轮要保证的关键行为或回归点",
                    "准备 `dimc scheduler complete` 所需的交付信息",
                ],
                "acceptance": [
                    "新增或更新的测试能表达任务目标",
                    "至少一条直接相关的 pytest 验证通过",
                    "测试范围没有反向扩大业务改动",
                ],
                "steps": [
                    "先定位现有测试入口和缺失覆盖点",
                    "只补与本任务直接相关的测试或断言",
                    "完成后运行最小必要测试并记录结果",
                ],
                "out_of_scope": [
                    "不得借测试任务顺手扩写业务范围",
                    "不得跳过失败原因直接改大量实现",
                    "不得把局部验证升级成全仓重构",
                ],
            }
        if task_class == "governance":
            return {
                "deliverables": [
                    "完成与目标直接对应的最小治理脚本、模板或入口变更",
                    "同步直接相关的共享入口或规则说明",
                    "准备 `dimc scheduler complete` 所需的交付信息",
                ],
                "acceptance": [
                    "治理规则、入口和边界表述保持自洽",
                    f"至少一条与 `{cli_hint}` 或对应治理链路相关的验证通过"
                    if cli_hint != "-"
                    else "至少一条直接相关的验证链路通过",
                    "共享范围与本地控制范围仍然清楚",
                ],
                "steps": [
                    "先核对当前规则、入口和直接相关的治理文件",
                    "只修改与当前治理目标直接相关的文件",
                    "完成后复扫入口一致性并运行对应验证",
                ],
                "out_of_scope": [
                    "不得顺手改写产品定义或项目落地结论",
                    "不得把治理任务升级成跨模块产品重构",
                    "不得无根据扩大共享提交范围",
                ],
            }
        return {
            "deliverables": [
                "完成与目标直接对应的最小代码或文档变更",
                "运行至少一条与该任务直接相关的验证链路",
                "准备 `dimc scheduler complete` 所需的交付信息",
            ],
            "acceptance": [
                "变更范围与任务目标一致",
                "白名单文件范围可解释",
                "至少一条对应验证链路通过",
            ],
            "steps": [
                "先阅读相关文件并确认最小改动边界",
                "只修改与任务直接相关的文件",
                "完成后运行最小必要验证并准备收口信息",
            ],
            "out_of_scope": [
                "不得扩大任务范围",
                "不得顺手修改受保护设计文档",
                "不得把当前任务升级成跨模块重构",
            ],
        }

    # === V1.0 新增功能 ===

    def find_task_card(self, task_id: str) -> Optional[Path]:
        """
        查找任务卡文件

        Args:
            task_id: 任务 ID（如 "H2", "D1"）

        Returns:
            任务卡文件路径，如果不存在返回 None
        """
        agent_tasks_dir = self.root / self.AGENT_TASKS_DIR
        if not agent_tasks_dir.exists():
            return None

        token = self._task_id_file_token(task_id)

        for pattern in (f"agent_{task_id.lower()}_*.md", f"agent_{token}_*.md"):
            matches = list(agent_tasks_dir.glob(pattern))
            if matches:
                return matches[0]

        # 尝试宽松匹配: *h2*.md
        for md_file in agent_tasks_dir.glob("*.md"):
            lower_name = md_file.name.lower()
            if task_id.lower() in lower_name or token in lower_name:
                return md_file

        return None

    def materialize_agent_task_card(
        self,
        task_id: str,
        *,
        title: str,
        goal: str,
        priority: str = "P2",
        related_files: Optional[List[str]] = None,
        deliverables: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        steps: Optional[List[str]] = None,
        out_of_scope: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> Path:
        task_id = task_id.strip()
        title = title.strip()
        goal = goal.strip()
        if not task_id:
            raise ValueError("task_id 不能为空")
        if not title:
            raise ValueError("title 不能为空")
        if not goal:
            raise ValueError("goal 不能为空")

        normalized_priority = priority.strip().upper() if priority.strip() else "P2"
        if normalized_priority not in TaskPriority.__members__:
            raise ValueError(f"无效优先级: {priority}")

        agent_tasks_dir = self.root / self.AGENT_TASKS_DIR
        agent_tasks_dir.mkdir(parents=True, exist_ok=True)

        existing = self.find_task_card(task_id)
        if existing is not None and existing.exists() and not overwrite:
            raise FileExistsError(f"任务卡已存在: {existing}")

        task_token = self._task_id_file_token(task_id)
        title_slug = self._title_file_slug(title)
        card_path = existing or (agent_tasks_dir / f"agent_{task_token}_{title_slug}.md")

        cli_hint = self._infer_cli(task_id, title)
        inferred_related = (
            list(self.TASK_FILE_HINTS.get(cli_hint, [])) if cli_hint in self.TASK_FILE_HINTS else []
        )
        related = [
            item.strip() for item in (related_files or []) if item and item.strip()
        ] or inferred_related
        task_class = self._infer_task_card_class(task_id, title, goal, related)
        default_sections = self._default_task_card_sections(task_class, cli_hint=cli_hint)
        deliverable_lines = self._normalize_bullet_lines(
            deliverables,
            default_sections["deliverables"],
        )
        acceptance_lines = self._normalize_bullet_lines(
            acceptance_criteria,
            default_sections["acceptance"],
        )
        step_lines = self._normalize_bullet_lines(
            steps,
            default_sections["steps"],
        )
        out_of_scope_lines = self._normalize_bullet_lines(
            out_of_scope,
            default_sections["out_of_scope"],
        )

        frontmatter_lines = [
            "---",
            f"priority: {normalized_priority}",
            "status: Open",
            f"task_class: {task_class}",
        ]
        if cli_hint != "-":
            frontmatter_lines.append(f"cli_hint: {cli_hint}")
        if related:
            frontmatter_lines.append("related_docs:")
            frontmatter_lines.extend(f"  - {item}" for item in related)
        frontmatter_lines.append("---")

        body_lines = [
            *frontmatter_lines,
            "",
            f"# Agent Task {task_id}: {title}",
            "",
            "## 目标",
            self._normalize_markdown_block(goal),
            "",
            "## 非目标",
            *out_of_scope_lines,
            "",
            "## 交付物",
            *deliverable_lines,
            "",
            "## 验收标准",
            *acceptance_lines,
            "",
            "## Step 规划",
            *step_lines,
        ]

        if related:
            body_lines.extend(
                [
                    "",
                    "## 相关文件",
                    *[f"- `{item}`" for item in related],
                ]
            )

        body_lines.extend(["", f"_Generated by scheduler intake at {self._now()}_"])
        card_path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
        return card_path

    def _infer_goal_title(self, goal: str) -> str:
        normalized = re.sub(r"\s+", " ", goal).strip()
        if not normalized:
            raise ValueError("goal 不能为空")

        first_segment = re.split(r"[。！？!?；;\n]+", normalized, maxsplit=1)[0].strip()
        title = first_segment or normalized
        title = title.strip(" ，,、；;:：")
        if len(title) > 28:
            title = title[:28].rstrip(" ，,、；;:：")
        return title or "未命名任务"

    def _ensure_unique_task_id(self, task_id: str) -> str:
        candidate = self._normalize_task_id(task_id)
        if not self.find_task_card(candidate):
            return candidate

        suffix = 2
        while True:
            next_candidate = f"{candidate}-{suffix:02d}"
            if not self.find_task_card(next_candidate):
                return next_candidate
            suffix += 1

    def _infer_goal_task_id(self, title: str, goal: str, *, task_class: str) -> str:
        seed = f"{title} {goal}".lower()
        ascii_part = re.sub(r"[^a-z0-9]+", "-", seed).strip("-")
        if not ascii_part:
            ascii_part = {
                "docs": "docs",
                "test": "test",
                "governance": "governance",
                "implementation": "task",
            }.get(task_class, "task")
        digest = hashlib.sha1(f"{title}\n{goal}".encode("utf-8")).hexdigest()[:6]
        candidate = f"{ascii_part[:24]}-{digest}"
        return self._ensure_unique_task_id(candidate)

    def materialize_goal_task_card(
        self,
        *,
        goal: str,
        title: Optional[str] = None,
        task_id: Optional[str] = None,
        priority: str = "P2",
        related_files: Optional[List[str]] = None,
        deliverables: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        steps: Optional[List[str]] = None,
        out_of_scope: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> Dict[str, str]:
        normalized_goal = re.sub(r"\s+", " ", goal).strip()
        if not normalized_goal:
            raise ValueError("goal 不能为空")

        resolved_title = (title or "").strip() or self._infer_goal_title(normalized_goal)
        inferred_class = self._infer_task_card_class(
            task_id or "",
            resolved_title,
            normalized_goal,
            related_files,
        )
        resolved_task_id = (task_id or "").strip() or self._infer_goal_task_id(
            resolved_title,
            normalized_goal,
            task_class=inferred_class,
        )
        card_path = self.materialize_agent_task_card(
            resolved_task_id,
            title=resolved_title,
            goal=normalized_goal,
            priority=priority,
            related_files=related_files,
            deliverables=deliverables,
            acceptance_criteria=acceptance_criteria,
            steps=steps,
            out_of_scope=out_of_scope,
            overwrite=overwrite,
        )
        task_card = self.load_task_card(resolved_task_id)
        return {
            "task_id": resolved_task_id,
            "title": resolved_title,
            "card_path": str(card_path),
            "task_class": str(task_card.get("task_class") or inferred_class),
            "cli_hint": str(task_card.get("cli_hint") or "-"),
        }

    def load_task_card(self, task_id: str) -> Dict:
        """
        加载任务卡内容

        Args:
            task_id: 任务 ID（如 "H2", "D1"）

        Returns:
            任务卡的结构化数据，包含：
            - id: 任务 ID
            - name: 任务名称
            - description: 任务描述
            - priority: 优先级
            - status: 状态
            - deliverables: 交付物
            - acceptance_criteria: 验收标准
            - steps: Step 规划
            - related_files: 相关文件列表
            - raw_content: 原始内容
        """
        task_card_path = self.find_task_card(task_id)

        if not task_card_path or not task_card_path.exists():
            synthetic = self._build_synthetic_task_card(task_id)
            if synthetic:
                return synthetic
            return {
                "error": f"任务卡不存在: {task_id}",
                "suggestion": f"请创建 {self.AGENT_TASKS_DIR}/agent_{task_id.lower()}_xxx.md",
            }

        content = task_card_path.read_text(encoding="utf-8")

        # 解析 YAML frontmatter
        frontmatter = self._parse_frontmatter(content)

        # 解析各个章节
        result = {
            "id": task_id.upper(),
            "name": self._extract_title(content),
            "priority": frontmatter.get("priority", "P2"),
            "status": frontmatter.get("status", "Open"),
            "auto_closeout": frontmatter.get("auto_closeout", ""),
            "task_class": frontmatter.get("task_class", "").strip()
            or self._infer_task_card_class(
                task_id,
                self._extract_title(content),
                self._extract_section(content, ["背景", "Background", "目标", "Goal"]),
                self._extract_related_files(content),
            ),
            "cli_hint": frontmatter.get("cli_hint", "").strip()
            or self._infer_cli(task_id, self._extract_title(content)),
            "description": self._extract_section(content, ["背景", "Background", "目标", "Goal"]),
            "deliverables": self._extract_section(content, ["交付物", "Deliverables"]),
            "acceptance_criteria": self._extract_section(
                content, ["验收标准", "Acceptance Criteria"]
            ),
            "steps": self._extract_section(content, ["Step 规划", "Steps", "Implementation"]),
            "related_files": self._extract_related_files(content),
            "raw_content": content,
            "path": str(task_card_path.relative_to(self.root)),
        }

        return result

    def infer_work_class_for_task(self, task_id: str) -> str:
        task_card = self.load_task_card(task_id)
        task_class = str(task_card.get("task_class") or "").strip().lower()
        if task_class in {"docs", "governance"}:
            return "ops"
        if task_class == "test":
            return "product"
        return "product"

    def _build_synthetic_task_card(self, task_id: str) -> Optional[Dict]:
        if not self._state:
            self.load_state()

        normalized_id = self._normalize_task_id(task_id)
        task = self._state.get("tasks", {}).get(normalized_id)
        if task is None:
            return None

        related_files = self._infer_related_files_for_task(task)
        cli = task.cli if task.cli and task.cli != "-" else "dimc <command>"
        description = (
            f"该任务当前没有独立任务卡，以下上下文由 docs/STATUS.md 调度表合成。\n"
            f"- 任务: {task.name}\n"
            f"- 当前状态: {task.status.value}\n"
            f"- 建议 CLI: {cli}"
        )
        deliverables = "\n".join(
            [
                "- 完成与该任务直接相关的最小代码/文档改动",
                "- 运行相关测试或完整 `scripts/check.zsh`",
                "- 输出 `[PR_READY]` 或显式记录失败原因",
            ]
        )
        acceptance_criteria = "\n".join(
            [
                "- 变更范围与任务目标一致",
                "- 至少一条对应验证链路通过",
                "- `docs/STATUS.md` 的任务事实与代码现实不冲突",
            ]
        )
        steps = "\n".join(
            [
                "1. 先阅读相关文件，确认当前实现缺口。",
                "2. 仅修改与本任务直接相关的代码或文档。",
                "3. 运行最小必要测试，再决定是否补跑完整 gate。",
            ]
        )

        return {
            "id": normalized_id,
            "name": task.name,
            "priority": task.priority.name,
            "status": task.status.value,
            "description": description,
            "deliverables": deliverables,
            "acceptance_criteria": acceptance_criteria,
            "steps": steps,
            "related_files": related_files,
            "raw_content": "",
            "path": "docs/STATUS.md (synthetic task card)",
            "synthetic": True,
        }

    def _parse_frontmatter(self, content: str) -> Dict:
        """解析 YAML frontmatter"""
        if not content.startswith("---"):
            return {}

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}

        frontmatter = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

        return frontmatter

    def _extract_title(self, content: str) -> str:
        """提取任务标题"""
        # 匹配 # Agent Task H2: Hybrid Timeline
        match = re.search(r"^#\s+(?:Agent Task [^:]+:\s*)?(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "Unknown Task"

    def _extract_section(self, content: str, section_names: List[str]) -> str:
        """提取指定章节内容"""
        lines = content.split("\n")

        for name in section_names:
            # 查找章节开始
            start_idx = None
            for i, line in enumerate(lines):
                # 匹配 ## 章节名 或 ### 章节名（允许开头有空格）
                if re.match(rf"^\s*##\s*{re.escape(name)}", line, re.IGNORECASE):
                    start_idx = i + 1
                    break

            if start_idx is None:
                continue

            # 查找章节结束（下一个 ## 或文件结束）
            end_idx = len(lines)
            for i in range(start_idx, len(lines)):
                if re.match(r"^\s*##\s+", lines[i]):
                    end_idx = i
                    break

            # 提取内容
            section_content = "\n".join(lines[start_idx:end_idx]).strip()
            if section_content:
                return section_content

        return ""

    def _extract_related_files(self, content: str) -> List[str]:
        """提取相关文件列表"""
        files = set()

        # 从 frontmatter 的 related_docs 提取
        match = re.search(r"related_docs:\s*\n((?:\s+-\s+.+\n)+)", content)
        if match:
            for line in match.group(1).split("\n"):
                if line.strip().startswith("-"):
                    files.add(line.strip()[1:].strip())

        # 从正文中提取 src/ 和 tests/ 路径
        for path_match in re.finditer(r"`((?:src|tests)/[^`]+)`", content):
            files.add(path_match.group(1))

        return sorted(files)

    def _infer_related_files_for_task(self, task: TaskInfo) -> List[str]:
        files = list(self.TASK_FILE_HINTS.get(task.cli, []))
        name = task.name.lower()
        task_id = task.id.lower()

        if "watcher" in name or "watcher" in task_id or "探测" in name:
            files.extend(
                [
                    "src/dimcause/watchers/state_watcher.py",
                    "src/dimcause/daemon/manager.py",
                    "tests/test_state_watcher.py",
                ]
            )
        if "trace" in name or "trace" in task_id or "追踪" in name:
            files.extend(
                [
                    "src/dimcause/core/trace.py",
                    "src/dimcause/core/code_indexer.py",
                    "tests/test_trace_engine.py",
                ]
            )
        if "schema" in name or "validator" in name:
            files.extend(
                [
                    "src/dimcause/core/schema_validator.py",
                    "tests/core/test_schema_validator.py",
                ]
            )

        deduped = []
        seen = set()
        for file_path in files:
            if file_path in seen:
                continue
            seen.add(file_path)
            deduped.append(file_path)
        return deduped

    def generate_task_prompt(self, task_id: str, include_code: bool = True) -> str:
        """
        生成任务的 AI prompt

        Args:
            task_id: 任务 ID
            include_code: 是否包含代码片段

        Returns:
            格式化的 prompt 字符串，可直接复制给 AI
        """
        task_card = self.load_task_card(task_id)

        if "error" in task_card:
            return f"""
═══════════════════════════════════════════════════════════
❌ 任务卡加载失败
═══════════════════════════════════════════════════════════

错误: {task_card["error"]}
建议: {task_card.get("suggestion", "检查任务 ID 是否正确")}
"""

        # 获取相关文件的代码片段
        code_status = ""
        if include_code and task_card["related_files"]:
            code_status = self._format_code_status(task_card["related_files"])

        prompt = f"""
═══════════════════════════════════════════════════════════
Task: {task_card["id"]} - {task_card["name"]}
═══════════════════════════════════════════════════════════

## 任务目标

{task_card["description"]}

## 交付物

{task_card["deliverables"]}

## 验收标准

{task_card["acceptance_criteria"]}
"""

        if code_status:
            prompt += f"""
## 当前代码状态

{code_status}
"""

        if task_card["related_files"]:
            prompt += f"""
## 相关文件

{self._format_related_files(task_card["related_files"])}
"""

        if task_card["steps"]:
            prompt += f"""
## Step 规划

{task_card["steps"]}
"""

        prompt += f"""
═══════════════════════════════════════════════════════════
任务卡路径: {task_card["path"]}
生成时间: {self._now()}
═══════════════════════════════════════════════════════════
"""

        return prompt

    def _format_code_status(self, files: List[str]) -> str:
        """格式化代码状态（读取文件前 50 行）"""
        lines = []

        for file_path in files[:5]:  # 最多显示 5 个文件
            full_path = self.root / file_path
            if not full_path.exists():
                lines.append(f"### {file_path}\n*文件不存在*\n")
                continue

            if not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                file_lines = content.split("\n")

                # 只取前 30 行
                preview = "\n".join(file_lines[:30])
                if len(file_lines) > 30:
                    preview += f"\n... (共 {len(file_lines)} 行)"

                # 确定语言
                suffix = full_path.suffix
                lang = {".py": "python", ".md": "markdown", ".js": "javascript"}.get(suffix, "")

                lines.append(f"### {file_path}\n```{lang}\n{preview}\n```\n")

            except Exception as e:
                lines.append(f"### {file_path}\n*读取失败: {e}*\n")

        return "\n".join(lines) if lines else "*无可用代码文件*"

    def _format_related_files(self, files: List[str]) -> str:
        """格式化相关文件列表"""
        if not files:
            return "*无*"
        return "\n".join(f"- `{f}`" for f in files)

    def get_ready_tasks(self) -> List[TaskInfo]:
        """
        获取可执行任务列表（非 Blocked 且非 Done）

        用于 loop 命令
        """
        tasks = self.discover_tasks()
        return [t for t in tasks if t.status not in (TaskStatus.BLOCKED, TaskStatus.DONE)]


# CLI 入口点
def run_plan():
    """执行 mal scheduler plan"""
    orchestrator = Orchestrator()
    print(orchestrator.plan())


if __name__ == "__main__":
    run_plan()
