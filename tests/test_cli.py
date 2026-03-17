import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


class TestCLI(unittest.TestCase):
    def setUp(self):
        # Setup temp environment
        self.test_dir = Path("./temp_test_cli").resolve()
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        # Mock .dimcause directory
        self.dimcause_dir = Path("~/.dimcause_test").expanduser()
        self.dimcause_dir.mkdir(parents=True, exist_ok=True)

        # Patch paths in CLI if possible, or just rely on relative paths in tests
        pass

    def tearDown(self):
        os.chdir(self.original_cwd)
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        if self.dimcause_dir.exists():
            shutil.rmtree(self.dimcause_dir)

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Dimcause", result.stdout)

    # ... (other tests unchanged) ...

    @patch("dimcause.cli.show_interactive_menu")
    @patch("dimcause.core.event_index.EventIndex")
    @patch("dimcause.storage.MarkdownStore")
    @patch("dimcause.core.models.Event")
    def test_log_command(self, mock_event_cls, mock_store_cls, mock_index_cls, mock_menu):
        # add 命令替代了旧的 log 命令
        mock_instance = mock_event_cls.return_value
        mock_instance.id = "test_id"
        mock_instance.type.value = "decision"

        mock_store = mock_store_cls.return_value
        mock_store.save.return_value = "/tmp/test.md"

        result = runner.invoke(app, ["add", "Test log content", "--type", "decision"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Logged", result.stdout)

    def test_timeline_command(self):
        result = runner.invoke(app, ["timeline", "--limit", "1"])
        self.assertEqual(result.exit_code, 0)

    def test_trace_command(self):
        # Trace requires DB, which might be empty
        result = runner.invoke(app, ["trace", "something", "--limit", "1"])
        # Should not crash even if empty
        self.assertEqual(result.exit_code, 0)

    def test_daily_start(self):
        # daily-start 命令已改名为 up，且包含交互式操作
        with (
            patch("dimcause.daemon.process.process_manager.is_running", return_value=True),
            patch("dimcause.utils.state.check_pending_merge", return_value=None),
            patch("dimcause.utils.state.check_orphan_jobs", return_value=[]),
            patch("dimcause.cli._fetch_tasks", return_value=[]),
            patch("dimcause.utils.state.get_last_session", return_value=None),
            patch("dimcause.cli._create_daily_log"),
        ):
            result = runner.invoke(app, ["up"])
            self.assertEqual(result.exit_code, 0)

    @patch("dimcause.cli.get_analyst")
    def test_reflect(self, mock_get_analyst):
        # reflect 命令会检查日志目录是否存在
        mock_analyst = mock_get_analyst.return_value
        mock_analyst.reflect_on_logs.return_value = "Mock Reflection"

        result = runner.invoke(app, ["reflect", "--date", "today"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("AI Reflecting on", result.stdout)

    @patch("dimcause.core.stats.get_stats")
    def test_stats(self, mock_get_stats):
        # Configure mock
        mock_get_stats.return_value = {"total_logs": 10, "active_days": 5, "completed_jobs": 2}

        result = runner.invoke(app, ["stats"])

        if result.exit_code != 0:
            print(result.stdout)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("10", result.stdout)

    def test_migrate(self):
        # Dry run migration on temp dir
        result = runner.invoke(app, ["migrate", ".", "--dry-run"])
        if result.exit_code != 0:
            print(result.stdout)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Files Scanned", result.stdout)


if __name__ == "__main__":
    unittest.main()
