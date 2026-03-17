import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dimcause.scheduler.orchestrator import Orchestrator
from dimcause.scheduler.runner import TaskRunner


def test_execute_job_start_uses_dimcause_cli_module(tmp_path, monkeypatch):
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)

    recorded = {}
    provisioned = {
        "branch": "codex/task-task-040-workspace",
        "worktree": str(tmp_path / "worktrees" / "scheduler-task-040-workspace"),
    }
    task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "Task-040.md"
    task_packet.parent.mkdir(parents=True, exist_ok=True)
    task_packet.write_text("# task packet", encoding="utf-8")

    def fake_run(cmd, cwd=None, check=False):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd
        recorded["check"] = check
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setitem(sys.modules, "pyperclip", SimpleNamespace(copy=lambda text: None))
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(orchestrator, "get_active_job", lambda: None)
    monkeypatch.setattr(orchestrator, "_sync_task_event_to_knowledge", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        orchestrator, "provision_task_workspace", lambda task_id, work_class="product": provisioned
    )
    monkeypatch.setattr(
        orchestrator, "materialize_task_packet", lambda *args, **kwargs: task_packet
    )

    result = runner._execute_job_start("Task-040", "context prompt")

    assert recorded["cmd"] == [
        sys.executable,
        "-m",
        "dimcause.cli",
        "job-start",
        "task-040-auto",
    ]
    assert recorded["cwd"] == orchestrator.root
    assert recorded["check"] is True
    assert (tmp_path / "tmp" / "context" / "Task-040_context.md").exists()
    assert result["job_id"] == "task-040-auto"
    assert result["context_file"] == tmp_path / "tmp" / "context" / "Task-040_context.md"
    assert result["task_packet_file"] == task_packet
    assert result["task_board_file"] == tmp_path / "tmp" / "coordination" / "task_board.md"
    assert result["job_dir"].name == "task-040-auto"
    assert result["branch"] == provisioned["branch"]
    assert result["worktree"] == provisioned["worktree"]
    assert result["work_class"] == "product"
    assert (
        result["session_dir"]
        == Path(provisioned["worktree"]) / ".agent" / "sessions" / "task-040-auto"
    )
    assert result["session_file"] == result["session_dir"] / "session.json"
    assert result["session_readme"] == result["session_dir"] / "README.md"
    assert result["durable_session_file"] == result["job_dir"] / "session.json"
    assert result["session_preflight_script"] == result["session_dir"] / "preflight.sh"
    assert result["session_launch_script"] == result["session_dir"] / "launch.sh"
    assert result["session_codex_run_script"] == result["session_dir"] / "codex-run.sh"
    assert result["session_codex_output_file"] == result["session_dir"] / "codex-last.md"
    assert (result["job_dir"] / "meta.json").exists()
    assert (result["job_dir"] / "task-packet.md").exists()
    assert result["session_dir"].exists()
    assert (result["session_dir"] / "context.md").exists()
    assert (result["session_dir"] / "task-packet.md").exists()
    assert (result["session_dir"] / "preflight.sh").exists()
    assert (result["session_dir"] / "launch.sh").exists()
    assert (result["session_dir"] / "codex-run.sh").exists()
    assert (result["job_dir"] / "session.json").exists()
    assert provisioned["branch"] in (result["job_dir"] / "meta.json").read_text(encoding="utf-8")
    assert provisioned["worktree"] in (result["job_dir"] / "meta.json").read_text(encoding="utf-8")
    assert str(result["durable_session_file"]) in (result["job_dir"] / "meta.json").read_text(
        encoding="utf-8"
    )
    assert "isolated execution bundle" in result["session_readme"].read_text(encoding="utf-8")


def test_execute_job_start_refuses_when_active_job_exists(tmp_path, monkeypatch):
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)

    monkeypatch.setattr(
        orchestrator,
        "get_active_job",
        lambda: ("existing-job", Path("/tmp/existing-job")),
    )

    with pytest.raises(RuntimeError, match="Active job already running"):
        runner._execute_job_start("Task-052", "context prompt")


def test_execute_job_start_reconciles_stale_active_job_before_starting(tmp_path, monkeypatch):
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)

    state = {"reconcile_calls": 0}
    provisioned = {
        "branch": "codex/task-task-077-workspace",
        "worktree": str(tmp_path / "worktrees" / "scheduler-task-077-workspace"),
    }
    task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "Task-077.md"
    task_packet.parent.mkdir(parents=True, exist_ok=True)
    task_packet.write_text("# task packet", encoding="utf-8")

    monkeypatch.setitem(sys.modules, "pyperclip", SimpleNamespace(copy=lambda text: None))
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    monkeypatch.setattr(
        orchestrator,
        "reconcile_running_tasks",
        lambda dry_run=False: (
            state.__setitem__("reconcile_calls", state["reconcile_calls"] + 1)
            or {"reconciled": 1, "skipped": 0, "tasks": []}
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "get_active_job",
        lambda: None if state["reconcile_calls"] > 0 else ("stale-job", Path("/tmp/stale-job")),
    )
    monkeypatch.setattr(orchestrator, "_sync_task_event_to_knowledge", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        orchestrator, "provision_task_workspace", lambda task_id, work_class="product": provisioned
    )
    monkeypatch.setattr(
        orchestrator, "materialize_task_packet", lambda *args, **kwargs: task_packet
    )

    result = runner._execute_job_start("Task-077", "context prompt")

    assert state["reconcile_calls"] == 1
    assert result["job_id"] == "task-077-auto"


def test_run_task_dry_run_works_with_synthetic_status_prompt(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATUS.md").write_text(
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
        encoding="utf-8",
    )
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)
    monkeypatch.setattr(orchestrator, "get_active_job", lambda: None)

    result = runner.run_task("L0 调度", dry_run=True, auto_approve=True)

    assert result is None


