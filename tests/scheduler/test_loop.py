from types import SimpleNamespace

from dimcause.scheduler.loop import SchedulerLoop
from dimcause.scheduler.orchestrator import TaskStatus


def test_run_loop_stops_when_active_job_exists(monkeypatch):
    loop = SchedulerLoop()
    run_called = {"value": False}

    monkeypatch.setattr(
        loop.orchestrator,
        "reconcile_running_tasks",
        lambda dry_run=False: {"reconciled": 0, "skipped": 0, "tasks": []},
    )
    monkeypatch.setattr(
        loop.orchestrator,
        "get_active_job",
        lambda: ("existing-job", "/tmp/existing-job"),
    )
    monkeypatch.setattr(loop.runner, "run_task", lambda *args, **kwargs: run_called.update(value=True))

    loop.run_loop(max_rounds=1, auto_continue=False, poll_interval=0.01)

    assert run_called["value"] is False


def test_run_loop_zero_rounds_means_infinite_mode_until_task_starts(monkeypatch):
    loop = SchedulerLoop()
    state = {"active_checks": 0, "run_calls": 0}
    next_task = SimpleNamespace(id="Task-052", name="Scheduler runtime", status=TaskStatus.PLANNED)

    def fake_get_active_job():
        state["active_checks"] += 1
        # First check: no active job, allow scheduler to start one.
        # Later checks: pretend the spawned job is active once, then gone.
        if state["run_calls"] == 0:
            return None
        if state["active_checks"] == 2:
            return ("task-052-auto", "/tmp/task-052-auto")
        return None

    def fake_run_task(task_id, auto_approve=False, dry_run=False, launch=None):
        state["run_calls"] += 1
        assert launch is None
        return {"job_id": "task-052-auto", "context_file": "/tmp/task-052_context.md"}

    monkeypatch.setattr(
        loop.orchestrator,
        "reconcile_running_tasks",
        lambda dry_run=False: {"reconciled": 0, "skipped": 0, "tasks": []},
    )
    monkeypatch.setattr(loop.orchestrator, "get_active_job", fake_get_active_job)
    monkeypatch.setattr(loop.orchestrator, "load_state", lambda: {"tasks": {}})
    monkeypatch.setattr(loop.orchestrator, "get_next_task", lambda: next_task if state["run_calls"] == 0 else None)
    monkeypatch.setattr(loop.runner, "run_task", fake_run_task)
    monkeypatch.setattr("dimcause.scheduler.loop.time.sleep", lambda _seconds: None)

    loop.run_loop(max_rounds=0, auto_continue=True, poll_interval=0.01)

    assert state["run_calls"] == 1


def test_run_loop_reconciles_stale_active_job_before_blocking(monkeypatch):
    loop = SchedulerLoop()
    state = {"reconcile_calls": 0, "run_calls": 0}
    next_task = SimpleNamespace(id="Task-077", name="Auto reconcile", status=TaskStatus.PLANNED)

    def fake_reconcile(dry_run=False):
        state["reconcile_calls"] += 1
        return {"reconciled": 1 if state["reconcile_calls"] == 1 else 0, "skipped": 0, "tasks": []}

    def fake_get_active_job():
        return None if state["reconcile_calls"] > 0 else ("stale-job", "/tmp/stale-job")

    def fake_run_task(task_id, auto_approve=False, dry_run=False, launch=None):
        state["run_calls"] += 1
        assert launch is None
        return {"job_id": "task-077-auto", "context_file": "/tmp/task-077_context.md"}

    monkeypatch.setattr(loop.orchestrator, "reconcile_running_tasks", fake_reconcile)
    monkeypatch.setattr(loop.orchestrator, "get_active_job", fake_get_active_job)
    monkeypatch.setattr(loop.orchestrator, "load_state", lambda: {"tasks": {}})
    monkeypatch.setattr(loop.orchestrator, "get_next_task", lambda: next_task)
    monkeypatch.setattr(loop.runner, "run_task", fake_run_task)
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: True)

    loop.run_loop(max_rounds=1, auto_continue=False, poll_interval=0.01)

    assert state["reconcile_calls"] == 1
    assert state["run_calls"] == 1


def test_wait_for_active_job_reconciles_until_stale_job_clears(monkeypatch):
    loop = SchedulerLoop()
    state = {"reconcile_calls": 0}

    def fake_reconcile(dry_run=False):
        state["reconcile_calls"] += 1
        return {"reconciled": 1 if state["reconcile_calls"] == 1 else 0, "skipped": 0, "tasks": []}

    def fake_get_active_job():
        return None if state["reconcile_calls"] > 0 else ("stale-job", "/tmp/stale-job")

    monkeypatch.setattr(loop.orchestrator, "reconcile_running_tasks", fake_reconcile)
    monkeypatch.setattr(loop.orchestrator, "get_active_job", fake_get_active_job)
    monkeypatch.setattr("dimcause.scheduler.loop.time.sleep", lambda _seconds: None)

    loop._wait_for_active_job(poll_interval=0.01)

    assert state["reconcile_calls"] == 1


def test_run_loop_forwards_launch_command_to_runner(monkeypatch):
    loop = SchedulerLoop()
    recorded = {}
    next_task = SimpleNamespace(id="Task-078", name="Loop launch", status=TaskStatus.PLANNED)

    monkeypatch.setattr(
        loop.orchestrator,
        "reconcile_running_tasks",
        lambda dry_run=False: {"reconciled": 0, "skipped": 0, "tasks": []},
    )
    monkeypatch.setattr(loop.orchestrator, "get_active_job", lambda: None)
    monkeypatch.setattr(loop.orchestrator, "load_state", lambda: {"tasks": {}})
    monkeypatch.setattr(loop.orchestrator, "get_next_task", lambda: next_task)
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *args, **kwargs: True)

    def fake_run_task(task_id, auto_approve=False, dry_run=False, launch=None):
        recorded["task_id"] = task_id
        recorded["auto_approve"] = auto_approve
        recorded["launch"] = launch
        return {"job_id": "task-078-auto", "context_file": "/tmp/task-078_context.md"}

    monkeypatch.setattr(loop.runner, "run_task", fake_run_task)

    loop.run_loop(
        max_rounds=1,
        auto_continue=False,
        poll_interval=0.01,
        launch="bash -lc echo launched",
    )

    assert recorded["task_id"] == "Task-078"
    assert recorded["auto_approve"] is True
    assert recorded["launch"] == "bash -lc echo launched"
