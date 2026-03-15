from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from dimcause.core.models import (
    DimcauseConfig,
    Event,
    EventType,
    RawData,
    SemanticEvent,
    SourceType,
)
from dimcause.reasoning.causal import CausalLink
from dimcause.services.pipeline import Pipeline


def test_pipeline_uses_runtime_storage_paths(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))

    assert pipeline.event_index.db_path == tmp_path / "index.db"
    assert pipeline.graph_store.db_path == tmp_path / "graph.db"
    assert pipeline.vector_store.db_path == str(tmp_path / "index.db")


def test_pipeline_save_event_writes_event_index(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
    pipeline.vector_store = Mock()
    pipeline.graph_store = Mock()

    event = Event(
        id="evt_pipeline_index",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Pipeline writes EventIndex",
        content="Ensure daemon pipeline writes to EventIndex.",
    )

    pipeline._save_event(event)

    conn = pipeline.event_index._get_conn()
    try:
        row = conn.execute(
            "SELECT id, markdown_path, type FROM events WHERE id = ?",
            (event.id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["id"] == event.id
    assert row["type"] == EventType.DECISION.value
    assert row["markdown_path"].endswith(f"{event.id}.md")


def test_pipeline_save_event_raises_when_event_index_write_fails(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
    pipeline.vector_store = Mock()
    pipeline.graph_store = Mock()
    pipeline.event_index = Mock()
    pipeline.event_index.add.return_value = False
    pipeline.event_index.db_path = tmp_path / "index.db"

    event = Event(
        id="evt_pipeline_fail",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Pipeline failure",
        content="Force EventIndex failure.",
    )

    with pytest.raises(RuntimeError, match="EventIndex add returned False"):
        pipeline._save_event(event)


def test_pipeline_process_merges_raw_context_and_related_files(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
    pipeline.vector_store = Mock()
    pipeline.graph_store = Mock()
    pipeline.reasoning_engine = None

    pipeline.extractor = Mock()
    pipeline.extractor.extract.return_value = Event(
        id="evt_context_merge",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Context merge",
        content="Merge raw metadata into event.",
        metadata={"extractor_hint": "present"},
    )

    raw = RawData(
        id="raw_context_merge",
        source=SourceType.CLAUDE_CODE,
        timestamp=datetime.now(),
        content="Implement src/dimcause/cli.py flow",
        metadata={"session_id": "sess-123", "job_id": "job-9"},
        files_mentioned=["src/dimcause/cli.py"],
        project_path=str(tmp_path),
    )

    pipeline.process(raw)
    stored = pipeline.event_index.load_event("evt_context_merge")

    assert stored is not None
    assert stored.metadata["session_id"] == "sess-123"
    assert stored.metadata["job_id"] == "job-9"
    assert stored.metadata["project_path"] == str(tmp_path)
    assert stored.metadata["module_path"] == "src/dimcause/cli.py"
    assert stored.metadata["extractor_hint"] == "present"
    projection = stored.metadata["object_projection"]
    assert projection["version"] == "v1"
    assert projection["material"]["object_family"] == "material"
    assert projection["material"]["source_ref"] == "raw_context_merge"
    assert projection["claims"][0]["object_family"] == "claim"
    assert projection["claims"][0]["statement"] == "Context merge"
    assert projection["relations"][0]["relation_type"] == "grounded_in"
    assert projection["relations"][0]["to_ref"] == projection["material"]["id"]
    assert stored.related_files == ["src/dimcause/cli.py"]


def test_pipeline_process_persists_explicit_related_event_relation(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
    pipeline.vector_store = Mock()
    pipeline.reasoning_engine = None

    target = Event(
        id="evt_requirement_target",
        type=EventType.REQUIREMENT,
        timestamp=datetime.now(),
        summary="Need a safer scheduler gate",
        content="Requirement for scheduler gating.",
        related_files=["src/dimcause/cli.py"],
        metadata={"session_id": "sess-200", "module_path": "src/dimcause/cli.py"},
    )
    pipeline._save_event(target)

    pipeline.extractor = Mock()
    pipeline.extractor.extract.return_value = Event(
        id="evt_decision_source",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Implement scheduler completion gate",
        content="Decision to implement scheduler completion gate.",
        related_event_ids=[target.id],
    )

    raw = RawData(
        id="raw_explicit_relation",
        source=SourceType.CLAUDE_CODE,
        timestamp=datetime.now(),
        content="We should implement the scheduler gate.",
        metadata={"session_id": "sess-200"},
        files_mentioned=["src/dimcause/cli.py"],
    )

    pipeline.process(raw)

    conn = pipeline.graph_store._get_conn()
    try:
        edge = conn.execute(
            "SELECT source, target, relation FROM graph_edges WHERE source = ? AND target = ? AND relation = ?",
            ("evt_decision_source", "evt_requirement_target", "implements"),
        ).fetchone()
    finally:
        conn.close()

    assert edge is not None
    links = pipeline.event_index.get_links("evt_decision_source")
    assert len(links) == 1
    assert links[0].relation == "implements"
    stored = pipeline.event_index.load_event("evt_decision_source")
    assert isinstance(stored, SemanticEvent)
    assert len(stored.causal_links) == 1


def test_pipeline_process_persists_inferred_reasoning_link(tmp_path: Path):
    pipeline = Pipeline(config=DimcauseConfig(data_dir=str(tmp_path)))
    pipeline.vector_store = Mock()

    target = Event(
        id="evt_requirement_reasoned",
        type=EventType.REQUIREMENT,
        timestamp=datetime.now(),
        summary="Need UNIX precision layer",
        content="Requirement for UNIX-native retrieval.",
        related_files=["src/dimcause/search/engine.py"],
        metadata={"session_id": "sess-300", "module_path": "src/dimcause/search/engine.py"},
    )
    pipeline._save_event(target)

    pipeline.extractor = Mock()
    pipeline.extractor.extract.return_value = Event(
        id="evt_decision_reasoned",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Add UNIX retrieval precision layer",
        content="Decision to add UNIX retrieval precision layer.",
    )
    pipeline.reasoning_engine = Mock()
    pipeline.reasoning_engine.infer.return_value = [
        CausalLink(
            source="evt_decision_reasoned",
            target="evt_requirement_reasoned",
            relation="implements",
            weight=0.91,
            metadata={"strategy": "semantic"},
        )
    ]

    raw = RawData(
        id="raw_reasoning_relation",
        source=SourceType.CLAUDE_CODE,
        timestamp=datetime.now(),
        content="Implement UNIX retrieval.",
        metadata={"session_id": "sess-300"},
        files_mentioned=["src/dimcause/search/engine.py"],
    )

    pipeline.process(raw)

    conn = pipeline.graph_store._get_conn()
    try:
        edge = conn.execute(
            "SELECT source, target, relation, metadata FROM graph_edges WHERE source = ? AND target = ? AND relation = ?",
            ("evt_decision_reasoned", "evt_requirement_reasoned", "implements"),
        ).fetchone()
    finally:
        conn.close()

    assert edge is not None
    assert "pipeline_reasoning" in edge["metadata"]
    links = pipeline.event_index.get_links("evt_decision_reasoned")
    assert len(links) == 1
    assert links[0].relation == "implements"
