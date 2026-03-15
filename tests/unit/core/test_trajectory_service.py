from datetime import datetime

from dimcause.reasoning.causal import CausalLink
from dimcause.core.models import EventType, SemanticEvent
from dimcause.core.trajectory import TrajectoryService


def test_trajectory_build():
    """Test building DAG from events."""
    # A -> B -> C
    evt_a = SemanticEvent(
        id="a", type=EventType.DECISION, timestamp=datetime.now(), summary="A", content="A"
    )
    evt_b = SemanticEvent(
        id="b", type=EventType.CODE_CHANGE, timestamp=datetime.now(), summary="B", content="B"
    )
    evt_c = SemanticEvent(
        id="c", type=EventType.CODE_CHANGE, timestamp=datetime.now(), summary="C", content="C"
    )

    # Link A -> B
    # 注意: Link 通常存储在 Source 事件中，或者作为独立实体
    # TrajectoryService 遍历 events.causal_links
    link_ab = CausalLink(source=evt_a.uri, target=evt_b.uri, relation="triggers")
    evt_a.causal_links = [link_ab]

    # Link B -> C
    link_bc = CausalLink(source=evt_b.uri, target=evt_c.uri, relation="leads_to")
    evt_b.causal_links = [link_bc]

    service = TrajectoryService([evt_a, evt_b, evt_c])

    # Check ancestors of C (should represent the 'cause')
    ancestors = service.get_ancestors(evt_c.uri)
    assert len(ancestors) == 2
    ids = {e.id for e in ancestors}
    assert "a" in ids
    assert "b" in ids

    # Check descendants of A (should represent the 'effect')
    descendants = service.get_descendants(evt_a.uri)
    assert len(descendants) == 2
    ids = {e.id for e in descendants}
    assert "b" in ids
    assert "c" in ids


def test_cycle_detection():
    """Test cycle detection."""
    # A -> B -> A
    evt_a = SemanticEvent(
        id="a", type=EventType.DECISION, timestamp=datetime.now(), summary="A", content="A"
    )
    evt_b = SemanticEvent(
        id="b", type=EventType.CODE_CHANGE, timestamp=datetime.now(), summary="B", content="B"
    )

    link_ab = CausalLink(source=evt_a.uri, target=evt_b.uri, relation="triggers")
    evt_a.causal_links = [link_ab]

    link_ba = CausalLink(source=evt_b.uri, target=evt_a.uri, relation="loops")
    evt_b.causal_links = [link_ba]

    service = TrajectoryService([evt_a, evt_b])
    cycles = service.detect_cycles()
    assert len(cycles) > 0
