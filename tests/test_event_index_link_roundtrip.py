from datetime import datetime

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SemanticEvent, SourceType
from dimcause.reasoning.causal import CausalLink


def test_event_index_upsert_links_roundtrips_semantic_event(tmp_path):
    index = EventIndex(db_path=str(tmp_path / "index.db"))
    event = Event(
        id="evt_roundtrip",
        type=EventType.DECISION,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary="Adopt scheduler verification",
        content="Decision content",
    )
    index.add(event, str(tmp_path / "evt_roundtrip.md"))

    ok = index.upsert_links(
        "evt_roundtrip",
        [
            CausalLink(
                source="evt_roundtrip",
                target="evt_requirement",
                relation="implements",
                weight=0.8,
                metadata={"strategy": "test"},
            )
        ],
    )

    assert ok is True

    loaded = index.load_event("evt_roundtrip")
    assert isinstance(loaded, SemanticEvent)
    assert len(loaded.causal_links) == 1
    assert loaded.causal_links[0].relation == "implements"
    assert loaded.causal_links[0].target == "evt_requirement"


def test_event_index_upsert_links_merges_without_overwriting_existing_edges(tmp_path):
    index = EventIndex(db_path=str(tmp_path / "index.db"))
    event = Event(
        id="evt_merge_links",
        type=EventType.DECISION,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary="Decision for search architecture",
        content="Decision content",
    )
    index.add(event, str(tmp_path / "evt_merge_links.md"))

    index.upsert_links(
        "evt_merge_links",
        [
            CausalLink(
                source="evt_merge_links", target="evt_req_a", relation="implements", weight=0.6
            )
        ],
    )
    index.upsert_links(
        "evt_merge_links",
        [
            CausalLink(
                source="evt_merge_links", target="evt_req_b", relation="implements", weight=0.9
            )
        ],
    )

    links = index.get_links("evt_merge_links")
    targets = {link.target for link in links}

    assert targets == {"evt_req_a", "evt_req_b"}