def test_execute_job_start_materializes_runtime_assets(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATUS.md").write_text(
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)
    provisioned = {
        "branch": "codex/task-l0-9db8dd2e",
        "worktree": str(tmp_path / "worktrees" / "scheduler-l0-9db8dd2e"),
    }

    monkeypatch.setitem(sys.modules, "pyperclip", SimpleNamespace(copy=lambda text: None))
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    monkeypatch.setattr(orchestrator, "get_active_job", lambda: None)
    monkeypatch.setattr(orchestrator, "_sync_task_event_to_knowledge", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        orchestrator, "provision_task_workspace", lambda task_id, work_class="product": provisioned
    )

    result = runner._execute_job_start("L0 调度", "context prompt")

    assert result["task_packet_file"].exists()
    assert result["task_board_file"].exists()
    assert (result["job_dir"] / "meta.json").exists()
    assert (result["job_dir"] / "task-packet.md").exists()
    runtime_state = (tmp_path / ".agent" / "scheduler_state.json").read_text(encoding="utf-8")
    assert '"task_packet_file"' in runtime_state
    assert '"job_dir"' in runtime_state
    assert "L0_调度.md" in runtime_state
    assert provisioned["branch"] in runtime_state
    assert provisioned["worktree"] in runtime_state
    assert '"session_dir"' in runtime_state
    assert '"session_file"' in runtime_state
    assert '"session_readme"' in runtime_state
    assert '"durable_session_file"' in runtime_state
    assert '"session_preflight_script"' in runtime_state
    assert '"session_launch_script"' in runtime_state
    assert '"session_codex_run_script"' in runtime_state
    assert '"session_codex_output_file"' in runtime_state
    task_board = result["task_board_file"].read_text(encoding="utf-8")
    assert provisioned["branch"] in task_board
    assert provisioned["worktree"] in task_board
    task_packet_body = result["task_packet_file"].read_text(encoding="utf-8")
    assert provisioned["branch"] in task_packet_body
    assert provisioned["worktree"] in task_packet_body
    assert (result["session_dir"] / "context.md").exists()
    assert (result["session_dir"] / "task-packet.md").exists()
    assert (result["session_dir"] / "preflight.sh").exists()
    assert (result["session_dir"] / "launch.sh").exists()
    assert (result["session_dir"] / "codex-run.sh").exists()
    assert (result["job_dir"] / "session.json").exists()
    assert "protected_doc_override" in task_packet_body
    assert "risk_level" in task_packet_body
    assert "## 4. Allowed Files" in task_packet_body
    assert "## 5. Forbidden Files" in task_packet_body
    assert str(result["session_preflight_script"]) in (
        result["session_dir"] / "session.json"
    ).read_text(encoding="utf-8")
    assert "preflight.sh" in (result["session_dir"] / "README.md").read_text(encoding="utf-8")
    assert "codex-run.sh" in (result["session_dir"] / "README.md").read_text(encoding="utf-8")
    assert "usage: launch.sh <command> [args...]" in (
        result["session_dir"] / "launch.sh"
    ).read_text(encoding="utf-8")
    launch_script_body = (result["session_dir"] / "launch.sh").read_text(encoding="utf-8")
    assert "preflight.sh" in launch_script_body
    assert "codex-run.sh" in launch_script_body
    codex_run_body = (result["session_dir"] / "codex-run.sh").read_text(encoding="utf-8")
    assert "codex exec --full-auto" in codex_run_body
    assert "context.md" in codex_run_body


