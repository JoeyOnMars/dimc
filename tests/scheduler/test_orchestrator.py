"""
Orchestrator 单元测试

测试后台调度功能：
1. 注册多个 mock jobs
2. 按 interval 触发 func
3. 异常隔离：一个 job 崩溃不影响其他 job 和主 loop
"""

import json
import os
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# 设置测试环境变量，防止真实 IO
os.environ["HF_HUB_OFFLINE"] = "1"

from dimcause.scheduler.orchestrator import Orchestrator


class TestOrchestratorJobRegistration:
    """测试任务注册功能"""

    def test_register_single_job(self):
        """测试注册单个任务"""
        orch = Orchestrator()

        def mock_job():
            pass

        orch.register_job("test_job", interval=1.0, func=mock_job)

        assert "test_job" in orch._jobs
        assert orch._jobs["test_job"].interval == 1.0
        assert orch._jobs["test_job"].func == mock_job

    def test_register_multiple_jobs(self):
        """测试注册多个不同任务"""
        orch = Orchestrator()

        def mock_job1():
            pass

        def mock_job2():
            pass

        orch.register_job("job1", interval=1.0, func=mock_job1)
        orch.register_job("job2", interval=2.0, func=mock_job2)

        assert len(orch._jobs) == 2
        assert "job1" in orch._jobs
        assert "job2" in orch._jobs

    def test_register_invalid_interval_raises(self):
        """测试注册负数 interval 抛出异常"""
        orch = Orchestrator()

        with pytest.raises(ValueError):
            orch.register_job("bad_job", interval=-1.0, func=lambda: None)


class TestOrchestratorExecution:
    """测试任务执行功能"""

    def test_start_triggers_job(self):
        """测试 start() 后能按 interval 触发 func"""
        orch = Orchestrator()

        call_count = {"count": 0}

        def mock_job():
            call_count["count"] += 1

        # 注册任务，interval 设为 0.1 秒
        orch.register_job("trigger_test", interval=0.1, func=mock_job)

        # 启动调度器
        orch.start()

        # 等待足够时间确保任务被执行（至少执行 2 次）
        time.sleep(0.35)

        # 停止调度器
        orch.stop()

        # 验证任务被触发至少 2 次
        assert call_count["count"] >= 2, f"Expected >=2, got {call_count['count']}"

    def test_multiple_jobs_both_execute(self):
        """测试多个任务都能执行"""
        orch = Orchestrator()

        count1 = {"count": 0}
        count2 = {"count": 0}

        def job1():
            count1["count"] += 1

        def job2():
            count2["count"] += 1

        orch.register_job("multi1", interval=0.1, func=job1)
        orch.register_job("multi2", interval=0.1, func=job2)

        orch.start()
        time.sleep(0.35)
        orch.stop()

        assert count1["count"] >= 2
        assert count2["count"] >= 2


class TestOrchestratorErrorIsolation:
    """测试异常隔离功能"""

    def test_job_exception_does_not_crash_orchestrator(self):
        """测试一个 job 抛出 Exception 时，主 loop 依然存活"""
        orch = Orchestrator()

        good_job_count = {"count": 0}
        error_job_count = {"count": 0}

        def good_job():
            good_job_count["count"] += 1

        def bad_job():
            error_job_count["count"] += 1
            raise RuntimeError("Simulated job failure")

        # 注册好任务和坏任务
        orch.register_job("good_job", interval=0.1, func=good_job)
        orch.register_job("bad_job", interval=0.1, func=bad_job)

        # 启动调度器
        orch.start()

        # 等待足够时间让坏任务执行并抛出异常
        time.sleep(0.35)

        # 停止调度器
        orch.stop()

        # 验证：
        # 1. 好任务仍然在执行（没有被坏任务杀死）
        # 2. 坏任务被调用了至少一次
        # 3. orchestrator 仍在运行状态
        assert good_job_count["count"] >= 2, "Good job should continue running"
        assert error_job_count["count"] >= 1, "Bad job should have been called"
        assert not orch.is_running, "Orchestrator should stop cleanly"

    def test_exception_is_logged(self):
        """测试异常被正确记录"""
        orch = Orchestrator()

        error_count = {"count": 0}

        def failing_job():
            error_count["count"] += 1
            raise ValueError("Test error")

        orch.register_job("failing", interval=0.1, func=failing_job)
        orch.start()
        time.sleep(0.25)
        orch.stop()

        # 验证错误计数增加
        job_status = orch.get_jobs_status()
        assert job_status["failing"]["error_count"] >= 1


