from unittest.mock import patch

from typer.testing import CliRunner

from dimcause.cli import app

runner = CliRunner()


@patch("dimcause.daemon.process.ProcessManager.start_daemon")
def test_daemon_start_background(mock_start):
    result = runner.invoke(app, ["daemon", "start"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@patch("dimcause.daemon.process.ProcessManager.stop_daemon")
def test_daemon_stop(mock_stop):
    result = runner.invoke(app, ["daemon", "stop"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


@patch("dimcause.daemon.process.ProcessManager.is_running")
@patch("dimcause.daemon.process.ProcessManager.get_pid")
def test_daemon_status_running(mock_pid, mock_running):
    mock_running.return_value = True
    mock_pid.return_value = 12345

    result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "Running (PID: 12345)" in result.stdout


@patch("dimcause.daemon.process.ProcessManager.is_running")
def test_daemon_status_stopped(mock_running):
    mock_running.return_value = False

    result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "Stopped" in result.stdout


@patch("dimcause.daemon.manager.DaemonManager")
def test_daemon_start_foreground(MockManager):
    mock_instance = MockManager.return_value

    # Simulate start --foreground
    result = runner.invoke(app, ["daemon", "start", "--foreground"])

    assert result.exit_code == 0
    MockManager.assert_called_once()
    mock_instance.run.assert_called_once()
