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

            subprocess.run(["git", "init"], cwd=str(root_dir), capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=str(root_dir),
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=str(root_dir),
                check=True,
            )

            yield root_dir, logs_dir

    @pytest.mark.protected
    def test_audit_scan(self, runner, temp_workspace, monkeypatch):
        """测试审计命令"""
        from dimcause.audit.engine import CheckResult
        from dimcause.audit.mode import STANDARD_MODE
        from dimcause.audit.result import AuditResult
        from dimcause.cli import app

        root_dir, logs_dir = temp_workspace

        # 创建一个包含敏感信息的文件，必须在 src 目录下才能被 scanned
        src_dir = root_dir / "src" / "mal"
        src_dir.mkdir(parents=True, exist_ok=True)
        secret_file = src_dir / "config.py"
        secret_file.write_text("API_KEY = 'sk-1234567890'")

        def fake_run_audit(*args, **kwargs):
            return AuditResult(
                mode=STANDARD_MODE,
                success=True,
                exit_code=0,
                raw_results=[
                    CheckResult(
                        check_name="sensitive_data",
                        success=False,
                        is_blocking=False,
                        message="Found 1 items.",
                        details=[f"[HIGH] {secret_file}: Found openai_key (pos: (0, 10))"],
                    )
                ],
            )

        monkeypatch.setattr("dimcause.audit.runner.run_audit", fake_run_audit)

        # 运行 audit
        result = runner.invoke(app, ["audit", str(root_dir)])
        assert result.exit_code == 0

        # 验证是否检测到敏感信息
        assert "SENSITIVE_DATA" in result.stdout
        assert "openai_key" in result.stdout
        assert str(secret_file) in result.stdout
