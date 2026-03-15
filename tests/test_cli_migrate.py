"""
Tests for 'mal migrate' CLI command.
"""

import pytest
from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


class TestCliMigrate:
    @pytest.fixture
    def workspace(self, tmp_path):
        """Setup a temporary workspace with mixed files"""
        logs = tmp_path / "logs"
        logs.mkdir()

        # v1 file
        (logs / "v1.md").write_text(
            "---\ndate: 2026-01-01\ntype: test\n---\nBody", encoding="utf-8"
        )

        # v2 file
        (logs / "v2.md").write_text(
            "---\nschema_version: 2\nid: x\ntimestamp: 2026\n---\nBody", encoding="utf-8"
        )

        # invalid file
        (logs / "broken.md").write_text("NOT YAML", encoding="utf-8")

        return logs

    def test_migrate_dry_run_default(self, workspace):
        """测试默认行为是 Dry Run"""
        result = runner.invoke(app, ["migrate", str(workspace)])

        assert result.exit_code == 0
        assert "Running Migration DRY RUN" in result.output

        # Remove whitespace for table matching
        output_clean = result.output.replace(" ", "")
        assert "FilesScanned3" in output_clean
        assert "NeedsMigration1" in output_clean

        # Verify no files changed
        assert "date: 2026-01-01" in (workspace / "v1.md").read_text()
        assert not list(workspace.glob("*.backup"))

    def test_migrate_real_run(self, workspace):
        """测试实际执行迁移"""
        result = runner.invoke(app, ["migrate", str(workspace), "--no-dry-run"])

        assert result.exit_code == 0
        assert "Running Migration REAL RUN" in result.output

        output_clean = result.output.replace(" ", "")
        assert "Migrated1" in output_clean

        # Verify migration
        content = (workspace / "v1.md").read_text()
        assert "schema_version: 2" in content

        # Verify Backup
        assert (workspace / "v1.md.v1.backup").exists()

    def test_migrate_no_backup(self, workspace):
        """测试禁用备份"""
        result = runner.invoke(app, ["migrate", str(workspace), "--no-dry-run", "--no-backup"])

        assert result.exit_code == 0
        assert "Backup: False" in result.output

        output_clean = result.output.replace(" ", "")
        assert "Migrated1" in output_clean

        # Verify NO Backup
        assert not list(workspace.glob("*.backup"))

    def test_migrate_file_target(self, workspace):
        """测试指定单个文件"""
        target = workspace / "v1.md"
        result = runner.invoke(app, ["migrate", str(target), "--no-dry-run"])

        assert result.exit_code == 0
        # The output depends on CLI implementation details.
        # Since I'm using print in CLI, let's check for keywords.
        assert "Migrated" in result.output and "1 file" in result.output
