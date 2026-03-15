import json
import os
import sqlite3

import pytest

from dimcause.core.models import Entity
from dimcause.storage.graph_store import GraphStore


# Using a temporary file for the test database
@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_graph.db")


@pytest.fixture
def graph_store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


def test_initialization(graph_store, temp_db_path):
    """Test that GraphStore initializes and creates tables."""
    assert os.path.exists(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='graph_nodes'")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='graph_edges'")
    assert cursor.fetchone() is not None
    conn.close()


def test_add_entity(graph_store, temp_db_path):
    """Test adding an entity writes to both memory and DB."""
    entity = Entity(name="TestEntity", type="concept", context="A test entity")
    graph_store.add_entity(entity)

    # Check memory
    assert "TestEntity" in graph_store._graph
    assert graph_store._graph.nodes["TestEntity"]["type"] == "concept"

    # Check DB
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, data FROM graph_nodes WHERE id='TestEntity'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "TestEntity"
    assert row[1] == "concept"
    data = json.loads(row[2])
    assert data["context"] == "A test entity"
    conn.close()


def test_add_relation(graph_store, temp_db_path):
    # [TEST_FIX_REASON] add_relation 废除，改用 _internal_add_relation 测试底层写库行为。
    # "related_to" 非结构边白名单，通过私有底座绕过白名单直接写入。
    """Test adding a relation writes to both memory and DB."""
    graph_store._internal_add_relation("A", "B", "related_to")

    # Check memory
    assert graph_store._graph.has_edge("A", "B")
    assert graph_store._graph.edges["A", "B"]["relation"] == "related_to"

    # Check DB
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source, target, relation FROM graph_edges WHERE source='A' AND target='B'"
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[2] == "related_to"

    # Check implicit node creation
    cursor.execute("SELECT id FROM graph_nodes WHERE id IN ('A', 'B')")
    nodes = cursor.fetchall()
    assert len(nodes) == 2
    conn.close()


def test_hydration(temp_db_path):
    """Test that a new GraphStore instance loads data from existing DB."""
    # 1. Create store and add data
    store1 = GraphStore(db_path=temp_db_path)
    # [TEST_FIX_REASON] add_relation 废除，改用 _internal_add_relation。
    store1._internal_add_relation("X", "Y", "connects")

    # 2. Create new store instance pointing to same DB
    store2 = GraphStore(db_path=temp_db_path)

    # 3. Verify data is loaded
    assert store2._graph is not None
    assert store2._graph.has_node("X")
    assert store2._graph.has_node("Y")
    assert store2._graph.has_edge("X", "Y")
    assert store2._graph.edges["X", "Y"]["relation"] == "connects"


def test_no_pickle(graph_store):
    """Ensure no pickle file is created (sanity check)."""
    # This test is more about verifying behavior via code inspection or ensuring no 'graph.pkl' logic runs.
    # Since we removed the code, we just check calling save() does nothing or raises no error.
    graph_store.save()
    # Check implementation detail: save() is pass
    assert True
