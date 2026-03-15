from datetime import datetime

from dimcause.reasoning.causal import CausalLink
from dimcause.core.models import EventType, SemanticEvent, SourceType


def test_semantic_event_instantiation():
    """Test that SemanticEvent can be instantiated with default values."""
    event = SemanticEvent(
        id="test-event-1",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Test Decision",
        content="This is a test decision.",
        source=SourceType.MANUAL,
    )

    assert event.id == "test-event-1"
    assert event.uri == "dev://event/test-event-1"
    assert event.causal_links == []
    assert event.context == {}


def test_semantic_event_with_links():
    """Test SemanticEvent with CausalLinks."""
    link = CausalLink(source="dev://event/1", target="dev://event/2", relation="triggers")

    event = SemanticEvent(
        id="test-event-2",
        type=EventType.CODE_CHANGE,
        timestamp=datetime.now(),
        summary="Test Change",
        content="Changed code.",
        causal_links=[link],
    )

    assert len(event.causal_links) == 1
    assert event.causal_links[0].relation == "triggers"
