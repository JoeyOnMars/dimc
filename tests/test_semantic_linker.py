from datetime import datetime, timedelta

import numpy as np

from dimcause.core.models import Event, EventType
from dimcause.reasoning.semantic_linker import SemanticLinker


class _FakeModel:
    def __init__(self, embeddings):
        self._embeddings = np.array(embeddings, dtype=float)

    def encode(self, texts, normalize_embeddings=True):
        return self._embeddings


def _make_event(event_id: str, event_type: EventType, summary: str) -> Event:
    return Event(
        id=event_id,
        type=event_type,
        timestamp=datetime.now(),
        summary=summary,
        content=summary,
    )


def test_semantic_linker_emits_only_ontology_backed_relations():
    linker = SemanticLinker(model_name="test-model")
    linker._model = _FakeModel([[1.0, 0.0], [1.0, 0.0]])

    decision = _make_event("evt_decision", EventType.DECISION, "Adopt precise scheduler gating")
    requirement = _make_event(
        "evt_requirement",
        EventType.REQUIREMENT,
        "Scheduler gate must validate PR readiness",
    )

    links = linker.link([decision, requirement], threshold=0.8)

    assert len(links) == 1
    assert links[0].relation == "implements"
    assert links[0].source == "evt_decision"
    assert links[0].target == "evt_requirement"


def test_semantic_linker_skips_pairs_without_valid_ontology_relation():
    linker = SemanticLinker(model_name="test-model")
    linker._model = _FakeModel([[1.0, 0.0], [1.0, 0.0]])

    discussion = _make_event("evt_discussion", EventType.DISCUSSION, "Discuss UNIX retrieval")
    reasoning = _make_event("evt_reasoning", EventType.REASONING, "Reason about precision layers")

    links = linker.link([discussion, reasoning], threshold=0.8)

    assert links == []


def test_semantic_linker_requires_override_signal_for_decision_pairs():
    linker = SemanticLinker(model_name="test-model")
    linker._model = _FakeModel([[1.0, 0.0], [1.0, 0.0]])

    older = Event(
        id="evt_old",
        type=EventType.DECISION,
        timestamp=datetime.now() - timedelta(minutes=5),
        summary="Keep timeline-only explanation",
        content="Timeline-only explanation",
    )
    newer = Event(
        id="evt_new",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Replace timeline-only explanation with causal evidence",
        content="Replace old behavior with causal evidence",
    )

    links = linker.link([older, newer], threshold=0.8)

    assert len(links) == 1
    assert links[0].relation == "overrides"
    assert links[0].source == "evt_new"
    assert links[0].target == "evt_old"
