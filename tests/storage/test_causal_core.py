"""
Causal Core 架构隔离验收测试 (Task 007-01)

测试覆盖（合约第 5 条，零容忍验收）：
1. 底座越权测试：GraphStore.add_structural_relation 被白名单干掉
2. 结构边绿灯：GraphStore.add_structural_relation("calls") 正常写库
3. 负向测试 1（时间倒流）：CausalEngine.link_causal 拦截
4. 负向测试 2（拓扑孤岛）：CausalEngine.link_causal 拦截
5. 豁免正向测试（Global Broadcast）：is_global=True 的 source 写入成功
"""

import tempfile
from datetime import datetime

import pytest

from dimcause.core.models import Event, EventType, SourceType
from dimcause.reasoning.causal_engine import CausalEngine
from dimcause.storage import (
    CausalTimeReversedError,
    GraphStore,
    IllegalRelationError,
    TopologicalIsolationError,
)


@pytest.fixture
def graph_store():
    """创建临时 GraphStore"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield GraphStore(db_path=f"{tmpdir}/test_graph.db")


@pytest.fixture
def causal_engine(graph_store):
    """创建 CausalEngine（依赖注入）"""
    return CausalEngine(graph_store=graph_store)


def _make_event(event_id: str, ts: datetime, metadata: dict) -> Event:
    """辅助函数：创建测试 Event"""
    return Event(
        id=event_id,
        type=EventType.CODE_CHANGE,
        timestamp=ts,
        summary="Test event",
        content="Test content",
        metadata=metadata,
        source=SourceType.CLAUDE_CODE,
    )


# =============================================================================
# 1. 底座越权测试
# =============================================================================

class TestStructuralRelationWhitelist:
    """GraphStore.add_structural_relation 白名单校验"""

    def test_illegal_relation_rejected(self, graph_store):
        """
        底座越权测试：传入因果关系类型 "causes"，应被白名单拦截。
        """
        with pytest.raises(IllegalRelationError) as exc_info:
            graph_store.add_structural_relation("A", "B", "causes")

        assert "causes" in str(exc_info.value)
        assert "CausalEngine" in str(exc_info.value)

    def test_structural_relation_allowed(self, graph_store):
        """
        结构边绿灯：add_structural_relation("calls") 正常写库。
        """
        # 不应抛出异常
        graph_store.add_structural_relation("module_a", "func_b", "calls")

        # 验证实际写入数据库
        conn = graph_store._get_conn()
        try:
            row = conn.execute(
                "SELECT source, target, relation FROM graph_edges "
                "WHERE source=? AND target=? AND relation=?",
                ("module_a", "func_b", "calls"),
            ).fetchone()
            assert row is not None, "结构边应写入数据库"
            assert row["relation"] == "calls"
        finally:
            conn.close()


# =============================================================================
# 2 & 3. 防线 A：时间锥拦截
# =============================================================================

class TestCausalCoreTimeBlock:
    """防线 A: CausalEngine 时间锥拦截"""

    def test_time_reversed_rejected(self, causal_engine):
        """
        负向测试 1（时间倒流）：target 时间早于 source 超出 Jitter，拦截。
        """
        source = _make_event(
            "src-001",
            datetime(2026, 2, 25, 10, 0, 0),
            {"session_id": "sess-A"},
        )
        target = _make_event(
            "tgt-001",
            datetime(2026, 2, 25, 9, 59, 58),  # 早 2 秒，超出 JITTER=1s
            {"session_id": "sess-A"},
        )

        with pytest.raises(CausalTimeReversedError) as exc_info:
            causal_engine.link_causal(source, target, "caused_by")

        assert exc_info.value.jitter == 1.0
        assert exc_info.value.source_time > exc_info.value.target_time

    def test_time_within_jitter_allowed(self, causal_engine):
        """
        时间在 Jitter 范围内，不应被时间锥拦截。
        """
        source = _make_event(
            "src-002",
            datetime(2026, 2, 25, 10, 0, 0),
            {"session_id": "sess-B"},
        )
        target = _make_event(
            "tgt-002",
            datetime(2026, 2, 25, 10, 0, 0, 500000),  # 0.5s 后，在 1s jitter 内
            {"session_id": "sess-B"},
        )

        try:
            causal_engine.link_causal(source, target, "caused_by")
        except CausalTimeReversedError:
            pytest.fail("时间在 jitter 范围内不应抛出 CausalTimeReversedError")


# =============================================================================
# 4. 防线 B：拓扑孤岛禁绝
# =============================================================================

class TestCausalCoreTopologicalBan:
    """防线 B: CausalEngine 拓扑孤岛拦截"""

    def test_topological_island_rejected(self, causal_engine):
        """
        负向测试 2（拓扑孤岛）：无交集且非全局事件，应抛出 TopologicalIsolationError。
        """
        source = _make_event(
            "src-003",
            datetime(2026, 2, 25, 10, 0, 0),
            {"session_id": "sess-X", "service_name": "svc-A"},
        )
        target = _make_event(
            "tgt-003",
            datetime(2026, 2, 25, 10, 0, 5),
            {"session_id": "sess-Y", "service_name": "svc-B"},  # 完全不同
        )

        with pytest.raises(TopologicalIsolationError) as exc_info:
            causal_engine.link_causal(source, target, "caused_by")

        assert exc_info.value.source_anchors is not None
        assert exc_info.value.target_anchors is not None
        # 确认无交集
        intersection = exc_info.value.source_anchors & exc_info.value.target_anchors
        assert len(intersection) == 0


# =============================================================================
# 5. 豁免正向测试（Global Broadcast Override）
# =============================================================================

class TestGlobalBroadcastOverride:
    """全局广播豁免：is_global=True 的 source 可辐射到局部 session"""

    def test_global_event_override_topological_isolation(self, causal_engine, graph_store):
        """
        豁免正向测试：source 带 is_global=True，target 有 session_id，
        即使拓扑锚点不相交也应允许写入。
        """
        source = _make_event(
            "global-alarm-001",
            datetime(2026, 2, 25, 10, 0, 0),
            {"is_global": True},  # 全局灾难级事件，无 session_id
        )
        target = _make_event(
            "session-timeout-001",
            datetime(2026, 2, 25, 10, 0, 5),
            {"session_id": "sess-Z"},  # 局部 session 事件
        )

        # 全局广播豁免，不应抛出异常
        result = causal_engine.link_causal(source, target, "caused_by")

        assert result["global_broadcast"] is True

        # 验证边实际写入数据库
        conn = graph_store._get_conn()
        try:
            row = conn.execute(
                "SELECT source, target, relation FROM graph_edges WHERE source=? AND target=?",
                (source.id, target.id),
            ).fetchone()
            assert row is not None, "全局广播边应写入数据库"
            assert row["relation"] == "caused_by"
        finally:
            conn.close()
