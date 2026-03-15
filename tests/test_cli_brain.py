from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


class TestCliBrain:
    @patch("dimcause.cli.get_analyst")
    @patch("dimcause.storage.MarkdownStore")
    @patch("dimcause.storage.VectorStore")
    @patch("dimcause.storage.GraphStore")
    def test_add_analyze_flow(self, mock_graph, mock_vector, mock_md, mock_get, tmp_path):
        # Mock analyst
        mock_analyst = MagicMock()
        mock_analyst.analyze_input.return_value = {
            "type": "task",
            "tags": ["bug", "ui"],
            "summary": "AI Summary",
        }
        mock_get.return_value = mock_analyst

        # Mock storage
        mock_md_instance = MagicMock()
        mock_md.return_value = mock_md_instance

        # Run add --analyze, simulate "y" for confirmation
        # We need to mock os.path.expanduser to avoid writing to real ~/.dimcause
        with patch("os.path.expanduser", return_value=str(tmp_path)):
            result = runner.invoke(app, ["add", "Fix bug", "--analyze"], input="y\n")

        if result.exit_code != 0:
            print(f"\nCommand failed. Output:\n{result.stdout}")

        assert result.exit_code == 0
        # Check components separately to avoid whitespace issues in Rich output
        stdout_lower = result.stdout.lower()
        assert "ai suggestion" in stdout_lower
        assert "type:" in stdout_lower and "task" in stdout_lower
        assert "tags:" in stdout_lower and "bug" in stdout_lower
        assert "summary:" in stdout_lower and "ai summary" in stdout_lower

        # Verify storage call
        mock_md_instance.save.assert_called_once()
        saved_event = mock_md_instance.save.call_args[0][0]
        assert saved_event.summary == "AI Summary"
        assert saved_event.type.value == "task"

        # Verify analyst called
        mock_analyst.analyze_input.assert_called_with("Fix bug")

    @patch("dimcause.cli.get_analyst")
    @patch("dimcause.cli.get_logs_dir")
    def test_reflect_integration(self, mock_logs_dir, mock_get, tmp_path):
        # Setup fake logs
        logs_root = tmp_path / "logs"
        today_dir = logs_root / "2026" / "01-01"
        today_dir.mkdir(parents=True)
        (today_dir / "log.md").write_text("Work Log", encoding="utf-8")

        mock_logs_dir.return_value = logs_root

        # Mock analyst
        mock_analyst = MagicMock()
        mock_analyst.reflect_on_logs.return_value = "# Report"
        mock_get.return_value = mock_analyst

        # Run
        result = runner.invoke(app, ["reflect", "--date", "2026-01-01"])

        if result.exit_code != 0:
            print(f"Reflect failed:\n{result.stdout}")

        assert result.exit_code == 0
        assert "AI Reflecting" in result.stdout
        # Rich markdown rendering usually hides the '#' but makes text bold
        # We search for "Report" to avoid formatting issues
        assert "Report" in result.stdout

        # Verify call
        args = mock_analyst.reflect_on_logs.call_args[0][0]
        assert "Work Log" in args
