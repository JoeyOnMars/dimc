from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dimcause.cli_graph import app
from dimcause.core.models import Event, EventType

runner = CliRunner()


@pytest.fixture
def mock_index():
    with patch("dimcause.cli_graph.EventIndex") as MockIndex:
        index_instance = MockIndex.return_value
        # Mock query results
        mock_event_data = [
            {"id": "e1", "type": "decision", "summary": "Review Code"},
            {"id": "e2", "type": "commit", "summary": "Fix Bug"},
        ]
        index_instance.query.return_value = mock_event_data

        # Mock load_event
        def side_effect(eid):
            if eid == "e1":
                return Event(
                    id="e1",
                    type=EventType.DECISION,
                    timestamp="2023-10-27T10:00:00",
                    summary="Review Code",
                    content="...",
                )
            if eid == "e2":
                return Event(
                    id="e2",
                    type=EventType.GIT_COMMIT,
                    timestamp="2023-10-27T11:00:00",
                    summary="Fix Bug",
                    content="...",
                )
            return None

        index_instance.load_event.side_effect = side_effect

        # Mock get_links
        from dimcause.reasoning.causal import CausalLink

        index_instance.get_links.return_value = [
            CausalLink(source="e2", target="e1", relation="realizes")
        ]

        yield index_instance


@pytest.fixture
def mock_engine():
    with patch("dimcause.cli_graph.HybridInferenceEngine") as MockEngine:
        engine_instance = MockEngine.return_value
        from dimcause.reasoning.causal import CausalLink

        engine_instance.infer.return_value = [
            CausalLink(source="e2", target="e1", relation="realizes")
        ]
        yield engine_instance


@pytest.fixture
def mock_validator():
    with patch("dimcause.cli_graph.AxiomValidator") as MockValidator:
        validator_instance = MockValidator.return_value
        # Default: no violations
        validator_instance.validate.return_value = []
        yield validator_instance


def test_build_dry_run(mock_index, mock_engine):
    """Test graph build command in dry-run mode"""
    result = runner.invoke(app, ["build", "--dry-run"])
    assert result.exit_code == 0
    assert "正在构建因果图谱" in result.stdout
    assert "推断出 1 个因果链接" in result.stdout
    assert "空跑模式" in result.stdout

    # Check index.add was NOT called
    mock_index.add.assert_not_called()


def test_build_save(mock_index, mock_engine):
    """Test graph build command saves links"""
    result = runner.invoke(app, ["build"])  # dry-run=False default
    assert result.exit_code == 0
    assert "已更新 1 个事件" in result.stdout

    # Check index.add WAS called
    mock_index.add.assert_called()


def test_show_ascii(mock_index):
    """Test graph show command with ascii format"""
    import networkx as nx
    mock_g = nx.DiGraph()
    mock_g.add_node("e1", type="decision")
    mock_g.add_node("e2", type="commit")
    mock_g.add_edge("e2", "e1", relation="realizes")

    with patch("dimcause.cli_graph.GraphStore") as MockStore:
        MockStore.return_value._graph = mock_g
        result = runner.invoke(app, ["show", "--format", "ascii"])

    assert result.exit_code == 0
    assert "Graph Summary" in result.stdout
    assert "Nodes: 2" in result.stdout
    assert "Edges: 1" in result.stdout


def test_show_mermaid(mock_index):
    """Test graph show command with mermaid format"""
    import networkx as nx
    mock_g = nx.DiGraph()
    mock_g.add_node("e1", type="decision")
    mock_g.add_node("e2", type="commit")
    mock_g.add_edge("e2", "e1", relation="realizes")

    with patch("dimcause.cli_graph.GraphStore") as MockStore:
        MockStore.return_value._graph = mock_g
        result = runner.invoke(app, ["show", "--format", "mermaid"])

    assert result.exit_code == 0
    assert "graph TD" in result.stdout
    assert "e2 -- realizes --> e1" in result.stdout


def test_check_valid(mock_index, mock_validator):
    """Test graph check command with no violations"""
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "✅ 未发现公理违规" in result.stdout


def test_check_violations(mock_index, mock_validator):
    """Test graph check command with violations"""
    from dimcause.reasoning.validator import ValidationResult, ValidationSeverity

    mock_validator.validate.return_value = [
        ValidationResult(
            axiom_id="test_axiom",
            severity=ValidationSeverity.ERROR,
            message="Test Violation",
            entity_id="e1",
            details={},
        )
    ]

    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "发现 1 个违规项" in result.stdout
    assert "Test Violation" in result.stdout