class TestOrchestratorLifecycle:
    """测试生命周期方法"""

    def test_stop_when_not_running(self):
        """测试在未运行时调用 stop 不崩溃"""
        orch = Orchestrator()
        orch.stop()  # 应该安全退出

    def test_get_jobs_status(self):
        """测试获取任务状态"""
        orch = Orchestrator()

        def mock_job():
            pass

        orch.register_job("status_test", interval=1.0, func=mock_job)

        status = orch.get_jobs_status()

        assert "status_test" in status
        assert status["status_test"]["interval"] == 1.0
        assert status["status_test"]["run_count"] == 0
        assert status["status_test"]["error_count"] == 0

    def test_is_running_property(self):
        """测试 is_running 属性"""
        orch = Orchestrator()

        assert orch.is_running is False

        orch.register_job("test", interval=1.0, func=lambda: None)
        orch.start()

        assert orch.is_running is True

        orch.stop()

        assert orch.is_running is False

    def test_get_active_job_delegates_to_state(self, monkeypatch):
        """测试 get_active_job 委托给 utils.state"""
        orch = Orchestrator()
        expected = ("task-052-auto", Path("/tmp/task-052-auto"))

        monkeypatch.setattr("dimcause.utils.state.get_active_job", lambda: expected)

        assert orch.get_active_job() == expected

    def test_inspect_task_runtime_reports_artifacts_and_launch_state(self, tmp_path):
        """测试 inspect_task_runtime 汇总 runtime 与 artifact 可用性。"""
        orch = Orchestrator(project_root=tmp_path)
        runtime_dir = tmp_path / ".agent"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"
        task_packet.parent.mkdir(parents=True, exist_ok=True)
        task_packet.write_text("# Task Packet", encoding="utf-8")

        session_dir = (
            tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-调度-auto"
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        launch_log = session_dir / "launch.log"
        launch_log.write_text("launch", encoding="utf-8")

        (runtime_dir / "scheduler_state.json").write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "running",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "task_packet_file": str(task_packet),
                            "session_dir": str(session_dir),
                            "session_launch_pid": 99999,
                            "session_launch_log": str(launch_log),
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        inspection = orch.inspect_task_runtime("L0 调度")

        assert inspection["task_id"] == "L0 调度"
        assert inspection["launch_running"] is False
        artifacts = inspection["artifacts"]
        assert {"name": "task_packet_file", "path": str(task_packet), "exists": True} in artifacts
        assert {"name": "session_dir", "path": str(session_dir), "exists": True} in artifacts
        assert {"name": "session_launch_log", "path": str(launch_log), "exists": True} in artifacts
        run = inspection["run"]
        assert run is not None
        assert run["run_type"] == "scheduler_task_runtime"
        assert run["state"]["status"] == "running"
        assert run["metadata"]["scheduler_task_id"] == "L0 调度"

    def test_get_task_run_exports_minimum_run_contract(self, tmp_path):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        worktree = tmp_path / "worktrees" / "scheduler-l0"
        worktree.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "failed",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": str(worktree),
                            "started_at": "2026-03-13T10:00:00",
                            "updated_at": "2026-03-13T10:05:00",
                            "failed_at": "2026-03-13T10:06:00",
                            "failure_reason": "operator stop",
                            "resume_count": 1,
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        run = orch.get_task_run("L0 调度")

        assert run is not None
        assert run.run_type == "scheduler_task_runtime"
        assert run.state.status.value == "failed"
        assert run.state.ended_at == "2026-03-13T10:06:00"
        assert run.state.failure_reason == "operator stop"
        assert run.state.resume_count == 1
        assert run.workspace == str(worktree)

    def test_provision_task_workspace_creates_codex_branch_and_tmp_worktree(
        self, tmp_path, monkeypatch
    ):
        orch = Orchestrator(project_root=tmp_path)
        calls = []

        def fake_run_git(*args, cwd=None):
            calls.append((args, cwd))
            if args == ("worktree", "list", "--porcelain"):
                return 0, "", ""
            if args[:2] == ("worktree", "add"):
                return 0, "", ""
            raise AssertionError(f"unexpected git args: {args}")

        monkeypatch.setattr("dimcause.utils.git.run_git", fake_run_git)

        workspace = orch.provision_task_workspace("L0 调度")

        assert workspace["branch"].startswith("codex/task-")
        assert workspace["worktree"].startswith("/tmp/dimc-worktrees/scheduler-")
        assert calls[0][0] == ("worktree", "list", "--porcelain")
        assert calls[1][0][0:4] == ("worktree", "add", workspace["worktree"], "-b")
        assert calls[1][0][4] == workspace["branch"]
        assert calls[1][0][5] == "main"
        assert calls[1][1] == tmp_path

    def test_provision_task_workspace_reuses_existing_branch_worktree(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        existing_worktree = "/tmp/dimc-worktrees/scheduler-l0-d0f4e3aa"
        recorded = {}

        def fake_find(branch_name):
            recorded["branch"] = branch_name
            return Path(existing_worktree)

        monkeypatch.setattr(orch, "_find_worktree_for_branch", fake_find)

        workspace = orch.provision_task_workspace("L0 调度")

        assert recorded["branch"].startswith("codex/task-")
        assert workspace == {"branch": recorded["branch"], "worktree": existing_worktree}


class TestOrchestratorCleanup:
    def test_cleanup_task_workspaces_reclaims_done_task_workspace(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        worktree = Path("/tmp") / "dimc-worktrees" / f"scheduler-cleanup-{time.time_ns()}"
        worktree.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "done",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": str(worktree),
                            "session_dir": str(worktree / ".agent" / "sessions" / "l0-调度-auto"),
                            "session_file": str(
                                worktree / ".agent" / "sessions" / "l0-调度-auto" / "session.json"
                            ),
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        calls = []

        def fake_run_git(*args, cwd=None):
            calls.append((args, cwd))
            if args == ("rev-parse", "--verify", "--quiet", "codex/task-l0-abc12345"):
                return 0, "codex/task-l0-abc12345", ""
            if args == (
                "merge-base",
                "--is-ancestor",
                "codex/task-l0-abc12345",
                "main",
            ):
                return 0, "", ""
            if args == ("worktree", "remove", str(worktree)):
                return 0, "", ""
            if args == ("branch", "-D", "codex/task-l0-abc12345"):
                return 0, "", ""
            raise AssertionError(f"unexpected git args: {args}")

        monkeypatch.setattr("dimcause.utils.git.run_git", fake_run_git)
        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)
        monkeypatch.setattr(orch, "_current_branch", lambda: "codex/task-072-scheduler-cleanup")

        summary = orch.cleanup_task_workspaces()

        assert summary["cleaned"] == 1
        assert summary["skipped"] == 0
        assert summary["errors"] == 0
        assert summary["tasks"][0]["task_id"] == "L0 调度"
        assert summary["tasks"][0]["action"] == "cleaned"
        assert summary["tasks"][0]["worktree_removed"] is True
        assert summary["tasks"][0]["branch_deleted"] is True
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["status"] == "done"
        assert runtime["worktree"] is None
        assert runtime["session_dir"] is None
        assert runtime["session_file"] is None
        assert runtime["archived_worktree"] == str(worktree)
        assert runtime["cleanup_status"] == "cleaned"
        assert runtime["cleanup_branch_deleted"] is True
        assert runtime["cleanup_worktree_removed"] is True
        assert calls[-1][0] == ("branch", "-D", "codex/task-l0-abc12345")

    def test_cleanup_task_workspaces_keeps_failed_tasks_for_review_by_default(
        self, tmp_path, monkeypatch
    ):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "failed",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": "/tmp/dimc-worktrees/scheduler-l0-abc12345",
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)

        def fail_if_called(*args, **kwargs):
            raise AssertionError("run_git should not be called for failed task cleanup by default")

        monkeypatch.setattr("dimcause.utils.git.run_git", fail_if_called)

        summary = orch.cleanup_task_workspaces()

        assert summary["cleaned"] == 0
        assert summary["skipped"] == 1
        assert summary["tasks"][0]["reason"] == "failed_task_kept_for_review"
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["cleanup_status"] == "skipped"
        assert runtime["cleanup_reason"] == "failed_task_kept_for_review"
        assert runtime["worktree"] == "/tmp/dimc-worktrees/scheduler-l0-abc12345"

    def test_cleanup_task_workspaces_skips_when_launch_pid_still_running(
        self, tmp_path, monkeypatch
    ):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "done",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": "/tmp/dimc-worktrees/scheduler-l0-abc12345",
                            "session_launch_pid": 43210,
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: True)

        def fail_if_called(*args, **kwargs):
            raise AssertionError("run_git should not be called when launch pid is alive")

        monkeypatch.setattr("dimcause.utils.git.run_git", fail_if_called)

        summary = orch.cleanup_task_workspaces()

        assert summary["cleaned"] == 0
        assert summary["skipped"] == 1
        assert summary["tasks"][0]["reason"] == "launch_pid_running"
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["cleanup_status"] == "skipped"
        assert runtime["cleanup_reason"] == "launch_pid_running"
        assert runtime["worktree"] == "/tmp/dimc-worktrees/scheduler-l0-abc12345"


