from pathlib import Path

from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


def test_scheduler_status_displays_active_session_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
    job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job-start.md").write_text("# start", encoding="utf-8")
    runtime_dir = tmp_path / ".agent"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    session_dir = tmp_path / "worktrees" / "scheduler-l0" / ".agent" / "sessions" / "l0-调度-auto"
    launch_script = session_dir / "launch.sh"
    launch_log = session_dir / "launch.log"
    (runtime_dir / "scheduler_state.json").write_text(
        (
            "{\n"
            '  "tasks": {\n'
            '    "L0 调度": {\n'
            '      "status": "running",\n'
            '      "job_id": "l0-调度-auto",\n'
            '      "branch": "codex/task-l0-abc12345",\n'
            f'      "worktree": "{tmp_path / "worktrees" / "scheduler-l0"}",\n'
            f'      "session_dir": "{session_dir}",\n'
            f'      "session_launch_script": "{launch_script}",\n'
            '      "session_launch_command": "bash -lc echo launched",\n'
            '      "session_launch_pid": 43210,\n'
            f'      "session_launch_log": "{launch_log}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.get_active_job",
        lambda self: ("l0-调度-auto", job_dir),
    )

    result = runner.invoke(app, ["scheduler", "status"])

    assert result.exit_code == 0, result.stdout
    assert "Active Job" in result.stdout
    assert "L0 调度" in result.stdout
    assert "codex/task-l0-abc12345" in result.stdout
    assert ".agent/sessions/" in result.stdout
    assert "launch.sh" in result.stdout
    assert "bash -lc echo launched" in result.stdout
    assert "43210" in result.stdout
    assert "launch.log" in result.stdout


def test_scheduler_status_lists_standalone_agent_task_as_next_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
                "| L0 调度 | Orchestrator 核心调度器 | ✅ 完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
        encoding="utf-8",
    )
    agent_tasks_dir = tmp_path / ".agent" / "agent-tasks"
    agent_tasks_dir.mkdir(parents=True, exist_ok=True)
    (agent_tasks_dir / "agent_why-object-evidence-v1_minimal.md").write_text(
        "\n".join(
            [
                "---",
                "priority: P1",
                "status: Open",
                "---",
                "",
                "# Agent Task why-object-evidence-v1: Why 最小对象证据落点",
                "",
                "## 目标",
                "让 why 链路先落出最小对象证据视图。",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scheduler", "status"])

    assert result.exit_code == 0, result.stdout
    assert "Why 最小对象证据落点" in result.stdout
    assert "why-object-evidence-v1" in result.stdout
    assert "P1" in result.stdout


def test_scheduler_inspect_renders_runtime_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_inspect(self, task_id):
        assert task_id == "L0 调度"
        return {
            "task_id": task_id,
            "runtime": {
                "status": "running",
                "job_id": "l0-调度-auto",
                "branch": "codex/task-l0-abc12345",
                "worktree": str(tmp_path / "worktrees" / "scheduler-l0"),
                "started_at": "2026-03-08T12:00:00",
                "session_launch_command": "bash -lc echo launched",
                "session_launch_pid": 43210,
                "session_launch_log": str(
                    tmp_path
                    / "worktrees"
                    / "scheduler-l0"
                    / ".agent"
                    / "sessions"
                    / "l0-调度-auto"
                    / "launch.log"
                ),
            },
            "launch_running": False,
            "artifacts": [
                {
                    "name": "task_packet_file",
                    "path": str(tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"),
                    "exists": True,
                },
                {
                    "name": "session_preflight_script",
                    "path": str(
                        tmp_path
                        / "worktrees"
                        / "scheduler-l0"
                        / ".agent"
                        / "sessions"
                        / "l0-调度-auto"
                        / "preflight.sh"
                    ),
                    "exists": False,
                },
            ],
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.inspect_task_runtime",
        fake_inspect,
    )

    result = runner.invoke(app, ["scheduler", "inspect", "L0 调度"])

    assert result.exit_code == 0, result.stdout
    assert "status: running" in result.stdout
    assert "job_id: l0-调度-auto" in result.stdout
    assert "branch: codex/task-l0-abc12345" in result.stdout
    assert "command: bash -lc echo launched" in result.stdout
    assert "pid: 43210" in result.stdout
    assert "running: no" in result.stdout
    assert "task_packet_file:" in result.stdout
    assert "exists: yes" in result.stdout
    assert "session_preflight_script:" in result.stdout
    assert "exists: no" in result.stdout


def test_scheduler_inspect_exits_when_task_runtime_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fake_inspect(self, task_id):
        raise RuntimeError(f"No runtime state found for task: {task_id}")

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.inspect_task_runtime",
        fake_inspect,
    )

    result = runner.invoke(app, ["scheduler", "inspect", "L9 不存在"])

    assert result.exit_code == 1
    assert "No runtime state found for task: L9 不存在" in result.stdout


def test_scheduler_run_forwards_launch_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = {}

    class DummyRunner:
        def __init__(self, orchestrator):
            recorded["orchestrator_root"] = orchestrator.root

        def run_task(self, task, dry_run=False, auto_approve=False, launch=None):
            recorded["task"] = task
            recorded["dry_run"] = dry_run
            recorded["auto_approve"] = auto_approve
            recorded["launch"] = launch

    monkeypatch.setattr("dimcause.scheduler.runner.TaskRunner", DummyRunner)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "run",
            "L0 调度",
            "--yes",
            "--launch",
            "bash -lc echo launched",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert recorded["task"] == "L0 调度"
    assert recorded["auto_approve"] is True
    assert recorded["launch"] == "bash -lc echo launched"


def test_scheduler_codex_run_forwards_options(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = {}

    class DummyRunner:
        def __init__(self, orchestrator):
            recorded["orchestrator_root"] = orchestrator.root

        def run_codex_task(
            self,
            task,
            *,
            auto_approve=False,
            dry_run=False,
            model=None,
            profile=None,
            json_output=False,
        ):
            recorded["task"] = task
            recorded["auto_approve"] = auto_approve
            recorded["dry_run"] = dry_run
            recorded["model"] = model
            recorded["profile"] = profile
            recorded["json_output"] = json_output
            return {
                "status": "running",
                "launch_command": "/tmp/session/codex-run.sh --profile fast --model gpt-5.4 --json",
                "launch_pid": 12345,
                "launch_log": str(tmp_path / "launch.log"),
            }

    monkeypatch.setattr("dimcause.scheduler.runner.TaskRunner", DummyRunner)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "codex-run",
            "L0 调度",
            "--yes",
            "--model",
            "gpt-5.4",
            "--profile",
            "fast",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert recorded["task"] == "L0 调度"
    assert recorded["auto_approve"] is True
    assert recorded["dry_run"] is False
    assert recorded["model"] == "gpt-5.4"
    assert recorded["profile"] == "fast"
    assert recorded["json_output"] is True
    assert "Codex CLI 已启动。" in result.stdout
    assert "12345" in result.stdout


def test_scheduler_codex_run_dry_run_renders_command_preview(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class DummyRunner:
        def __init__(self, orchestrator):
            pass

        def run_codex_task(
            self,
            task,
            *,
            auto_approve=False,
            dry_run=False,
            model=None,
            profile=None,
            json_output=False,
        ):
            assert task == "L0 调度"
            assert dry_run is True
            return {
                "task_id": task,
                "command": "/tmp/session/codex-run.sh --profile fast",
                "worktree": str(tmp_path / "worktree"),
                "session_dir": str(tmp_path / "session"),
                "output_file": str(tmp_path / "session" / "codex-last.md"),
            }

    monkeypatch.setattr("dimcause.scheduler.runner.TaskRunner", DummyRunner)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "codex-run",
            "L0 调度",
            "--dry-run",
            "--profile",
            "fast",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Codex 启动命令预览" in result.stdout
    assert "/tmp/session/codex-run.sh --profile fast" in result.stdout


def test_scheduler_intake_materializes_local_task_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "intake",
            "why-object-evidence-v1",
            "--title",
            "Why 最小对象证据落点",
            "--goal",
            "让 why 链路先落出最小对象证据视图。",
            "--priority",
            "P1",
            "--related-file",
            "src/dimcause/cli.py",
            "--acceptance",
            "`dimc why` 至少输出一条对象证据线索",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Task card created." in result.stdout
    assert "dimc scheduler run 'why-object-evidence-v1' --yes" in result.stdout
    card_files = list(
        (tmp_path / ".agent" / "agent-tasks").glob("agent_why-object-evidence-v1_*.md")
    )
    assert len(card_files) == 1
    content = card_files[0].read_text(encoding="utf-8")
    assert "priority: P1" in content
    assert "task_class: implementation" in content
    assert "risk_level: medium" in content
    assert "cli_hint: dimc why" in content
    assert "## 目标" in content
    assert "让 why 链路先落出最小对象证据视图。" in content


def test_scheduler_kickoff_materializes_goal_and_runs_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = {}

    class DummyRunner:
        def __init__(self, orchestrator):
            recorded["root"] = orchestrator.root

        def run_task(self, task, dry_run=False, auto_approve=False, launch=None):
            recorded["task"] = task
            recorded["dry_run"] = dry_run
            recorded["auto_approve"] = auto_approve
            recorded["launch"] = launch

    monkeypatch.setattr("dimcause.scheduler.runner.TaskRunner", DummyRunner)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "kickoff",
            "--goal",
            "补齐 scheduler 的高层目标入口，并直接启动调度执行。",
            "--dry-run",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "High-level goal materialized." in result.stdout
    assert recorded["dry_run"] is True
    assert recorded["auto_approve"] is True
    assert recorded["task"]
    card_files = list((tmp_path / ".agent" / "agent-tasks").glob("agent_*.md"))
    assert len(card_files) == 1
    content = card_files[0].read_text(encoding="utf-8")
    assert "task_class: governance" in content
    assert "risk_level: low" in content
    assert "cli_hint: dimc scheduler" in content
    assert "补齐 scheduler 的高层目标入口，并直接启动调度执行。" in content


def test_scheduler_intake_infers_governance_defaults_and_related_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "intake",
            "scheduler-intake-defaults-v1",
            "--title",
            "调度 intake 默认字段收敛",
            "--goal",
            "补齐 scheduler intake 的默认字段生成，减少手工传参。",
        ],
    )

    assert result.exit_code == 0, result.stdout
    card_files = list(
        (tmp_path / ".agent" / "agent-tasks").glob("agent_scheduler-intake-defaults-v1_*.md")
    )
    assert len(card_files) == 1
    content = card_files[0].read_text(encoding="utf-8")
    assert "task_class: governance" in content
    assert "risk_level: low" in content
    assert "cli_hint: dimc scheduler" in content
    assert "## 相关文件" in content
    assert "`src/dimcause/scheduler/orchestrator.py`" in content
    assert "`src/dimcause/cli.py`" in content
    assert "- 完成与目标直接对应的最小治理脚本、模板或入口变更" in content
    assert "- 治理规则、入口和边界表述保持自洽" in content
    assert "- 先核对当前规则、入口和直接相关的治理文件" in content


def test_scheduler_loop_forwards_launch_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = {}

    class DummyLoop:
        def run_loop(self, max_rounds=0, auto_continue=False, poll_interval=5.0, launch=None):
            recorded["max_rounds"] = max_rounds
            recorded["auto_continue"] = auto_continue
            recorded["launch"] = launch

    monkeypatch.setattr("dimcause.scheduler.loop.SchedulerLoop", DummyLoop)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "loop",
            "--max-rounds",
            "3",
            "--auto",
            "--launch",
            "bash -lc echo launched",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert recorded["max_rounds"] == 3
    assert recorded["auto_continue"] is True
    assert recorded["launch"] == "bash -lc echo launched"


def test_scheduler_cleanup_forwards_options_and_renders_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_cleanup(self, *, include_failed=False, dry_run=False, base_ref="main"):
        captured["include_failed"] = include_failed
        captured["dry_run"] = dry_run
        captured["base_ref"] = base_ref
        return {
            "cleaned": 1,
            "skipped": 1,
            "errors": 0,
            "tasks": [
                {"task_id": "L0 调度", "action": "would_clean", "reason": "ok"},
                {
                    "task_id": "L1 自动化",
                    "action": "skipped",
                    "reason": "failed_task_kept_for_review",
                },
            ],
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.cleanup_task_workspaces",
        fake_cleanup,
    )

    result = runner.invoke(
        app,
        [
            "scheduler",
            "cleanup",
            "--include-failed",
            "--dry-run",
            "--base-ref",
            "main",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["include_failed"] is True
    assert captured["dry_run"] is True
    assert captured["base_ref"] == "main"
    assert "Dry-run preview" in result.stdout
    assert "cleaned: 1 | skipped: 1 | errors: 0" in result.stdout
    assert "L0 调度: would_clean (ok)" in result.stdout
    assert "L1 自动化: skipped (failed_task_kept_for_review)" in result.stdout


def test_scheduler_prune_runtime_forwards_options_and_renders_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_prune(self, *, include_failed=False, retain_days=14, dry_run=False):
        captured["include_failed"] = include_failed
        captured["retain_days"] = retain_days
        captured["dry_run"] = dry_run
        return {
            "pruned": 1,
            "skipped": 1,
            "tasks": [
                {"task_id": "L0 调度", "action": "would_prune", "reason": "ok"},
                {"task_id": "L1 自动化", "action": "skipped", "reason": "within_retention_window"},
            ],
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.prune_runtime_tasks",
        fake_prune,
    )

    result = runner.invoke(
        app,
        [
            "scheduler",
            "prune-runtime",
            "--include-failed",
            "--retain-days",
            "30",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["include_failed"] is True
    assert captured["retain_days"] == 30
    assert captured["dry_run"] is True
    assert "Dry-run preview" in result.stdout
    assert "pruned: 1 | skipped: 1" in result.stdout
    assert "L0 调度: would_prune (ok)" in result.stdout
    assert "L1 自动化: skipped (within_retention_window)" in result.stdout


def test_scheduler_reconcile_forwards_options_and_renders_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_reconcile(self, *, dry_run=False):
        captured["dry_run"] = dry_run
        return {
            "reconciled": 1,
            "skipped": 1,
            "tasks": [
                {
                    "task_id": "L0 调度",
                    "action": "would_reconcile",
                    "reason": "launch_pid_not_running",
                },
                {
                    "task_id": "L1 自动化",
                    "action": "skipped",
                    "reason": "running_without_launch_pid_review_required",
                },
            ],
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.reconcile_running_tasks",
        fake_reconcile,
    )

    result = runner.invoke(app, ["scheduler", "reconcile", "--dry-run"])

    assert result.exit_code == 0, result.stdout
    assert captured["dry_run"] is True
    assert "Dry-run preview" in result.stdout
    assert "reconciled: 1 | skipped: 1" in result.stdout
    assert "L0 调度: would_reconcile (launch_pid_not_running)" in result.stdout
    assert "L1 自动化: skipped (running_without_launch_pid_review_required)" in result.stdout


def test_scheduler_stop_forwards_options_and_renders_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_stop(self, task_id, *, reason, force=False):
        captured["task_id"] = task_id
        captured["reason"] = reason
        captured["force"] = force
        return {
            "status": "failed",
            "stop_signal": "SIGKILL",
            "signal_sent": True,
            "failure_reason": reason,
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.stop_task_launch",
        fake_stop,
    )

    result = runner.invoke(
        app,
        [
            "scheduler",
            "stop",
            "L0 调度",
            "--reason",
            "operator stop",
            "--force",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["task_id"] == "L0 调度"
    assert captured["reason"] == "operator stop"
    assert captured["force"] is True
    assert "Scheduler task stopped." in result.stdout
    assert "status: failed" in result.stdout
    assert "signal: SIGKILL" in result.stdout
    assert "signal_sent: True" in result.stdout
    assert "reason: operator stop" in result.stdout


def test_scheduler_resume_forwards_options_and_renders_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_resume(self, task_id, *, launch=None):
        captured["task_id"] = task_id
        captured["launch"] = launch
        return {
            "status": "running",
            "launch_command": launch or "bash -lc echo resumed",
            "launch_pid": 54321,
            "launch_log": str(tmp_path / "launch.log"),
            "resume_count": 2,
        }

    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator.resume_task_launch",
        fake_resume,
    )

    result = runner.invoke(
        app,
        [
            "scheduler",
            "resume",
            "L0 调度",
            "--launch",
            "bash -lc echo resumed",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["task_id"] == "L0 调度"
    assert captured["launch"] == "bash -lc echo resumed"
    assert "status: running" in result.stdout
    assert "command: bash -lc echo resumed" in result.stdout
    assert "pid: 54321" in result.stdout
    assert "resume_count: 2" in result.stdout


def test_scheduler_complete_records_runtime_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
        lambda *args, **kwargs: None,
    )

    report_path = tmp_path / "tmp" / "scheduler" / "task-056.json"
    job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
    provisioned_worktree = "/tmp/dimc-worktrees/scheduler-l0-abc12345"
    session_dir = Path(provisioned_worktree) / ".agent" / "sessions" / "l0-调度-auto"
    job_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "scheduler_state.json").write_text(
        (
            "{\n"
            '  "tasks": {\n'
            '    "L0 调度": {\n'
            '      "status": "running",\n'
            '      "job_id": "l0-调度-auto",\n'
            '      "branch": "codex/task-l0-abc12345",\n'
            f'      "worktree": "{provisioned_worktree}",\n'
            f'      "session_dir": "{session_dir}",\n'
            f'      "session_file": "{session_dir / "session.json"}",\n'
            f'      "session_readme": "{session_dir / "README.md"}",\n'
            f'      "durable_session_file": "{job_dir / "session.json"}",\n'
            f'      "job_dir": "{job_dir}",\n'
            f'      "context_file": "{tmp_path / "tmp" / "context" / "L0_调度_context.md"}",\n'
            f'      "task_packet_file": "{tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "tmp" / "coordination" / "task_packets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md").write_text(
        "# packet", encoding="utf-8"
    )
    (job_dir / "task-packet.md").write_text("# packet", encoding="utf-8")

    def fake_run_scheduler_pr_ready(
        repo_root: Path,
        task_id: str,
        *,
        task_packet,
        allow,
        risk,
        base_ref,
        report_file,
        skip_check,
        allow_dirty,
    ):
        assert repo_root == tmp_path
        assert task_id == "L0 调度"
        assert allow == ["src/dimcause/scheduler/"]
        assert risk == ["needs follow-up"]
        assert base_ref == "main"
        assert report_file == report_path
        assert skip_check is False
        assert allow_dirty is False
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text('{"status":"pass"}', encoding="utf-8")
        return "[PR_READY]\nbranch: codex/task-056", report_path

    monkeypatch.setattr("dimcause.cli._run_scheduler_pr_ready", fake_run_scheduler_pr_ready)

    result = runner.invoke(
        app,
        [
            "scheduler",
            "complete",
            "L0 调度",
            "--allow",
            "src/dimcause/scheduler/",
            "--risk",
            "needs follow-up",
            "--report-file",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    runtime_path = tmp_path / ".agent" / "scheduler_state.json"
    assert runtime_path.exists()
    payload = runtime_path.read_text(encoding="utf-8")
    assert '"status": "done"' in payload
    assert '"branch": "codex/task-l0-abc12345"' in payload
    assert provisioned_worktree in payload
    assert '"pr_ready_report": "[PR_READY]\\nbranch: codex/task-056"' in payload
    task_board = tmp_path / "tmp" / "coordination" / "task_board.md"
    assert task_board.exists()
    assert "done" in task_board.read_text(encoding="utf-8")
    assert "codex/task-l0-abc12345" in task_board.read_text(encoding="utf-8")
    assert provisioned_worktree in task_board.read_text(encoding="utf-8")
    assert (job_dir / "pr-ready.md").exists()
    assert (job_dir / "check-report.json").exists()
    assert (job_dir / "job-end.md").exists()
    meta_payload = (job_dir / "meta.json").read_text(encoding="utf-8")
    assert '"status": "done"' in meta_payload
    assert '"branch": "codex/task-l0-abc12345"' in meta_payload
    assert provisioned_worktree in meta_payload
    assert str(session_dir) in meta_payload
    assert str(session_dir / "session.json") in meta_payload
    assert str(job_dir / "session.json") in meta_payload


def test_scheduler_fail_records_failure_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
        lambda *args, **kwargs: None,
    )
    job_dir = tmp_path / "docs" / "logs" / "2026" / "03-08" / "jobs" / "l0-调度-auto"
    provisioned_worktree = "/tmp/dimc-worktrees/scheduler-l0-abc12345"
    session_dir = Path(provisioned_worktree) / ".agent" / "sessions" / "l0-调度-auto"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "task-packet.md").write_text("# packet", encoding="utf-8")
    runtime_dir = tmp_path / ".agent"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "scheduler_state.json").write_text(
        (
            "{\n"
            '  "tasks": {\n'
            '    "L0 调度": {\n'
            '      "status": "running",\n'
            '      "job_id": "l0-调度-auto",\n'
            '      "branch": "codex/task-l0-abc12345",\n'
            f'      "worktree": "{provisioned_worktree}",\n'
            f'      "session_dir": "{session_dir}",\n'
            f'      "session_file": "{session_dir / "session.json"}",\n'
            f'      "session_readme": "{session_dir / "README.md"}",\n'
            f'      "durable_session_file": "{job_dir / "session.json"}",\n'
            f'      "job_dir": "{job_dir}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "scheduler",
            "fail",
            "L0 调度",
            "--reason",
            "verification failed",
        ],
    )

    assert result.exit_code == 0, result.stdout
    runtime_path = tmp_path / ".agent" / "scheduler_state.json"
    payload = runtime_path.read_text(encoding="utf-8")
    assert '"status": "failed"' in payload
    assert '"branch": "codex/task-l0-abc12345"' in payload
    assert provisioned_worktree in payload
    assert '"failure_reason": "verification failed"' in payload
    task_board = tmp_path / "tmp" / "coordination" / "task_board.md"
    assert task_board.exists()
    task_board_body = task_board.read_text(encoding="utf-8")
    assert "verification failed" in task_board_body
    assert "codex/task-l0-abc12345" in task_board_body
    assert provisioned_worktree in task_board_body
    assert (job_dir / "job-end.md").exists()
    assert "verification failed" in (job_dir / "job-end.md").read_text(encoding="utf-8")
    meta_payload = (job_dir / "meta.json").read_text(encoding="utf-8")
    assert '"status": "failed"' in meta_payload
    assert '"branch": "codex/task-l0-abc12345"' in meta_payload
    assert provisioned_worktree in meta_payload
    assert str(session_dir) in meta_payload
    assert str(session_dir / "session.json") in meta_payload
    assert str(job_dir / "session.json") in meta_payload


def test_scheduler_complete_defaults_to_runtime_task_packet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._sync_task_event_to_knowledge",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "dimcause.scheduler.orchestrator.Orchestrator._link_task_lifecycle_events",
        lambda *args, **kwargs: None,
    )

    runtime_dir = tmp_path / ".agent"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    task_packet = tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md"
    task_packet.parent.mkdir(parents=True, exist_ok=True)
    task_packet.write_text("# task packet", encoding="utf-8")
    (runtime_dir / "scheduler_state.json").write_text(
        (
            "{\n"
            '  "tasks": {\n'
            '    "L0 调度": {\n'
            '      "status": "running",\n'
            f'      "task_packet_file": "{task_packet}"\n'
            "    }\n"
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    def fake_run_scheduler_pr_ready(
        repo_root: Path,
        task_id: str,
        *,
        task_packet,
        allow,
        risk,
        base_ref,
        report_file,
        skip_check,
        allow_dirty,
    ):
        assert repo_root == tmp_path
        assert task_id == "L0 调度"
        assert task_packet == Path(
            str(tmp_path / "tmp" / "coordination" / "task_packets" / "L0_调度.md")
        )
        return (
            "[PR_READY]\nbranch: codex/task-065",
            tmp_path / "tmp" / "scheduler" / "task-065.json",
        )

    monkeypatch.setattr("dimcause.cli._run_scheduler_pr_ready", fake_run_scheduler_pr_ready)

    result = runner.invoke(app, ["scheduler", "complete", "L0 调度"])

    assert result.exit_code == 0, result.stdout
