import sqlite3
from pathlib import Path

import pytest

from dimcause.storage.graph_store import GraphStore


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture providing a temporary database path."""
    return str(tmp_path / "test_graph.db")


@pytest.fixture
def graph_store(temp_db_path):
    """Fixture providing an initialized GraphStore instance."""
    return GraphStore(db_path=temp_db_path)


def test_schema_created_automatically(temp_db_path):
    """
    Validation Test: Verify that GraphStore creates its own schema on initialization.
    Rule: No External Assumptions.
    """
    assert not Path(temp_db_path).exists()

    GraphStore(db_path=temp_db_path)

    assert Path(temp_db_path).exists()

    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]

    assert "graph_nodes" in table_names
    assert "graph_edges" in table_names

    conn.close()


def test_add_get_node(graph_store):
    """Test standard Node CRUD operations via add_entity."""
    node_id = "test_node_1"
    node_type = "decision"
    data = {"confidence": 0.9, "summary": "Test Summary"}

    graph_store.add_entity(node_id, node_type, **data)

    # Verify via in-memory graph
    assert graph_store._graph.has_node(node_id)
    node_data = graph_store._graph.nodes[node_id]
    assert node_data["type"] == node_type
    assert node_data["confidence"] == data["confidence"]
    assert node_data["summary"] == data["summary"]

    # Verify persisted to SQLite
    conn = sqlite3.connect(str(graph_store.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM graph_nodes WHERE id=?", (node_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row["type"] == node_type


def test_add_get_edge(graph_store):
    # [TEST_FIX_REASON] add_relation 废除，改为 _internal_add_relation 测试底层写库功能，
    # "caused" 非结构边白名单，仅通过私有底座写入。
    """Test standard Edge CRUD operations via _internal_add_relation."""
    source = "node_a"
    target = "node_b"
    relation = "caused"

    graph_store.add_entity(source, "event")
    graph_store.add_entity(target, "event")
    graph_store._internal_add_relation(source, target, relation)

    # Verify via in-memory graph
    assert graph_store._graph.has_edge(source, target)
    edge_data = graph_store._graph.get_edge_data(source, target)
    assert edge_data["relation"] == relation

    # Verify persisted to SQLite
    conn = sqlite3.connect(str(graph_store.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM graph_edges WHERE source=? AND target=?", (source, target)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["relation"] == relation


def test_foreign_key_constraint(graph_store):
    """
    Validation Test: Verify foreign key constraints are active.
    Rule: Data Integrity.
    """
    conn = sqlite3.connect(str(graph_store.db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        conn.execute(
            "INSERT INTO graph_edges (source, target, relation, weight, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("missing_a", "missing_b", "rel", 1.0, "{}", 0.0),
        )
        conn.commit()
    conn.close()


def test_networkx_roundtrip(graph_store):
    """Test that nodes/edges persist and reload correctly (roundtrip via SQLite)."""
    graph_store.add_entity("n1", "event", score=10)
    graph_store.add_entity("n2", "event", score=20)
    # [TEST_FIX_REASON] add_relation 废除，"next" 非白名单关系，改用 _internal_add_relation。
    graph_store._internal_add_relation("n1", "n2", "next")

    # Simulate reload: new instance from same DB
    db_path = str(graph_store.db_path)
    gs2 = GraphStore(db_path=db_path)

    assert gs2._graph.has_node("n1")
    assert gs2._graph.has_node("n2")
    assert gs2._graph.nodes["n1"]["score"] == 10
    assert gs2._graph.has_edge("n1", "n2")
    assert gs2._graph.get_edge_data("n1", "n2")["relation"] == "next"


def test_upsert_behavior(graph_store):
    """Test that adding existing nodes updates them (Upsert via add_entity)."""
    node_id = "u_node"

    graph_store.add_entity(node_id, "type1", v=1)
    assert graph_store._graph.nodes[node_id]["type"] == "type1"
    assert graph_store._graph.nodes[node_id]["v"] == 1

    graph_store.add_entity(node_id, "type2", v=2)
    assert graph_store._graph.nodes[node_id]["type"] == "type2"
    assert graph_store._graph.nodes[node_id]["v"] == 2