class TestOrchestratorRuntimePrune:
    def test_prune_runtime_tasks_removes_old_done_entries(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "done",
                            "job_id": "l0-调度-auto",
                            "worktree": None,
                            "session_dir": None,
                            "cleanup_at": old_ts,
                            "completed_at": old_ts,
                            "archived_worktree": "/tmp/dimc-worktrees/scheduler-l0-old",
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)

        summary = orch.prune_runtime_tasks(retain_days=7)

        assert summary["pruned"] == 1
        assert summary["skipped"] == 0
        assert summary["tasks"][0]["task_id"] == "L0 调度"
        assert summary["tasks"][0]["action"] == "pruned"
        assert orch.get_task_runtime("L0 调度") is None

    def test_prune_runtime_tasks_skips_recent_or_uncleaned_entries(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        new_ts = datetime.now().isoformat()
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "done",
                            "job_id": "l0-调度-auto",
                            "worktree": None,
                            "session_dir": None,
                            "cleanup_at": new_ts,
                        },
                        "L1 自动化": {
                            "status": "done",
                            "job_id": "l1-自动化-auto",
                            "worktree": "/tmp/dimc-worktrees/scheduler-l1-old",
                            "session_dir": None,
                            "cleanup_at": old_ts,
                        },
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)

        summary = orch.prune_runtime_tasks(retain_days=7)

        assert summary["pruned"] == 0
        assert summary["skipped"] == 2
        reasons = {item["task_id"]: item["reason"] for item in summary["tasks"]}
        assert reasons["L0 调度"] == "within_retention_window"
        assert reasons["L1 自动化"] == "workspace_not_cleaned"
        assert orch.get_task_runtime("L0 调度") is not None
        assert orch.get_task_runtime("L1 自动化") is not None

    def test_prune_runtime_tasks_failed_requires_opt_in(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "failed",
                            "job_id": "l0-调度-auto",
                            "worktree": None,
                            "session_dir": None,
                            "cleanup_at": old_ts,
                            "failed_at": old_ts,
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)

        default_summary = orch.prune_runtime_tasks(retain_days=7)
        assert default_summary["pruned"] == 0
        assert default_summary["skipped"] == 1
        assert default_summary["tasks"][0]["reason"] == "failed_task_kept_for_review"
        assert orch.get_task_runtime("L0 调度") is not None

        include_failed_summary = orch.prune_runtime_tasks(retain_days=7, include_failed=True)
        assert include_failed_summary["pruned"] == 1
        assert include_failed_summary["tasks"][0]["action"] == "pruned"
        assert orch.get_task_runtime("L0 调度") is None


