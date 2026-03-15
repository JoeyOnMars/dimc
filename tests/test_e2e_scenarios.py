"""
扩展的端到端 CLI 场景测试
"""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner


class TestCLIE2EScenarios:
    """CLI 级端到端场景测试"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def temp_workspace(self, monkeypatch):
        """创建完整的临时工作区"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            # Patch dimcause.cli local helpers
            monkeypatch.setattr("dimcause.cli.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.cli.get_logs_dir", lambda: logs_dir)

            # Patch dimcause.core modules (used by internal logic called by CLI)
            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )
            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: root_dir)

            # 初始化真实的 Git 仓库以支持 git 操作测试
            import subprocess

            subprocess.run(["git", "init"], cwd=str(root_dir), capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(root_dir))
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(root_dir))

            yield root_dir, logs_dir

    @pytest.mark.skip(reason="daily-start/daily-end 命令已从 CLI 移除，测试需要重写以匹配新工作流")
    def test_day_handover_scenario(self, runner, temp_workspace, monkeypatch):
        """测试 Day 1 到 Day 2 的交接流程"""
        from dimcause.cli import app

        root_dir, logs_dir = temp_workspace

        # === Day 1 ===
        day1_str = "2026-01-15"
        # Patch BOTH CLI local and core functions
        monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: day1_str)
        monkeypatch.setattr(
            "dimcause.services.workflow.get_today_dir", lambda: logs_dir / "2026" / "01-15"
        )
        monkeypatch.setattr("dimcause.cli.get_today_str", lambda: day1_str)
        monkeypatch.setattr("dimcause.cli.get_today_dir", lambda: logs_dir / "2026" / "01-15")

        # 1. Start Day 1
        result = runner.invoke(app, ["daily-start"], input="y\n")
        assert result.exit_code == 0

        # 2. Start Job
        result = runner.invoke(app, ["job-start", "feat-auth"])
        assert result.exit_code == 0

        # 3. End Job
        # 模拟 job-end 后的文件编辑
        day1_dir = logs_dir / "2026" / "01-15"
        job_dir = day1_dir / "jobs" / "feat-auth"
        job_dir.mkdir(parents=True, exist_ok=True)  # Ensure dir exists if mock missed it

        # Run job-end
        result = runner.invoke(app, ["job-end", "feat-auth"])
        assert result.exit_code == 0

        # 修改 end.md 模拟遗留问题
        job_end_path = job_dir / "end.md"
        if job_end_path.exists():
            content = job_end_path.read_text()
            content = content.replace("## [遗留]\n- ", "## [遗留]\n- Fix critical bug\n")
            job_end_path.write_text(content)

        # 4. End Day 1
        # 需要确认导出(y) 和 选择Git提交方式(1: 直接提交)
        result = runner.invoke(app, ["daily-end"], input="y\n1\n")
        assert result.exit_code == 0

        # 验证 Day 1 Summary 包含该 item
        # Implementation Note: daily-end creates a template, it does NOT auto-aggregate job todos into the file.
        # So checking file content here is wrong unless we simulate user editing it.
        # But we want to verify context propagation, so we rely on daily-start reading the job log directly.

        # === Day 2 ===
        day2_str = "2026-01-16"
        monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: day2_str)
        monkeypatch.setattr(
            "dimcause.services.workflow.get_today_dir", lambda: logs_dir / "2026" / "01-16"
        )
        monkeypatch.setattr("dimcause.cli.get_today_str", lambda: day2_str)
        monkeypatch.setattr("dimcause.cli.get_today_dir", lambda: logs_dir / "2026" / "01-16")

        # 5. Start Day 2
        # 此时应读取到 Day 1 的 Context (from Job end log)
        result = runner.invoke(app, ["daily-start"], input="y\n")
        assert result.exit_code == 0
        assert "Fix critical bug" in result.stdout

        # 验证 Day 2 start.md 包含待办
        # Note: current implementation prints todos to console but does not auto-fill file.
        # day2_start_path = logs_dir / "2026" / "01-16" / "start.md"
        # assert "Fix critical bug" in day2_start_path.read_text()

    @pytest.mark.skip(reason="audit 扫描真实代码库，lint/format/sensitive_data 问题导致 exit_code=1，不适合自动化断言")
    def test_audit_scan(self, runner, temp_workspace, monkeypatch):
        """测试审计命令"""

        from dimcause.cli import app

        root_dir, logs_dir = temp_workspace

        # Mock subprocess.run to avoid running real tests
        class MockProcess:
            returncode = 0
            stdout = "100 passed"
            stderr = ""

        def mock_run(*args, **kwargs):
            return MockProcess()

        monkeypatch.setattr("subprocess.run", mock_run)

        # 创建一个包含敏感信息的文件，必须在 src 目录下才能被 scanned
        src_dir = root_dir / "src" / "mal"
        src_dir.mkdir(parents=True, exist_ok=True)
        secret_file = src_dir / "config.py"
        secret_file.write_text("API_KEY = 'sk-1234567890'")

        # 运行 audit
        result = runner.invoke(app, ["audit"])
        assert result.exit_code == 0

        # 验证是否检测到敏感信息
        # audit 输出通常包含警告
        assert "敏感信息" in result.stdout or "Potential sensitive" in result.stdout
