from unittest.mock import MagicMock, patch

from dimcause.audit.mode import AuditMode
from dimcause.audit.runner import run_audit
from dimcause.reasoning.validator import ValidationResult, ValidationSeverity


@patch("dimcause.audit.runner.AuditEngine")
@patch("dimcause.audit.runner.GraphStore")
@patch("dimcause.audit.runner.AxiomValidator")
def test_audit_runs_causal_validation(MockValidator, MockGraphStore, MockEngine):
    # Setup
    mock_engine_instance = MockEngine.return_value
    mock_engine_instance.run_all.return_value = []  # No linter errors

    mock_store = MockGraphStore.return_value
    mock_store._graph = MagicMock()  # Non-empty graph
    mock_store._graph.__len__.return_value = 10

    mock_validator = MockValidator.return_value
    expected_issue = ValidationResult(
        axiom_id="R1", severity=ValidationSeverity.ERROR, message="Test Failure", entity_id="E1"
    )
    mock_validator.validate.return_value = [expected_issue]

    # Run
    result = run_audit([], mode=AuditMode.STANDARD)

    # Verify
    assert len(result.causal_issues) == 1
    assert result.causal_issues[0] == expected_issue
    MockValidator.return_value.validate.assert_called_once()