class TestOrchestratorRuntimeReconcile:
    def test_reconcile_running_tasks_marks_dead_launch_failed(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "task-packet.md").write_text("# packet", encoding="utf-8")
        session_dir = (
            tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-调度-auto"
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        durable_session_file = job_dir / "session.json"
        launch_log = session_dir / "launch.log"
        session_file.write_text("{}", encoding="utf-8")
        durable_session_file.write_text("{}", encoding="utf-8")
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "running",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": str(tmp_path / "worktrees" / "scheduler-l0"),
                            "job_dir": str(job_dir),
                            "session_file": str(session_file),
                            "durable_session_file": str(durable_session_file),
                            "session_launch_pid": 43210,
                            "session_launch_log": str(launch_log),
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: ("l0-调度-auto", job_dir))
        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
            lambda *args, **kwargs: None,
        )

        summary = orch.reconcile_running_tasks()

        assert summary["reconciled"] == 1
        assert summary["skipped"] == 0
        assert summary["tasks"][0]["action"] == "reconciled"
        assert summary["tasks"][0]["reason"] == "launch_pid_not_running"
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["status"] == "failed"
        assert runtime["session_reconcile_reason"] == "launch_pid_not_running"
        assert "launch exited before scheduler completion" in runtime["failure_reason"]
        assert "# reconciled at:" in launch_log.read_text(encoding="utf-8")
        assert '"reconcile_reason": "launch_pid_not_running"' in session_file.read_text(
            encoding="utf-8"
        )
        assert '"session_reconcile_reason": "launch_pid_not_running"' in (
            job_dir / "meta.json"
        ).read_text(encoding="utf-8")
        assert (job_dir / "job-end.md").exists()

    def test_reconcile_running_tasks_keeps_manual_running_without_launch_pid(
        self, tmp_path, monkeypatch
    ):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "running",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "get_active_job", lambda: None)

        summary = orch.reconcile_running_tasks()

        assert summary["reconciled"] == 0
        assert summary["skipped"] == 1
        assert summary["tasks"][0]["reason"] == "running_without_launch_pid_review_required"
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["status"] == "running"
        assert runtime.get("session_reconcile_reason") is None


