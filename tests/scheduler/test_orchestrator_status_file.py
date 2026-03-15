from pathlib import Path

from dimcause.scheduler.orchestrator import Orchestrator, TaskPriority, TaskStatus


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_state_prefers_modern_status_and_parses_v61_progress_table(tmp_path: Path) -> None:
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
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成（基础调度循环已实现） |",
                "| L1 自动化 | dimc detect IDE 探测 | 📋 待实现 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )
    _write(
        tmp_path / "docs" / "V5.2" / "STATUS-5.2-001.md",
        "\n".join(
            [
                "| ID | Name | CLI | Status |",
                "|:---|:---|:---|:---|",
                "| H1 | History | `dimc history` | Done |",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    state = orchestrator.load_state()

    assert "error" not in state
    assert "L0 调度" in state["tasks"]
    assert "H1" not in state["tasks"]
    assert state["tasks"]["L0 调度"].status == TaskStatus.IN_PROGRESS
    assert state["tasks"]["L0 调度"].cli == "dimc scheduler"
    assert state["tasks"]["L1 自动化"].status == TaskStatus.PLANNED
    assert state["tasks"]["L1 自动化"].cli == "dimc detect"


def test_load_state_returns_error_when_only_legacy_status_exists(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "V5.2" / "STATUS-5.2-001.md",
        "\n".join(
            [
                "| ID | Name | CLI | Status |",
                "|:---|:---|:---|:---|",
                "| H1 | History | `dimc history` | Done |",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    state = orchestrator.load_state()

    assert "error" in state
    assert "docs/STATUS.md" in state["error"]


def test_load_state_returns_error_if_no_status_file(tmp_path: Path) -> None:
    orchestrator = Orchestrator(project_root=tmp_path)
    state = orchestrator.load_state()

    assert "error" in state
    assert "docs/STATUS.md" in state["error"]


def test_runtime_state_overlay_marks_task_done_and_excludes_it_from_next_task(
    tmp_path: Path,
) -> None:
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
                "| L0 调度 | Scheduler completion | 📋 待实现 |",
                "| L1 自动化 | Detect tools | 📋 待实现 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    orchestrator.record_task_completed(
        "L0 调度",
        pr_ready_report="[PR_READY]\nbranch: codex/task-056",
        report_path=tmp_path / "tmp" / "scheduler" / "task-056.json",
    )

    state = orchestrator.load_state()

    assert state["tasks"]["L0 调度"].status == TaskStatus.DONE
    assert orchestrator.get_next_task().id == "L1 自动化"


def test_runtime_state_overlay_marks_task_failed_as_blocked(tmp_path: Path) -> None:
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
                "| L0 调度 | Scheduler completion | 📋 待实现 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    runtime = orchestrator.record_task_failed("L0 调度", reason="pr_ready failed")
    state = orchestrator.load_state()

    assert runtime["status"] == "failed"
    assert runtime["failure_reason"] == "pr_ready failed"
    assert state["tasks"]["L0 调度"].status == TaskStatus.BLOCKED


def test_load_task_card_falls_back_to_synthetic_status_card(tmp_path: Path) -> None:
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
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    orchestrator.load_state()

    task_card = orchestrator.load_task_card("L0 调度")

    assert task_card["synthetic"] is True
    assert task_card["path"] == "docs/STATUS.md (synthetic task card)"
    assert "src/dimcause/scheduler/orchestrator.py" in task_card["related_files"]


def test_generate_task_prompt_uses_synthetic_status_card_when_no_agent_task_exists(
    tmp_path: Path,
) -> None:
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
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    prompt = orchestrator.generate_task_prompt("L0 调度", include_code=False)

    assert "❌ 任务卡加载失败" not in prompt
    assert "docs/STATUS.md (synthetic task card)" in prompt
    assert "当前没有独立任务卡" in prompt


def test_load_state_infers_priority_from_modern_status_prefix(tmp_path: Path) -> None:
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
                "| P0-Safety | 移除高风险写路径 | 📋 待修复 |",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    state = orchestrator.load_state()

    assert state["tasks"]["P0-Safety"].priority == TaskPriority.P0
    assert state["tasks"]["L0 调度"].priority == TaskPriority.P2


def test_agent_task_frontmatter_priority_overrides_default_priority(tmp_path: Path) -> None:
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
                "| H1 | History | 📋 待实现 |",
                "",
                "## 4. 核心模块状态（代码验证）",
            ]
        ),
    )
    _write(
        tmp_path / ".agent" / "agent-tasks" / "agent_h1_demo.md",
        "\n".join(
            [
                "---",
                "priority: P0",
                "---",
                "",
                "# Agent Task H1: History",
            ]
        ),
    )

    orchestrator = Orchestrator(project_root=tmp_path)
    state = orchestrator.load_state()

    assert state["tasks"]["H1"].priority == TaskPriority.P0
