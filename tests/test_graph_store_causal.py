import sqlite3

import pytest

from dimcause.storage.graph_store import GraphStore


@pytest.fixture
def graph_store(tmp_path):
    return GraphStore(db_path=str(tmp_path / "graph_store_causal.db"))


def _insert_node(conn: sqlite3.Connection, node_id: str, node_type: str = "event") -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO graph_nodes (id, type, data, last_updated)
        VALUES (?, ?, '{}', 0.0)
        """,
        (node_id, node_type),
    )


def _insert_edge(
    conn: sqlite3.Connection,
    source: str,
    target: str,
    relation: str,
    created_at: float,
) -> None:
    conn.execute(
        """
        INSERT INTO graph_edges (source, target, relation, weight, metadata, created_at)
        VALUES (?, ?, ?, 1.0, '{}', ?)
        """,
        (source, target, relation, created_at),
    )


def test_get_causal_chain_ignores_structural_overwrite_on_same_pair(graph_store):
    conn = graph_store._get_conn()
    try:
        _insert_node(conn, "evt_a")
        _insert_node(conn, "evt_b")
        # 同一对节点同时存在因果边和结构边，DiGraph 内存图会被覆盖，
        # 该测试要求 get_causal_chain 走 SQL 仍能命中因果边。
        _insert_edge(conn, "evt_a", "evt_b", "caused_by", 100.0)
        _insert_edge(conn, "evt_a", "evt_b", "calls", 200.0)
    finally:
        conn.close()

    chain = graph_store.get_causal_chain("evt_b", depth=1)
    assert chain == ["evt_a"]


def test_get_causal_chain_bfs_order_filters_structural_and_excludes_self(graph_store):
    conn = graph_store._get_conn()
    try:
        for node in ["evt_target", "evt_new", "evt_old", "evt_level2", "evt_noise"]:
            _insert_node(conn, node)

        _insert_edge(conn, "evt_old", "evt_target", "caused_by", 100.0)
        _insert_edge(conn, "evt_new", "evt_target", "triggers", 200.0)
        _insert_edge(conn, "evt_noise", "evt_target", "calls", 300.0)  # 结构边，必须过滤
        _insert_edge(conn, "evt_level2", "evt_new", "resulted_in", 250.0)
        # 构造回环，验证 target_id 不会被回收进结果
        _insert_edge(conn, "evt_target", "evt_level2", "caused_by", 50.0)
    finally:
        conn.close()

    chain = graph_store.get_causal_chain("evt_target", depth=3)

    assert chain == ["evt_new", "evt_old", "evt_level2"]
    assert "evt_target" not in chain
    assert "evt_noise" not in chain