class TestOrchestratorStop:
    def test_stop_task_launch_terminates_process_and_marks_failed(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "task-packet.md").write_text("# packet", encoding="utf-8")
        session_dir = (
            tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-调度-auto"
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        durable_session_file = job_dir / "session.json"
        launch_log = session_dir / "launch.log"
        session_file.write_text("{}", encoding="utf-8")
        durable_session_file.write_text("{}", encoding="utf-8")
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "running",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": str(tmp_path / "worktrees" / "scheduler-l0"),
                            "job_dir": str(job_dir),
                            "session_file": str(session_file),
                            "durable_session_file": str(durable_session_file),
                            "session_launch_pid": 43210,
                            "session_launch_log": str(launch_log),
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        kill_calls = []
        running = {"alive": True}

        def fake_kill(pid, sig):
            kill_calls.append((pid, sig))
            if sig == 0:
                if running["alive"]:
                    return None
                raise ProcessLookupError()
            if pid == 43210 and sig == signal.SIGTERM:
                running["alive"] = False
                return None
            raise AssertionError(f"unexpected kill call: {(pid, sig)}")

        monkeypatch.setattr("dimcause.scheduler.orchestrator.os.kill", fake_kill)
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
            lambda *args, **kwargs: None,
        )

        result = orch.stop_task_launch("L0 调度", reason="operator stop")

        assert result["status"] == "failed"
        assert result["signal_sent"] is True
        assert result["stop_signal"] == "SIGTERM"
        assert kill_calls[0] == (43210, 0)
        assert kill_calls[1] == (43210, signal.SIGTERM)
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["status"] == "failed"
        assert runtime["failure_reason"] == "operator stop"
        assert runtime["session_stop_signal"] == "SIGTERM"
        assert runtime["session_stop_reason"] == "operator stop"
        assert "operator stop" in launch_log.read_text(encoding="utf-8")
        assert '"stop_signal": "SIGTERM"' in session_file.read_text(encoding="utf-8")
        assert '"session_stop_signal": "SIGTERM"' in (job_dir / "meta.json").read_text(
            encoding="utf-8"
        )

    def test_stop_task_launch_without_live_pid_marks_failed(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "task-packet.md").write_text("# packet", encoding="utf-8")
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "running",
                            "job_id": "l0-调度-auto",
                            "job_dir": str(job_dir),
                            "session_launch_pid": 43210,
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
            lambda *args, **kwargs: None,
        )

        result = orch.stop_task_launch("L0 调度", reason="operator stop")

        assert result["status"] == "failed"
        assert result["signal_sent"] is False
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["failure_reason"] == "operator stop"

    def test_resume_task_launch_restarts_failed_runtime(self, tmp_path, monkeypatch):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        worktree = tmp_path / "worktrees" / "scheduler-l0"
        worktree.mkdir(parents=True, exist_ok=True)
        job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
        job_dir.mkdir(parents=True, exist_ok=True)
        session_dir = worktree / ".agent" / "sessions" / "l0-调度-auto"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        durable_session_file = job_dir / "session.json"
        launch_script = session_dir / "launch.sh"
        launch_log = session_dir / "launch.log"
        launch_script.write_text("#!/usr/bin/env zsh\nexit 0\n", encoding="utf-8")
        launch_script.chmod(0o755)
        session_file.write_text("{}", encoding="utf-8")
        durable_session_file.write_text("{}", encoding="utf-8")
        (job_dir / "meta.json").write_text("{}", encoding="utf-8")
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "failed",
                            "job_id": "l0-调度-auto",
                            "branch": "codex/task-l0-abc12345",
                            "worktree": str(worktree),
                            "job_dir": str(job_dir),
                            "session_dir": str(session_dir),
                            "session_file": str(session_file),
                            "durable_session_file": str(durable_session_file),
                            "session_launch_script": str(launch_script),
                            "session_launch_command": "bash -lc echo resumed",
                            "session_launch_pid": 43210,
                            "session_launch_log": str(launch_log),
                            "failure_reason": "operator stop",
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(orch, "_is_process_alive", lambda pid: False)

        class DummyProcess:
            pid = 54321

        monkeypatch.setattr(
            "dimcause.scheduler.orchestrator.subprocess.Popen",
            lambda *args, **kwargs: DummyProcess(),
        )

        result = orch.resume_task_launch("L0 调度")

        assert result["status"] == "running"
        assert result["launch_pid"] == 54321
        assert result["launch_command"] == "bash -lc echo resumed"
        assert result["resume_count"] == 1
        runtime = orch.get_task_runtime("L0 调度")
        assert runtime is not None
        assert runtime["status"] == "running"
        assert runtime["session_launch_pid"] == 54321
        assert runtime["failure_reason"] is None
        assert runtime["resume_count"] == 1
        assert "# resumed at:" in launch_log.read_text(encoding="utf-8")
        assert '"resume_count": 1' in session_file.read_text(encoding="utf-8")
        assert '"resume_count": 1' in (job_dir / "meta.json").read_text(encoding="utf-8")

    def test_resume_task_launch_rejects_completed_task(self, tmp_path):
        orch = Orchestrator(project_root=tmp_path)
        runtime_file = tmp_path / ".agent" / "scheduler_state.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "tasks": {
                        "L0 调度": {
                            "status": "done",
                            "session_launch_script": str(tmp_path / "missing.sh"),
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="Task already completed"):
            orch.resume_task_launch("L0 调度")
