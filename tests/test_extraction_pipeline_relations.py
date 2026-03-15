import time
from datetime import datetime

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType
from dimcause.core.schema import ChunkRecord
from dimcause.extractors.extraction_pipeline import ExtractionPipeline
from dimcause.storage.chunk_store import ChunkStore
from dimcause.storage.graph_store import GraphStore


def test_extraction_pipeline_links_non_causal_ontology_relation(tmp_path):
    event_index = EventIndex(db_path=str(tmp_path / "index.db"))
    graph_store = GraphStore(db_path=str(tmp_path / "graph.db"))
    chunk_store = ChunkStore(db_path=tmp_path / "chunks.db")
    pipeline = ExtractionPipeline(
        event_index=event_index,
        graph_store=graph_store,
        chunk_store=chunk_store,
    )

    requirement = Event(
        id="evt_requirement",
        type=EventType.REQUIREMENT,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary="Need scheduler verification",
        content="Requirement for scheduler verification.",
        metadata={"session_id": "sess-400", "module_path": "src/dimcause/cli.py"},
    )
    event_index.add(requirement, "/tmp/evt_requirement.md")

    chunk = ChunkRecord(
        chunk_id="chunk-implements",
        source_event_id="evt_source",
        session_id="sess-400",
        content="Implement scheduler verification",
        created_at=time.time(),
        updated_at=time.time(),
    )
    decision = Event(
        id="evt_decision",
        type=EventType.DECISION,
        source=SourceType.MANUAL,
        timestamp=datetime.now(),
        summary="Implement scheduler verification",
        content="Decision to implement scheduler verification.",
        related_event_ids=["evt_requirement"],
        metadata={"session_id": "sess-400", "module_path": "src/dimcause/cli.py"},
    )

    event_index.add(
        decision, "/tmp/evt_decision.md", source_chunk_id=chunk.chunk_id, source_layer="l1"
    )
    pipeline._link_causal_edges(decision)

    conn = graph_store._get_conn()
    try:
        edge = conn.execute(
            "SELECT source, target, relation FROM graph_edges WHERE source = ? AND target = ? AND relation = ?",
            ("evt_decision", "evt_requirement", "implements"),
        ).fetchone()
    finally:
        conn.close()

    assert edge is not None
    links = event_index.get_links("evt_decision")
    assert len(links) == 1
    assert links[0].relation == "implements"
