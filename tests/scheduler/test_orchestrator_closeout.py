import json
import subprocess
from pathlib import Path

from dimcause.scheduler.orchestrator import Orchestrator


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo_with_feature_branch(tmp_path: Path, *, branch: str) -> Path:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _write(
        tmp_path / "docs" / "STATUS.md",
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| GOV-1 | 调度治理收口 | 📋 待实现 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        )
        + "\n",
    )
    _write(tmp_path / "docs" / "coordination" / "README.md", "# coordination\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "switch", "-c", branch)
    _write(tmp_path / "docs" / "coordination" / "README.md", "# coordination\n\nupdated\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "update coordination")
    _git(tmp_path, "switch", "main")
    return tmp_path


def _write_runtime_and_task_card(
    repo: Path,
    *,
    task_id: str,
    branch: str,
    task_class: str,
) -> None:
    report_path = repo / "tmp" / "reports" / f"{task_id}.json"
    job_dir = repo / "docs" / "logs" / "2026" / "03-17" / "jobs" / f"{task_id}-auto"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"ok": True}, ensure_ascii=False), encoding="utf-8")
    _write(
        repo / ".agent" / "agent-tasks" / f"agent_{task_id.lower()}_demo.md",
        "\n".join(
            [
                "---",
                "priority: P1",
                "status: Open",
                f"task_class: {task_class}",
                "cli_hint: dimc scheduler",
                "---",
                "",
                f"# Agent Task {task_id}: 调度治理收口",
                "",
                "## 目标",
                "完成调度治理收口。",
                "",
                "## 交付物",
                "- 输出最小交付。",
                "",
                "## 验收标准",
                "- 通过最小验证。",
                "",
                "## Step 规划",
                "1. 准备收口。",
            ]
        )
        + "\n",
    )
    _write(
        repo / ".agent" / "scheduler_state.json",
        json.dumps(
            {
                "tasks": {
                    task_id: {
                        "status": "done",
                        "job_id": f"{task_id.lower()}-auto",
                        "branch": branch,
                        "worktree": str(repo),
                        "job_dir": str(job_dir),
                        "report_path": str(report_path),
                        "pr_ready_report": "[PR_READY]\nbranch: " + branch,
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def _commit_branch_change(repo: Path, branch: str, relpath: str, content: str) -> None:
    _git(repo, "switch", branch)
    _write(repo / relpath, content)
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", f"update {relpath}")
    _git(repo, "switch", "main")


def test_summarize_task_closeout_marks_governance_task_eligible(tmp_path: Path) -> None:
    branch = "codex/ops-gov-closeout"
    repo = _init_repo_with_feature_branch(tmp_path, branch=branch)
    _write_runtime_and_task_card(repo, task_id="GOV-1", branch=branch, task_class="governance")

    orchestrator = Orchestrator(project_root=repo)
    summary = orchestrator.summarize_task_closeout("GOV-1")

    assert summary["eligible"] is True
    assert summary["task_class"] == "governance"
    assert summary["closeout_policy"] == "auto"
    assert summary["ahead_behind"] == {"base_only": 0, "branch_only": 1}


def test_auto_closeout_task_merges_branch_and_updates_runtime(tmp_path: Path) -> None:
    branch = "codex/ops-gov-closeout"
    repo = _init_repo_with_feature_branch(tmp_path, branch=branch)
    _write_runtime_and_task_card(repo, task_id="GOV-1", branch=branch, task_class="governance")

    orchestrator = Orchestrator(project_root=repo)
    result = orchestrator.auto_closeout_task("GOV-1")

    assert result["closeout_status"] == "merged"
    counts = _git(repo, "rev-list", "--left-right", "--count", f"main...{branch}")
    assert counts == "0\t0" or counts == "0 0"
    runtime = orchestrator.get_task_runtime("GOV-1")
    assert runtime is not None
    assert runtime["closeout_status"] == "merged"
    assert runtime["closeout_branch"] == branch
    task_board = (repo / "tmp" / "coordination" / "task_board.md").read_text(encoding="utf-8")
    assert "| GOV-1 | 调度治理收口 |" in task_board
    assert "| merged |" in task_board


def test_summarize_task_closeout_blocks_implementation_task_by_default(tmp_path: Path) -> None:
    branch = "codex/task-impl-closeout"
    repo = _init_repo_with_feature_branch(tmp_path, branch=branch)
    _commit_branch_change(repo, branch, "src/app.py", "print('impl')\n")
    _write_runtime_and_task_card(repo, task_id="IMPL-1", branch=branch, task_class="implementation")

    orchestrator = Orchestrator(project_root=repo)
    summary = orchestrator.summarize_task_closeout("IMPL-1")

    assert summary["eligible"] is False
    assert "task_class_not_low_risk" in summary["blocking_reasons"]
    assert "missing_progress_doc_sync" in summary["blocking_reasons"]
    assert summary["progress_doc_sync_required"] is True
    assert summary["progress_doc_sync_ok"] is False


def test_summarize_task_closeout_blocks_implementation_without_progress_docs(
    tmp_path: Path,
) -> None:
    branch = "codex/task-impl-closeout"
    repo = _init_repo_with_feature_branch(tmp_path, branch=branch)
    _commit_branch_change(repo, branch, "src/app.py", "print('impl')\n")
    _write_runtime_and_task_card(repo, task_id="IMPL-1", branch=branch, task_class="implementation")

    orchestrator = Orchestrator(project_root=repo)
    summary = orchestrator.summarize_task_closeout("IMPL-1", allow_implementation=True)

    assert summary["eligible"] is False
    assert summary["blocking_reasons"] == ["missing_progress_doc_sync"]
    assert "src/app.py" in summary["changed_files"]
    assert summary["progress_docs_touched"] == []


def test_summarize_task_closeout_allows_implementation_with_progress_docs(
    tmp_path: Path,
) -> None:
    branch = "codex/task-impl-closeout"
    repo = _init_repo_with_feature_branch(tmp_path, branch=branch)
    _commit_branch_change(repo, branch, "src/app.py", "print('impl')\n")
    _commit_branch_change(
        repo,
        branch,
        "docs/STATUS.md",
        "\n".join(
            [
                "# Status",
                "",
                "## 3. V6.1 进度 (审计修复与 Production Polish)",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| IMPL-1 | 产品实现收口 | ✅ 已完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        )
        + "\n",
    )
    _write_runtime_and_task_card(repo, task_id="IMPL-1", branch=branch, task_class="implementation")

    orchestrator = Orchestrator(project_root=repo)
    summary = orchestrator.summarize_task_closeout("IMPL-1", allow_implementation=True)

    assert summary["eligible"] is True
    assert summary["progress_doc_sync_required"] is True
    assert summary["progress_doc_sync_ok"] is True
    assert "docs/STATUS.md" in summary["progress_docs_touched"]
