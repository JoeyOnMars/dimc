from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from dimcause.runtime.contracts import Run, RunArtifact, RunState, RunStatus

TASK_RUNTIME_ARTIFACT_KINDS: dict[str, str] = {
    "context_file": "context",
    "task_packet_file": "task_packet",
    "task_board_file": "task_board",
    "job_dir": "job_dir",
    "session_dir": "session_dir",
    "session_file": "session_file",
    "session_readme": "session_readme",
    "durable_session_file": "durable_session_file",
    "session_preflight_script": "preflight_script",
    "session_launch_script": "launch_script",
    "session_launch_log": "launch_log",
}

TASK_STATUS_TO_RUN_STATUS: dict[str, RunStatus] = {
    "planned": RunStatus.PENDING,
    "running": RunStatus.RUNNING,
    "done": RunStatus.SUCCEEDED,
    "failed": RunStatus.FAILED,
    "blocked": RunStatus.FAILED,
}


def scheduler_task_runtime_to_run(
    task_id: str, runtime: Dict[str, Any], project_root: Optional[Path] = None
) -> Run:
    """将现有 scheduler task runtime 适配为最小 Run 合同。"""
    if not runtime:
        raise ValueError("runtime payload is required")

    state = RunState(
        status=_map_status(runtime.get("status")),
        started_at=_as_str(runtime.get("started_at")),
        updated_at=_as_str(runtime.get("updated_at")),
        ended_at=_resolve_ended_at(runtime),
        failure_reason=_as_str(runtime.get("failure_reason")),
        resume_count=_as_int(runtime.get("resume_count")),
        metadata=_compact_dict(
            {
                "session_launch_pid": runtime.get("session_launch_pid"),
                "session_stop_signal": runtime.get("session_stop_signal"),
            }
        ),
    )

    workspace = _resolve_workspace(runtime.get("worktree"), project_root)
    artifacts = _collect_artifacts(runtime, project_root=project_root)

    return Run(
        id=_build_run_id(task_id=task_id, runtime=runtime),
        run_type="scheduler_task_runtime",
        state=state,
        workspace=workspace,
        branch=_as_str(runtime.get("branch")),
        artifacts=artifacts,
        metadata=_compact_dict(
            {
                "scheduler_task_id": task_id,
                "scheduler_status": _as_str(runtime.get("status")),
                "job_id": _as_str(runtime.get("job_id")),
                "legacy_runtime_source": "scheduler",
            }
        ),
    )


def _map_status(raw_status: Any) -> RunStatus:
    if not isinstance(raw_status, str):
        return RunStatus.UNKNOWN
    return TASK_STATUS_TO_RUN_STATUS.get(raw_status.strip().lower(), RunStatus.UNKNOWN)


def _resolve_ended_at(runtime: Dict[str, Any]) -> Optional[str]:
    for field_name in ("completed_at", "failed_at", "session_reconciled_at"):
        value = _as_str(runtime.get(field_name))
        if value:
            return value
    return None


def _collect_artifacts(runtime: Dict[str, Any], project_root: Optional[Path]) -> list[RunArtifact]:
    artifacts: list[RunArtifact] = []
    for field_name, artifact_kind in TASK_RUNTIME_ARTIFACT_KINDS.items():
        value = runtime.get(field_name)
        if not isinstance(value, str) or not value.strip():
            continue
        resolved_path = _resolve_path(value, project_root=project_root)
        artifacts.append(
            RunArtifact(
                name=field_name,
                kind=artifact_kind,
                path=str(resolved_path),
                exists=resolved_path.exists(),
                metadata={"scheduler_field": field_name},
            )
        )
    return artifacts


def _resolve_workspace(worktree_value: Any, project_root: Optional[Path]) -> Optional[str]:
    value = _as_str(worktree_value)
    if not value:
        return None
    return str(_resolve_path(value, project_root=project_root))


def _resolve_path(raw_path: str, project_root: Optional[Path]) -> Path:
    path = Path(raw_path)
    if path.is_absolute() or project_root is None:
        return path
    return project_root / path


def _build_run_id(task_id: str, runtime: Dict[str, Any]) -> str:
    seed = "|".join(
        [
            task_id,
            _as_str(runtime.get("job_id")) or "",
            _as_str(runtime.get("started_at")) or "",
            _as_str(runtime.get("updated_at")) or "",
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"run_{digest}"


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _compact_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [])}
