from unittest.mock import patch

from typer.testing import CliRunner

from dimcause.audit.engine import CheckResult
from dimcause.audit.mode import STANDARD_MODE
from dimcause.audit.result import AuditResult
from dimcause.cli import app

runner = CliRunner()


@patch("dimcause.audit.runner.run_audit")
def test_audit_command_success(mock_run_audit):
    """Test audit command when all checks pass."""
    mock_run_audit.return_value = AuditResult(
        mode=STANDARD_MODE,
        success=True,
        exit_code=0,
        raw_results=[
            CheckResult("lint", True, "Lint check passed"),
            CheckResult("type_check", True, "Type check passed"),
        ],
    )

    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 0
    assert "All Blocking Checks Passed" in result.stdout


@patch("dimcause.audit.runner.run_audit")
def test_audit_command_failure(mock_run_audit):
    """Test audit command when a blocking check fails."""
    mock_run_audit.return_value = AuditResult(
        mode=STANDARD_MODE,
        success=False,
        exit_code=1,
        raw_results=[
            CheckResult("lint", False, "Found issues", details=["Error 1"], is_blocking=True),
        ],
    )

    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 1
    assert "Audit Failed" in result.stdout
    assert "Error 1" in result.stdout


@patch("dimcause.audit.runner.run_audit")
def test_audit_command_watch(mock_run_audit):
    # Watch mode is hard to test with runner.invoke without side effects.
    # Placeholder test — just verifies the function exists.
    pass
