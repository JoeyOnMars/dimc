"""
V6.3 Local-First 提取流水线编排器

架构决策：ADR-CL-001 v3.0（外键校验建边）
- CausalLinker 不再扫描，不再用 N×M 增量闭包
- 事件入库后同步执行 _link_causal_edges（O(1) 外键校验）
- L1（BGE-M3 离线）/ L2（云端 LLM 可选）流水线留待后续实现

定案 8/9/10/26 — V6.3
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, List

from dimcause.core.models import Event, EventType, SourceType
from dimcause.core.ontology import get_ontology
from dimcause.core.schema import ChunkRecord
from dimcause.objects import attach_object_projection, project_chunk_event_bundle
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.causal_engine import CAUSAL_RELATIONS_SET, CausalEngine
from dimcause.reasoning.relation_inference import (
    infer_directed_ontology_relation,
    to_ontology_event_class,
)
from dimcause.storage.chunk_store import ChunkStore
from dimcause.storage.graph_store import CausalTimeReversedError, TopologicalIsolationError

if TYPE_CHECKING:
    from dimcause.core.event_index import EventIndex
    from dimcause.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """
    V6.3 提取流水线编排器。

    当前实现范围（定案 26）：
    - _link_causal_edges：事件入库后同步外键校验建边

    待实现（后续步骤）：
    - _run_l1：L1 BGE-M3 离线提取
    - _run_l2：L2 云端 LLM 精炼（可选）
    - run：批次编排，WAL 集成
    """

    def __init__(
        self,
        event_index: EventIndex,
        graph_store: GraphStore,
        chunk_store: ChunkStore,
    ) -> None:
        self.event_index = event_index
        self.graph_store = graph_store
        self.chunk_store = chunk_store
        self.ontology = get_ontology()
        self.causal_engine = CausalEngine(graph_store=graph_store)

    def _link_causal_edges(self, event: Event) -> None:
        """
        事件入库后同步执行外键校验建边。无扫描器，无时间窗，无队列。

        调用时机：EventIndex.add() 完成后，由 _persist_events() 调用。
        容错：目标事件不存在、关系无法推断、ontology 校验失败 → logger.warning + 跳过，不 raise。

        字段名：related_event_ids（P博士裁定，2026-02-23）
        """
        # EventIndex.get() 通过 Pydantic model_validate 反序列化，
        # related_event_ids 已是 Python list，不得再套 json.loads()。
        # isinstance 兜底处理直接从 DB row 构建的边缘路径。
        related_ids = event.related_event_ids or []
        if isinstance(related_ids, str):
            related_ids = json.loads(related_ids)
        if not related_ids:
            return

        for target_id in related_ids:
            target_event = self.event_index.load_event(target_id)
            if target_event is None:
                logger.warning(f"[CausalLinker] 目标事件不存在: {target_id}，跳过")
                continue

            result = infer_directed_ontology_relation(event, target_event)
            if result is None:
                logger.warning(
                    f"[CausalLinker] 本体中无合法关系: {event.type} ↔ {target_event.type}，跳过"
                )
                continue

            relation, source_evt, target_evt = result
            source_class = to_ontology_event_class(source_evt)
            target_class = to_ontology_event_class(target_evt)
            if not source_class or not target_class:
                logger.warning(
                    f"[CausalLinker] 无法映射事件类型到 ontology: {source_evt.type} -> {target_evt.type}，跳过"
                )
                continue

            valid, msg = self.ontology.validate_relation(relation, source_class, target_class)
            if not valid:
                logger.warning(f"[CausalLinker] 本体校验失败: {msg}，跳过")
                continue

            # 路由判断：因果边走 CausalEngine 防线，结构边走 GraphStore 白名单入口
            if relation in CAUSAL_RELATIONS_SET:
                try:
                    self.causal_engine.link_causal(
                        source=source_evt,
                        target=target_evt,
                        relation=relation,
                    )
                    logger.debug(
                        f"[CausalLinker] 因果边: {source_evt.id} --{relation}--> {target_evt.id}"
                    )
                except CausalTimeReversedError as e:
                    logger.warning(f"[CausalLinker] 时间锥拦截，跳过: {e}")
                except TopologicalIsolationError as e:
                    logger.warning(f"[CausalLinker] 拓扑孤岛拦截，跳过: {e}")
            else:
                self.graph_store.add_semantic_relation(source_evt.id, target_evt.id, relation)
                logger.debug(
                    f"[CausalLinker] 结构边: {source_evt.id} --{relation}--> {target_evt.id}"
                )

            link = CausalLink(
                source=source_evt.id,
                target=target_evt.id,
                relation=relation,
                weight=1.0,
                metadata={"strategy": "explicit_reference"},
            )
            if not self.event_index.upsert_links(source_evt.id, [link]):
                logger.warning(f"[CausalLinker] EventIndex link upsert failed: {source_evt.id}")

    # =========================================================================
    # Task 004: run() + _run_l1/_run_l2/_persist_events
    # =========================================================================

    def run(self, session_id: str) -> dict:
        """
        执行 L1→(L2)→Persist→Link 全流程。

        Returns:
            dict: {"l1_count": int, "l2_count": int, "link_count": int, "errors": int}
        """
        stats = {"l1_count": 0, "l2_count": 0, "link_count": 0, "errors": 0}

        pending = self.chunk_store.get_pending_extraction(session_id=session_id)
        if not pending:
            return stats

        has_llm = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))

        for chunk in pending:
            l1_done = False

            # ── L1 阶段（仅 raw 状态的 chunk）──
            if chunk.status == "raw":
                try:
                    events = self._run_l1(chunk)
                    count = self._persist_events(events, chunk, "l1")
                    stats["l1_count"] += count
                    self.chunk_store.update_status(chunk.chunk_id, "embedded")
                    l1_done = True
                except Exception as e:
                    logger.error(f"L1 failed for {chunk.chunk_id}: {e}")
                    stats["errors"] += 1
                    continue  # 跳过该 chunk 的 L2

            # ── L2 阶段（已 embedded + 有 LLM Key）──
            if has_llm and (l1_done or chunk.status == "embedded"):
                try:
                    events = self._run_l2(chunk)
                    count = self._persist_events(events, chunk, "l2")
                    stats["l2_count"] += count
                    self.chunk_store.update_status(chunk.chunk_id, "extracted")
                except Exception as e:
                    logger.warning(f"L2 failed for {chunk.chunk_id}: {e}")
                    stats["errors"] += 1

        return stats

    def _run_l1(self, chunk: ChunkRecord) -> List[Event]:
        """
        对单个 chunk 执行 L1 本地提取（无 LLM 依赖）。

        优先从 extract_session_events 内部获取结构化数据，
        避免 markdown → Event 逆解析。
        event_id 命名空间：'evt_' + sha256(chunk_id:l1:index)[:16]
        提取失败返回空列表，不抛异常。
        """
        from dimcause.extractors.session_extractor import SessionExtractor

        if not chunk.content:
            return []

        # SessionExtractor 需要 Claude Code markdown 格式
        # 包装成 USER/ASSISTANT 对（带时间戳以匹配正则）
        formatted = f"### USER (2024-01-01 00:00:00)\n\n{chunk.content}\n\n### ASSISTANT (2024-01-01 00:00:01)\n\nAssistant response."

        try:
            extractor = SessionExtractor(use_embedding=False)
            result = extractor.extract(formatted)
        except Exception as e:
            logger.warning(f"SessionExtractor failed for {chunk.chunk_id}: {e}")
            return []

        events = []
        idx = 0

        # completed_tasks → EventType.DECISION (as completed task)
        for item in result.completed_tasks[:5]:
            event_id = self._make_event_id(chunk.chunk_id, "l1", idx)
            events.append(self._make_event(event_id, "decision", item, chunk))
            idx += 1

        # problems → EventType.DIAGNOSTIC
        for item in result.problems[:5]:
            event_id = self._make_event_id(chunk.chunk_id, "l1", idx)
            events.append(self._make_event(event_id, "diagnostic", item, chunk))
            idx += 1

        # decisions → EventType.DECISION
        for item in result.decisions[:5]:
            event_id = self._make_event_id(chunk.chunk_id, "l1", idx)
            events.append(self._make_event(event_id, "decision", item, chunk))
            idx += 1

        # pending → EventType.TASK
        for item in result.pending[:5]:
            event_id = self._make_event_id(chunk.chunk_id, "l1", idx)
            events.append(self._make_event(event_id, "task", item, chunk))
            idx += 1

        return events

    def _run_l2(self, chunk: ChunkRecord) -> List[Event]:
        """
        对单个 chunk 执行 L2 云端 LLM 提取。

        复用 brain/extractor.py 中的 EventExtractor.extract_from_text()。
        event_id 命名空间：'evt_' + sha256(chunk_id:l2:index)[:16]
        失败时抛异常，由 run() 层捕获。
        """
        from dimcause.brain.extractor import EventExtractor

        if not chunk.content:
            return []

        try:
            extractor = EventExtractor()
            # extract_from_text 返回 List[Event]
            events = extractor.extract_from_text(chunk.content)
        except Exception as e:
            raise RuntimeError(f"L2 extraction failed for {chunk.chunk_id}: {e}") from e

        # 重写 event_id 带上 layer 标记，防止与 L1 冲突
        rewritten = []
        for i, ev in enumerate(events):
            new_id = self._make_event_id(chunk.chunk_id, "l2", i)
            ev.id = new_id
            # 注入 session_id 到 metadata（为 CausalEngine 提供拓扑锚点）
            if ev.metadata is None:
                ev.metadata = {}
            ev.metadata["session_id"] = chunk.session_id
            rewritten.append(ev)

        return rewritten

    def _persist_events(
        self,
        events: List[Event],
        chunk: ChunkRecord,
        layer: str,
    ) -> int:
        """
        将事件写入 EventIndex，同步调用 _link_causal_edges 建边。

        L1 策略：add_if_not_exists()（只补不覆盖）
        L2 策略：先 delete_by_chunk_layer()，再逐条 add()

        Returns:
            int: 成功写入的事件数量
        """
        if layer == "l2":
            self.event_index.delete_by_chunk_layer(chunk.chunk_id, "l2")

        count = 0

        for event in events:
            attach_object_projection(event, project_chunk_event_bundle(chunk, event))
            fake_path = f"/fake/chunks/{chunk.chunk_id}/{event.id}.md"
            if layer == "l1":
                ok = self.event_index.add_if_not_exists(
                    event,
                    fake_path,
                    source_chunk_id=chunk.chunk_id,
                    source_layer="l1",
                )
            else:
                ok = self.event_index.add(
                    event,
                    fake_path,
                    source_chunk_id=chunk.chunk_id,
                    source_layer="l2",
                )
            if ok:
                count += 1
                try:
                    self._link_causal_edges(event)
                    # 简单统计 link 数（实际应从 graph_store 返回）
                except Exception as e:
                    logger.warning(f"CausalLinker failed for {event.id}: {e}")

        return count

    @staticmethod
    def _make_event_id(chunk_id: str, layer: str, index: int) -> str:
        """生成 event_id：'evt_' + sha256(chunk_id:layer:index)[:16]"""
        key = f"{chunk_id}:{layer}:{index}"
        return "evt_" + hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def _make_event(event_id: str, event_type: str, summary: str, chunk: ChunkRecord) -> Event:
        """从提取结果构造 Event 对象。"""
        return Event(
            id=event_id,
            type=EventType(event_type),
            source=SourceType.CLAUDE_CODE,
            timestamp=datetime.fromtimestamp(chunk.created_at),
            summary=summary[:50],
            content=summary,
            metadata={"session_id": chunk.session_id},
        )
