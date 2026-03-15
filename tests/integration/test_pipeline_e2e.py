import pytest
import os
import time
from datetime import datetime
from dimcause.core.schema import ChunkRecord
from dimcause.storage.chunk_store import ChunkStore
from dimcause.storage.graph_store import GraphStore
from dimcause.core.event_index import EventIndex
from dimcause.extractors.extraction_pipeline import ExtractionPipeline
from dimcause.core.models import Event, EventType, SourceType

@pytest.fixture
def env(tmp_path):
    os.environ["DEEPSEEK_API_KEY"] = "sk-fake-for-test"
    db_path = tmp_path / "dimcause.db"
    cs = ChunkStore(tmp_path / "chunks.db")
    ei = EventIndex(str(db_path))
    gs = GraphStore(str(db_path))
    pipe = ExtractionPipeline(ei, gs, cs)
    yield {"cs": cs, "ei": ei, "gs": gs, "pipe": pipe, "session": "sess_e2e_01"}
    os.environ.pop("DEEPSEEK_API_KEY", None)

def test_pipeline_e2e_flow(env):
    cs = env["cs"]
    pipe = env["pipe"]
    session_id = env["session"]
    ei = env["ei"]

    content = "Today I decided to migrate the DB to JSON. This fixes #42."
    chunk_id = ChunkStore.make_chunk_id(f"evt_{session_id}_01", content)
    chunk = ChunkRecord(
        chunk_id=chunk_id,
        source_event_id=f"evt_{session_id}_01",
        session_id=session_id,
        content=content,
        status="raw",
        created_at=time.time(),
        updated_at=time.time(),
    )
    cs.add_chunk(chunk)

    from dimcause.brain.extractor import EventExtractor
    
    # 我们不 mock _run_l2，而是让它真实调用，只要 mock 掉内部 LLM 请求即可
    def mock_extract(self, text):
        return [
            Event(
                id="fake1",
                type=EventType.DECISION,
                summary="Migrate DB to JSON",
                content="Decided to migrate DB to JSON",
                timestamp=datetime.now()
            ),
            Event(
                id="fake2",
                type=EventType.DIAGNOSTIC,
                summary="Fixed #42",
                content="Fixed #42 in DB",
                timestamp=datetime.now()
            )
        ]

    # Monkeypatch
    setattr(EventExtractor, 'extract_from_text', mock_extract)

    stats = pipe.run(session_id)
    
    assert stats["l2_count"] == 2
    assert cs.get_chunk(chunk_id).status == "extracted"

    coalesced = ei.query_coalesced()
    
    # Debug print internal events table
    conn = ei._get_conn()
    all_events = conn.execute("SELECT id, type, source_layer FROM events").fetchall()
    print("=== Raw DB Events ===")
    for row in all_events:
        print(dict(row))
    conn.close()

    l2_events = [e for e in coalesced if e.get("source_layer") == "l2"]
    assert len(l2_events) == 2


