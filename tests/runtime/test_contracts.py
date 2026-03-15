from pathlib import Path

from dimcause.runtime.contracts import RunStatus
from dimcause.scheduler.run_bridge import scheduler_task_runtime_to_run


def test_scheduler_task_runtime_to_run_builds_minimum_contract(tmp_path):
    task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"
    task_packet.parent.mkdir(parents=True, exist_ok=True)
    task_packet.write_text("# packet", encoding="utf-8")

    launch_log = tmp_path / "sessions" / "launch.log"
    launch_log.parent.mkdir(parents=True, exist_ok=True)
    launch_log.write_text("launch", encoding="utf-8")

    runtime = {
        "status": "running",
        "job_id": "l0-调度-auto",
        "branch": "codex/task-l0-abc12345",
        "worktree": str(tmp_path / "worktrees" / "scheduler-l0"),
        "task_packet_file": str(task_packet),
        "session_launch_log": str(launch_log),
        "started_at": "2026-03-13T10:00:00",
        "updated_at": "2026-03-13T10:05:00",
        "resume_count": 2,
        "session_launch_pid": 43210,
    }

    run = scheduler_task_runtime_to_run("L0 调度", runtime, project_root=tmp_path)

    assert run.run_type == "scheduler_task_runtime"
    assert run.state.status == RunStatus.RUNNING
    assert run.state.started_at == "2026-03-13T10:00:00"
    assert run.state.updated_at == "2026-03-13T10:05:00"
    assert run.state.resume_count == 2
    assert run.workspace == str(Path(runtime["worktree"]))
    assert run.branch == "codex/task-l0-abc12345"
    assert run.metadata["scheduler_task_id"] == "L0 调度"
    assert run.metadata["job_id"] == "l0-调度-auto"
    assert {artifact.name for artifact in run.artifacts} == {
        "task_packet_file",
        "session_launch_log",
    }
    assert run.artifacts[0].path


def test_scheduler_task_runtime_to_run_maps_done_to_succeeded(tmp_path):
    runtime = {
        "status": "done",
        "updated_at": "2026-03-13T10:05:00",
        "completed_at": "2026-03-13T10:06:00",
    }

    run = scheduler_task_runtime_to_run("L0 调度", runtime, project_root=tmp_path)

    assert run.state.status == RunStatus.SUCCEEDED
    assert run.state.ended_at == "2026-03-13T10:06:00"
