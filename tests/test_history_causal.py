import json
from unittest.mock import patch

from dimcause.core.event_index import EventIndex
from dimcause.core.history import _get_causal_related_events, get_file_history
from dimcause.storage.graph_store import GraphStore


def _insert_event(
    event_index: EventIndex,
    event_id: str,
    summary: str,
    file_path: str,
    timestamp: str,
    include_file_hint: bool,
) -> None:
    date = timestamp[:10]
    json_cache = json.dumps({"related_files": [file_path]}) if include_file_hint else json.dumps({})
    conn = event_index._get_conn()
    try:
        conn.execute(
            """
            INSERT INTO events (
                id, type, source, timestamp, date, summary, tags,
                markdown_path, mtime, json_cache
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                "decision",
                "manual",
                timestamp,
                date,
                summary,
                "",
                f"/tmp/{event_id}.md",
                0.0,
                json_cache,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _build_history_fixture(tmp_path, file_path: str) -> EventIndex:
    db_path = tmp_path / "history_causal.db"
    event_index = EventIndex(db_path=str(db_path))

    _insert_event(
        event_index,
        event_id="evt_seed",
        summary=f"touches {file_path}",
        file_path=file_path,
        timestamp="2026-03-04T10:00:00",
        include_file_hint=True,
    )
    _insert_event(
        event_index,
        event_id="evt_root",
        summary="root cause event",
        file_path=file_path,
        timestamp="2026-03-03T10:00:00",
        include_file_hint=False,
    )

    graph_store = GraphStore(db_path=str(db_path))
    graph_store._internal_add_relation("evt_root", "evt_seed", "caused_by")
    # 同一事件-文件对上叠加结构边，验证种子不会因 DiGraph 覆盖丢失
    graph_store._internal_add_relation("evt_seed", file_path, "modifies")
    graph_store._internal_add_relation("evt_seed", file_path, "calls")

    return event_index


def test_get_file_history_uses_causal_chain_with_same_db_fallback(tmp_path):
    file_path = "src/demo.py"
    event_index = _build_history_fixture(tmp_path, file_path)

    called_paths = []

    def _factory(path=None):
        called_paths.append(path)
        return GraphStore(db_path=path)

    with patch("dimcause.storage.graph_store.create_graph_store", side_effect=_factory):
        commits = get_file_history(
            file_path=file_path,
            limit=10,
            event_index=event_index,
            use_causal_chain=True,
        )

    hashes = {c.hash for c in commits}
    assert "evt_seed" in hashes
    assert "evt_root" in hashes
    root_commit = next(c for c in commits if c.hash == "evt_root")
    seed_commit = next(c for c in commits if c.hash == "evt_seed")
    assert root_commit.from_causal_chain is True
    assert seed_commit.from_causal_chain is False
    assert called_paths == [str(event_index.db_path)]


def test_get_causal_related_events_no_content_column_and_seed_kept(tmp_path):
    file_path = "src/demo.py"
    event_index = _build_history_fixture(tmp_path, file_path)

    # 明确验证 events 表没有 content 列（防幽灵字段）
    conn = event_index._get_conn()
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(events)")}
    finally:
        conn.close()
    assert "content" not in cols

    called_paths = []

    def _factory(path=None):
        called_paths.append(path)
        return GraphStore(db_path=path)

    with patch("dimcause.storage.graph_store.create_graph_store", side_effect=_factory):
        causal_events = _get_causal_related_events(
            file_path=file_path,
            event_index=event_index,
            max_depth=2,
        )

    assert [evt["id"] for evt in causal_events] == ["evt_root"]
    assert all(evt.get("_from_causal_chain") is True for evt in causal_events)
    assert called_paths == [str(event_index.db_path)]
