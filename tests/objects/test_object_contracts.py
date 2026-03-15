from dimcause.core.models import Event
from dimcause.objects.contracts import (
    Check,
    CheckStatus,
    Claim,
    ClaimStatus,
    Material,
    Relation,
    RelationDirectionality,
    RelationState,
    RelationStateHistoryEntry,
    Result,
    ResultOutcome,
)


def test_minimum_object_family_contracts_are_independent_from_event():
    assert not issubclass(Material, Event)
    assert not issubclass(Claim, Event)
    assert not issubclass(Relation, Event)
    assert not issubclass(Check, Event)
    assert not issubclass(Result, Event)


def test_material_claim_relation_check_result_can_be_instantiated_minimally():
    material = Material(
        id="mat-1", material_type="markdown", source_ref="docs/logs/2026/03-13/start.md"
    )
    claim = Claim(
        id="claim-1",
        claim_type="decision_claim",
        statement="这次修改由运行内核收口驱动",
        target_refs=["mat-1"],
        status=ClaimStatus.PROPOSED,
    )
    relation = Relation(
        id="rel-1",
        relation_type="supports",
        from_ref="claim-1",
        to_ref="mat-1",
        directionality=RelationDirectionality.DIRECTED,
        state=RelationState.CANDIDATE,
        state_history=[
            RelationStateHistoryEntry(
                state=RelationState.CANDIDATE,
                changed_at="2026-03-13T10:00:00",
            )
        ],
    )
    check = Check(
        id="check-1",
        check_type="consistency_check",
        target_refs=["claim-1", "rel-1"],
        status=CheckStatus.PENDING,
    )
    result = Result(
        id="result-1",
        result_type="check_result",
        producer_ref="check-1",
        target_refs=["claim-1"],
        outcome=ResultOutcome.UNKNOWN,
    )

    assert material.object_family == "material"
    assert claim.object_family == "claim"
    assert relation.object_family == "relation"
    assert check.object_family == "check"
    assert result.object_family == "result"


def test_relation_keeps_directionality_and_state_history_slots():
    relation = Relation(
        id="rel-1",
        relation_type="supports",
        from_ref="claim-1",
        to_ref="material-1",
        directionality=RelationDirectionality.UNDIRECTED,
        state=RelationState.SUPPORTED,
        state_history=[
            RelationStateHistoryEntry(
                state=RelationState.CANDIDATE,
                changed_at="2026-03-13T10:00:00",
            ),
            RelationStateHistoryEntry(
                state=RelationState.SUPPORTED,
                changed_at="2026-03-13T10:05:00",
            ),
        ],
        grade_refs={"evidence": "E2", "causality": "C2"},
    )

    assert relation.directionality == RelationDirectionality.UNDIRECTED
    assert [entry.state for entry in relation.state_history] == [
        RelationState.CANDIDATE,
        RelationState.SUPPORTED,
    ]
    assert relation.grade_refs == {"evidence": "E2", "causality": "C2"}


def test_check_and_result_keep_status_and_outcome_as_independent_contracts():
    check = Check(id="check-1", check_type="review_gate", status=CheckStatus.RUNNING)
    result = Result(id="result-1", result_type="review_result", outcome=ResultOutcome.PARTIAL)

    assert check.status == CheckStatus.RUNNING
    assert result.outcome == ResultOutcome.PARTIAL
