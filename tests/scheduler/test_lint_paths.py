from pathlib import Path

from dimcause.scheduler.lint import ProjectLinter, run_lint


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_status_file_prefers_v6_status(tmp_path: Path) -> None:
    modern = tmp_path / "docs" / "STATUS.md"
    legacy = tmp_path / "docs" / "V5.2" / "STATUS-5.2-001.md"
    _write(modern, "# modern")
    _write(legacy, "# legacy")

    linter = ProjectLinter(project_root=tmp_path)

    assert linter._resolve_status_file() == modern


def test_resolve_status_file_returns_none_when_modern_status_missing(tmp_path: Path) -> None:
    legacy = tmp_path / "docs" / "V5.2" / "STATUS-5.2-001.md"
    _write(legacy, "# legacy")

    linter = ProjectLinter(project_root=tmp_path)

    assert linter._resolve_status_file() is None


def test_check_cli_implementation_uses_dimcause_cli_path(tmp_path: Path) -> None:
    cli_file = tmp_path / "src" / "dimcause" / "cli.py"
    _write(
        cli_file,
        "\n".join(
            [
                "def daily_start(): pass",
                "def daily_end(): pass",
                "def job_start(): pass",
                "def job_end(): pass",
                "def search(): pass",
                "def why(): pass",
            ]
        ),
    )

    linter = ProjectLinter(project_root=tmp_path)
    linter._check_cli_implementation()

    assert linter.report.checks_passed == 1
    assert not any(issue.message.startswith("CLI 文件不存在") for issue in linter.report.issues)


def test_run_lint_accepts_target_path_keyword(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "STATUS.md",
        "\n".join(
            [
                "## 3. V6.1 进度",
                "",
                "| 任务 | 内容 | 状态 |",
                "|:---|:---|:---|",
                "| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成 |",
                "",
                "## 4. 核心模块状态",
            ]
        ),
    )
    _write(
        tmp_path / "src" / "dimcause" / "cli.py",
        "\n".join(
            [
                "def daily_start(): pass",
                "def daily_end(): pass",
                "def job_start(): pass",
                "def job_end(): pass",
                "def search(): pass",
                "def why(): pass",
            ]
        ),
    )

    report = run_lint(target_path=tmp_path)

    assert report is not None