def test_execute_job_start_can_auto_launch_session_command(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATUS.md").write_text(
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)
    provisioned = {
        "branch": "codex/task-l0-9db8dd2e",
        "worktree": str(tmp_path / "worktrees" / "scheduler-l0-9db8dd2e"),
    }
    popen_record = {}

    class DummyProcess:
        pid = 43210

    monkeypatch.setitem(sys.modules, "pyperclip", SimpleNamespace(copy=lambda text: None))
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0)
    )
    monkeypatch.setattr(orchestrator, "get_active_job", lambda: None)
    monkeypatch.setattr(orchestrator, "_sync_task_event_to_knowledge", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        orchestrator, "provision_task_workspace", lambda task_id, work_class="product": provisioned
    )

    def fake_popen(cmd, cwd=None, stdout=None, stderr=None, text=None, start_new_session=None):
        popen_record["cmd"] = cmd
        popen_record["cwd"] = cwd
        popen_record["stderr"] = stderr
        popen_record["text"] = text
        popen_record["start_new_session"] = start_new_session
        if stdout is not None:
            stdout.write("launched\n")
            stdout.flush()
        return DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = runner._execute_job_start("L0 调度", "context prompt", launch="bash -lc echo launched")

    assert result["launch_command"] == "bash -lc echo launched"
    assert result["launch_pid"] == 43210
    assert result["launch_log"] == result["session_dir"] / "launch.log"
    assert result["launch_log"].exists()
    assert "launched" in result["launch_log"].read_text(encoding="utf-8")
    assert popen_record["cmd"][0] == str(result["session_launch_script"])
    assert popen_record["cmd"][1:] == ["bash", "-lc", "echo", "launched"]
    assert popen_record["cwd"] == orchestrator.root
    assert popen_record["text"] is True
    assert popen_record["start_new_session"] is True
    runtime_state = (tmp_path / ".agent" / "scheduler_state.json").read_text(encoding="utf-8")
    assert '"session_launch_command": "bash -lc echo launched"' in runtime_state
    assert '"session_launch_pid": 43210' in runtime_state
    assert '"session_launch_log"' in runtime_state
    session_payload = (result["session_dir"] / "session.json").read_text(encoding="utf-8")
    assert '"launch_command": "bash -lc echo launched"' in session_payload
    assert '"launch_pid": 43210' in session_payload
    meta_payload = (result["job_dir"] / "meta.json").read_text(encoding="utf-8")
    assert '"session_launch_command": "bash -lc echo launched"' in meta_payload
    assert '"session_launch_pid": 43210' in meta_payload


def test_run_codex_task_bootstraps_runtime_and_resumes_launch(tmp_path, monkeypatch):
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)
    bootstrap_calls = {"count": 0}
    recorded = {}
    session_dir = tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-auto"
    session_dir.mkdir(parents=True, exist_ok=True)
    codex_run_script = session_dir / "codex-run.sh"
    codex_run_script.write_text("#!/usr/bin/env zsh\nexit 0\n", encoding="utf-8")
    codex_run_script.chmod(0o755)

    def fake_run_task(task_id, dry_run=False, auto_approve=False, launch=None):
        bootstrap_calls["count"] += 1
        assert task_id == "L0 调度"
        assert dry_run is False
        assert auto_approve is True
        runtime_dir = tmp_path / ".agent"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "scheduler_state.json").write_text(
            (
                "{\n"
                '  "tasks": {\n'
                '    "L0 调度": {\n'
                '      "status": "running",\n'
                f'      "session_dir": "{session_dir}",\n'
                f'      "session_codex_run_script": "{codex_run_script}",\n'
                f'      "session_codex_output_file": "{session_dir / "codex-last.md"}"\n'
                "    }\n"
                "  }\n"
                "}\n"
            ),
            encoding="utf-8",
        )

    def fake_resume(task_id, *, launch=None):
        recorded["task_id"] = task_id
        recorded["launch"] = launch
        return {
            "status": "running",
            "launch_command": launch,
            "launch_pid": 24680,
            "launch_log": str(session_dir / "launch.log"),
        }

    monkeypatch.setattr(runner, "run_task", fake_run_task)
    monkeypatch.setattr(orchestrator, "resume_task_launch", fake_resume)

    result = runner.run_codex_task(
        "L0 调度",
        auto_approve=True,
        model="gpt-5.4",
        profile="fast",
        json_output=True,
    )

    assert bootstrap_calls["count"] == 1
    assert recorded["task_id"] == "L0 调度"
    assert recorded["launch"] == (f"{codex_run_script} --profile fast --model gpt-5.4 --json")
    assert result["launch_pid"] == 24680


def test_run_codex_task_dry_run_returns_command_preview(tmp_path):
    orchestrator = Orchestrator(project_root=tmp_path)
    runner = TaskRunner(orchestrator)
    session_dir = tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-auto"
    session_dir.mkdir(parents=True, exist_ok=True)
    codex_run_script = session_dir / "codex-run.sh"
    codex_run_script.write_text("#!/usr/bin/env zsh\nexit 0\n", encoding="utf-8")
    codex_run_script.chmod(0o755)
    runtime_dir = tmp_path / ".agent"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "scheduler_state.json").write_text(
        (
            "{\n"
            '  "tasks": {\n'
            '    "L0 调度": {\n'
            '      "status": "running",\n'
            f'      "session_dir": "{session_dir}",\n'
            f'      "worktree": "{tmp_path / "worktrees" / "scheduler-l0"}",\n'
            f'      "session_codex_run_script": "{codex_run_script}",\n'
            f'      "session_codex_output_file": "{session_dir / "codex-last.md"}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    result = runner.run_codex_task("L0 调度", dry_run=True)

    assert result["task_id"] == "L0 调度"
    assert result["command"] == str(codex_run_script)
    assert result["session_dir"] == str(session_dir)
    assert result["output_file"] == str(session_dir / "codex-last.md")
