import networkx as nx
import pytest

from dimcause.reasoning.validator import AxiomValidator, ValidationSeverity


class TestAxiomValidator:
    @pytest.fixture
    def validator(self):
        return AxiomValidator()

    def test_commit_must_have_cause_valid(self, validator):
        """测试合规的 Commit"""
        g = nx.DiGraph()
        g.add_node("c1", type="commit")
        g.add_node("d1", type="decision")
        g.add_edge("c1", "d1", relation="realizes")

        results = validator.validate(g)
        assert len(results) == 0

    def test_commit_must_have_cause_invalid(self, validator):
        """测试缺少因果的 Commit"""
        g = nx.DiGraph()
        g.add_node("c1", type="commit")
        # 孤立 Commit

        results = validator.validate(g)
        assert len(results) == 1
        assert results[0].axiom_id == "commit_must_have_cause"
        assert results[0].severity == ValidationSeverity.WARNING

    def test_commit_fix_incident_valid(self, validator):
        """测试修复 Incident 的 Commit"""
        g = nx.DiGraph()
        g.add_node("c1", type="commit")
        g.add_node("i1", type="incident")
        g.add_edge("c1", "i1", relation="fixes")

        results = validator.validate(g)
        assert len(results) == 0

    def test_decision_cycle_valid(self, validator):
        """测试无环 Decision flow"""
        g = nx.DiGraph()
        g.add_node("d1", type="decision")
        g.add_node("d2", type="decision")
        g.add_node("d3", type="decision")
        g.add_edge("d2", "d1", relation="overrides")
        g.add_edge("d3", "d2", relation="overrides")

        results = validator.validate(g)
        assert len(results) == 0

    def test_decision_cycle_invalid(self, validator):
        """测试有环 Decision flow"""
        g = nx.DiGraph()
        g.add_node("d1", type="decision")
        g.add_node("d2", type="decision")
        g.add_edge("d2", "d1", relation="overrides")
        g.add_edge("d1", "d2", relation="overrides")  # 环

        results = validator.validate(g)
        assert len(results) == 1
        assert results[0].axiom_id == "no_decision_cycle"
        assert results[0].severity == ValidationSeverity.ERROR

    def test_function_traceability_valid(self, validator):
        """测试可追溯的 Function"""
        g = nx.DiGraph()
        g.add_node("f1", type="function")
        g.add_node("c1", type="commit")
        g.add_node("d1", type="decision")

        # c1 modifies f1
        g.add_edge("c1", "f1", relation="modifies")
        # c1 realizes d1
        g.add_edge("c1", "d1", relation="realizes")

        results = validator.validate(g)
        assert len(results) == 0

    def test_function_traceability_invalid(self, validator):
        """测试不可追溯的 Function"""
        g = nx.DiGraph()
        g.add_node("f1", type="function")
        g.add_node("c1", type="commit")

        # c1 modifies f1
        g.add_edge("c1", "f1", relation="modifies")

        # Make c1 valid per Rule 4.1 (fixes incident), but invalid per Rule 4.3 (no decision)
        g.add_node("i1", type="incident")
        g.add_edge("c1", "i1", relation="fixes")

        results = validator.validate(g)
        assert len(results) == 1
        assert results[0].axiom_id == "function_traceability"
