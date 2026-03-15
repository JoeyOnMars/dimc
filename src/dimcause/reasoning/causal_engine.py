"""
CausalEngine - 因果边写入唯一入口 (Task 007-01)

架构分层：
- GraphStore (哑存储层)：只负责结构边写入，_internal_add_relation 为私有底座。
- CausalEngine (Domain 领域护城河)：独占因果关系知识库，全权执行时空锁与广播豁免。

RFC-011 铁律（为方案 B 无痛迁移预留）：
1. 彻底依赖注入：GraphStore 实例由顶层传入，禁止在此硬编码 GraphStore()。
2. 纯粹可序列化：所有出入参可被 JSON/Protobuf 序列化，禁止依赖进程内内存引用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Set

from dimcause.core.models import Event
from dimcause.storage.graph_store import (
    CausalTimeReversedError,
    GraphStore,
    TopologicalIsolationError,
)

if TYPE_CHECKING:
    pass


# 合法因果关系白名单（由 CausalEngine 独占）
CAUSAL_RELATIONS_SET: frozenset = frozenset(
    {
        "caused_by",
        "triggers",
        "leads_to",
        "correlated_with",
        "depends_on_causal",
        "resulted_in",
    }
)


class CausalEngine:
    """
    因果边写入唯一入口。

    使用方式：
        engine = CausalEngine(graph_store=my_graph_store)
        result = engine.link_causal(source_event, target_event, "caused_by")
    """

    JITTER_SECONDS: float = 1.0

    def __init__(self, graph_store: GraphStore) -> None:
        """
        初始化 CausalEngine。

        RFC-011 铁律：GraphStore 实例必须由外部传入，禁止在此方法内部
        创建 GraphStore() 实例（确保未来方案 B 的无痛替换）。
        """
        self._graph_store = graph_store

    def _get_topological_anchors(self, event: Event) -> Set[str]:
        """
        提取事件的拓扑锚点。

        从 metadata 中提取 session_id、service_name、module_path、job_id。
        禁止使用 event.id 作为无脑兜底——提取不到锚点时诚实返回空 set()。
        """
        anchors: Set[str] = set()
        m = event.metadata or {}

        if val := m.get("session_id"):
            anchors.add(f"session:{val}")
        if val := m.get("service_name"):
            anchors.add(f"service:{val}")
        if val := m.get("module_path"):
            anchors.add(f"module:{val}")
        if val := m.get("job_id"):
            anchors.add(f"job:{val}")

        # 绝对禁止：anchors.add(f"event:{event.id[:8]}")
        return anchors

    def link_causal(
        self,
        source: Event,
        target: Event,
        relation: str,
        weight: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> dict:
        """
        写入一条因果边（唯一合法入口）。

        执行双重硬锁：
        - 防线 A（时间锥）：target 时间不得早于 source 时间 + jitter
        - 防线 B（拓扑孤岛 + Global Broadcasting 豁免）：
            * 普通情况：两事件必须有拓扑锚点交集
            * 全局广播豁免：source.metadata["is_global"] is True 且
              target 有局部 session_id，跳过孤岛拦截

        返回：写入结果摘要（dict），含实际写入的 source_anchors/target_anchors 信息。

        仅当双重防线全部通过后，才调用 GraphStore._internal_add_relation() 落盘。
        """
        if metadata is None:
            metadata = {}

        # --- 防线 A: 时间锥拦截 ---
        source_time: float = source.timestamp.timestamp()
        target_time: float = target.timestamp.timestamp()

        if target_time + self.JITTER_SECONDS < source_time:
            raise CausalTimeReversedError(
                source_time=source_time,
                target_time=target_time,
                jitter=self.JITTER_SECONDS,
            )

        # --- 防线 B: 拓扑孤岛 + Global Broadcasting Override ---
        source_anchors = self._get_topological_anchors(source)
        target_anchors = self._get_topological_anchors(target)

        source_meta = source.metadata or {}
        target_meta = target.metadata or {}

        # 全局广播豁免：source 是全局灾难级事件，允许辐射到局部 session 事件
        is_global_broadcast = source_meta.get("is_global") is True and bool(
            target_meta.get("session_id")
        )

        if is_global_broadcast:
            intersection: Set[str] = set()  # 豁免时交集可以为空
        else:
            intersection = source_anchors & target_anchors
            if not intersection:
                raise TopologicalIsolationError(
                    source_anchors=source_anchors,
                    target_anchors=target_anchors,
                )

        # --- 通过双重防线，调用私有底座落盘 ---
        causal_meta = {
            **metadata,
            "causal_core": True,
            "source_anchors": sorted(source_anchors),
            "target_anchors": sorted(target_anchors),
            "intersection": sorted(intersection),
            "global_broadcast": is_global_broadcast,
        }

        self._graph_store._internal_add_relation(
            source=source.id,
            target=target.id,
            relation=relation,
            weight=weight,
            metadata=causal_meta,
        )

        return {
            "source_id": source.id,
            "target_id": target.id,
            "relation": relation,
            "weight": weight,
            "source_anchors": sorted(source_anchors),
            "target_anchors": sorted(target_anchors),
            "intersection": sorted(intersection),
            "global_broadcast": is_global_broadcast,
        }
