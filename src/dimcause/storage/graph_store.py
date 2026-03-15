"""
GraphStore - 知识图谱存储 (SQLite Registry Strategy)

遵照 ADR-001 (STORAGE_ARCHITECTURE.md)，GraphStore 作为 SQLite Registry 的内存视图。
- 数据源: SQLite (index.db: graph_nodes, graph_edges)
- 运行时: NetworkX DiGraph (Hydrated on load)
- 持久化: 直接写入 SQLite，不使用 Pickle。
"""

import json
import sqlite3
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dimcause.core.models import Entity, Event

# =============================================================================
# Causal Core 异常定义 (Task 007-01)
# =============================================================================


class CausalCoreError(Exception):
    """Causal Core 基础异常"""

    pass


class CausalTimeReversedError(CausalCoreError):
    """时间倒流异常：target 时间早于 source"""

    def __init__(self, source_time: float, target_time: float, jitter: float):
        self.source_time = source_time
        self.target_time = target_time
        self.jitter = jitter
        super().__init__(
            f"时间倒流禁止: source={source_time}, target={target_time}, 允许抖动={jitter}s"
        )


class TopologicalIsolationError(CausalCoreError):
    """拓扑孤岛异常：源与目标无拓扑交集"""

    def __init__(self, source_anchors: Set[str], target_anchors: Set[str]):
        self.source_anchors = source_anchors
        self.target_anchors = target_anchors
        super().__init__(
            f"拓扑孤岛禁止: source_anchors={source_anchors}, "
            f"target_anchors={target_anchors}, 交集为空"
        )


class IllegalRelationError(CausalCoreError):
    """非法关系类型：不允许通过当前公开接口写入"""

    def __init__(self, relation: str, hint: Optional[str] = None):
        self.relation = relation
        self.hint = hint or "请改用正确的图关系写入接口"
        super().__init__(f"关系类型 '{relation}' 不允许通过当前接口写入，{self.hint}")


# =============================================================================
# GraphStore 主类
# =============================================================================


class GraphStore:
    """
    知识图谱存储（基于 NetworkX + SQLite Backend）

    实现 IGraphStore 接口。
    启动时从 SQLite 加载数据构建图。
    写入时同步更新 SQLite 和内存图。
    """

    def __init__(self, db_path: str = "~/.dimcause/index.db", persist_path: Optional[str] = None):
        if persist_path is not None:
            warnings.warn(
                "persist_path 已废弃，请改用 db_path=，将在 V7.0 移除",
                DeprecationWarning,
                stacklevel=2,
            )
            db_path = persist_path
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._graph = None
        self._ensure_schema()
        self._setup()

    def _ensure_schema(self) -> None:
        """确保 GraphStore 所需的表结构存在"""
        conn = self._get_conn()
        try:
            # graph_nodes 表
            conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data JSON DEFAULT '{}',
                last_updated REAL NOT NULL
            )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(type)")

            # graph_edges 表
            conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata JSON DEFAULT '{}',
                created_at REAL NOT NULL,
                PRIMARY KEY (source, target, relation),
                FOREIGN KEY(source) REFERENCES graph_nodes(id),
                FOREIGN KEY(target) REFERENCES graph_nodes(id)
            )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_relation ON graph_edges(relation)")

            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接。isolation_level=None 禁止隐式 BEGIN，支持手动 BEGIN IMMEDIATE。"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _setup(self) -> None:
        """初始化图并从数据库加载"""
        try:
            import networkx as nx

            self._graph = nx.DiGraph()
            self.load_from_db()
        except ImportError:
            print("Warning: networkx not installed, graph features disabled")
            self._graph = None

    def load_from_db(self) -> None:
        """从 SQLite 加载图数据 (Hydration)"""
        if self._graph is None:
            return

        if not self.db_path.exists():
            return

        conn = self._get_conn()
        try:
            # 1. 加载节点
            # 检查表是否存在
            try:
                cursor = conn.execute("SELECT id, type, data FROM graph_nodes")
                for row in cursor:
                    try:
                        data = json.loads(row["data"]) if row["data"] else {}
                    except json.JSONDecodeError:
                        data = {}

                    # Prevent TypeError: got multiple values for keyword argument 'type'
                    if "type" in data:
                        del data["type"]

                    self._graph.add_node(row["id"], type=row["type"], **data)
            except sqlite3.OperationalError:
                # 表可能不存在（尚未迁移或初始化）
                pass

            # 2. 加载边
            try:
                cursor = conn.execute(
                    "SELECT source, target, relation, weight, metadata FROM graph_edges"
                )
                for row in cursor:
                    try:
                        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                    except json.JSONDecodeError:
                        metadata = {}

                    # Prevent TypeError for edge attributes
                    for key in ["relation", "weight"]:
                        if key in metadata:
                            del metadata[key]

                    self._graph.add_edge(
                        row["source"],
                        row["target"],
                        relation=row["relation"],
                        weight=row["weight"],
                        **metadata,
                    )
            except sqlite3.OperationalError:
                pass

        finally:
            conn.close()

    def save(self) -> None:
        """
        持久化图

        Deprecated: 在 SQLite 策略下，写入即持久化。此方法保留为空以兼容旧代码接口，但不再执行 Pickle dump。
        """
        warnings.warn(
            "GraphStore.save() is deprecated and will be removed in V7.0. "
            "GraphStore now uses SQLite auto-persistence strategy.",
            DeprecationWarning,
            stacklevel=2,
        )
        pass

    def _upsert_node(
        self, conn: sqlite3.Connection, node_id: str, node_type: str, data: Dict[str, Any]
    ) -> None:
        """内部方法：写入节点到 DB"""
        import time

        conn.execute(
            """
            INSERT OR REPLACE INTO graph_nodes (id, type, data, last_updated)
            VALUES (?, ?, ?, ?)
        """,
            (node_id, node_type, json.dumps(data), time.time()),
        )

    def _merge_metadata(self, old: Dict, new: Dict) -> Dict:
        """
        合并两个 metadata 字典（定案25）。
        - List 字段：去重追加（旧值在前，新值补充）
        - 标量字段：新值覆盖旧值
        """
        merged = dict(old)
        for key, new_val in new.items():
            if key in merged and isinstance(merged[key], list) and isinstance(new_val, list):
                # List 字段去重追加：旧值 + 新增条目
                existing_set = set(merged[key])
                merged[key] = merged[key] + [v for v in new_val if v not in existing_set]
            else:
                merged[key] = new_val
        return merged

    def _upsert_edge(
        self,
        conn: sqlite3.Connection,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        metadata: Dict = None,
    ) -> None:
        """内部方法：写入边到 DB"""
        import time

        if metadata is None:
            metadata = {}

        conn.execute(
            """
            INSERT OR REPLACE INTO graph_edges (source, target, relation, weight, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (source, target, relation, weight, json.dumps(metadata), time.time()),
        )

    def add_entity(self, entity_id: str | Entity, entity_type: str = "unknown", **kwargs) -> None:
        """添加实体（节点）"""
        if self._graph is None:
            return

        # Handle Entity object input
        if isinstance(entity_id, Entity):
            entity = entity_id
            entity_id = entity.name
            entity_type = entity.type
            kwargs.update({"context": entity.context})

        # Update in-memory graph
        self._graph.add_node(entity_id, type=entity_type, **kwargs)

        # Persist to SQLite
        conn = self._get_conn()
        try:
            self._upsert_node(conn, entity_id, entity_type, kwargs)
            conn.commit()
        finally:
            conn.close()

    # ===========================================================================
    # 结构边公开接口（白名单校验）
    # ===========================================================================

    # 结构边允许的关系类型白名单
    STRUCTURAL_RELATIONS: frozenset = frozenset({"calls", "imports", "contains", "depends_on"})

    def add_structural_relation(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        写入结构边（GraphStore 对外唯一公开的关系写入接口）。

        仅允许白名单内的关系类型：calls、imports、contains、depends_on。
        因果边必须通过 CausalEngine.link_causal() 写入，禁止走此接口。
        """
        if relation not in self.STRUCTURAL_RELATIONS:
            raise IllegalRelationError(
                relation, hint="结构边仅允许 calls/imports/contains/depends_on"
            )
        self._internal_add_relation(
            source=source,
            target=target,
            relation=relation,
            weight=weight,
            metadata=metadata,
        )

    def add_semantic_relation(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        写入 ontology 定义的非因果语义关系。

        这层专门承接 `implements/realizes/fixes/...` 这类合法本体边，
        避免它们被错误塞进结构边接口。
        """
        from dimcause.core.ontology import get_ontology
        from dimcause.reasoning.causal_engine import CAUSAL_RELATIONS_SET

        ontology = get_ontology()
        relation_def = ontology.get_relation(relation)
        if relation_def is None:
            raise IllegalRelationError(relation, hint="关系未在 ontology.yaml 中定义")
        if relation in CAUSAL_RELATIONS_SET:
            raise IllegalRelationError(relation, hint="因果边请走 CausalEngine.link_causal()")
        if relation in self.STRUCTURAL_RELATIONS:
            raise IllegalRelationError(
                relation,
                hint="结构边请走 GraphStore.add_structural_relation()",
            )

        self._internal_add_relation(
            source=source,
            target=target,
            relation=relation,
            weight=weight,
            metadata=metadata,
        )

    def _internal_add_relation(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        私有底座：写入或更新图边（RMW + BEGIN IMMEDIATE）。

        不对外暴露。外部写入请走：
        - 结构边：add_structural_relation()
        - 因果边：CausalEngine.link_causal()

        - weight：取 MAX(existing, new)，置信度只升不降
        - metadata.derived_from_chunks：List 去重追加，历史来源永不丢失
        - created_at：首次 INSERT 时记录，UPDATE 不变
        - 并发安全：BEGIN IMMEDIATE 排他锁防止惊群写冲突
        """
        import time

        if metadata is None:
            metadata = {}

        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")

            # 确保节点存在
            for node_id in (source, target):
                row = conn.execute("SELECT id FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO graph_nodes (id, type, data, last_updated) VALUES (?, ?, ?, ?)",
                        (node_id, "unknown", "{}", time.time()),
                    )

            # RMW：读取现有边
            existing = conn.execute(
                "SELECT weight, metadata FROM graph_edges WHERE source=? AND target=? AND relation=?",
                (source, target, relation),
            ).fetchone()

            if existing is not None:
                # 边已存在：weight 取 MAX，metadata 去重合并，created_at 不变
                old_weight = existing["weight"] or 0.0
                try:
                    old_meta = json.loads(existing["metadata"]) if existing["metadata"] else {}
                except json.JSONDecodeError:
                    old_meta = {}

                new_weight = max(old_weight, weight)
                new_meta = self._merge_metadata(old_meta, metadata)

                conn.execute(
                    "UPDATE graph_edges SET weight=?, metadata=? WHERE source=? AND target=? AND relation=?",
                    (new_weight, json.dumps(new_meta), source, target, relation),
                )
            else:
                # 边不存在：首次 INSERT，记录 created_at
                conn.execute(
                    "INSERT INTO graph_edges (source, target, relation, weight, metadata, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (source, target, relation, weight, json.dumps(metadata), time.time()),
                )
                new_weight = weight
                new_meta = metadata

            conn.execute("COMMIT")

            # DB 落盘后再更新内存图（防止 COMMIT 失败导致内存脏写）
            if self._graph is not None:
                if source not in self._graph:
                    self._graph.add_node(source, type="unknown")
                if target not in self._graph:
                    self._graph.add_node(target, type="unknown")
                self._graph.add_edge(
                    source,
                    target,
                    relation=relation,
                    weight=new_weight,
                    **{k: v for k, v in new_meta.items() if k not in ("relation", "weight")},
                )
            else:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "[GraphStore] networkx 未初始化，_internal_add_relation 仅写入 DB，内存图跳过"
                )

        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def find_related(self, entity_name: str, depth: int = 1) -> List[Entity]:
        """
        查找相关实体

        Args:
            entity_name: 实体名称
            depth: 搜索深度

        Returns:
            相关实体列表
        """
        if self._graph is None or entity_name not in self._graph:
            return []

        # BFS 查找邻居
        related = set()
        current_level = {entity_name}

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                # 出边（后继）
                next_level.update(self._graph.successors(node))
                # 入边（前驱）
                next_level.update(self._graph.predecessors(node))

            related.update(next_level)
            current_level = next_level - related

        # 转换为 Entity
        entities = []
        for name in related:
            if name != entity_name:
                node_data = self._graph.nodes[name]
                entities.append(
                    Entity(
                        name=name,
                        type=node_data.get("type", "unknown"),
                        context=node_data.get("context"),
                    )
                )

        return entities

    def find_experts(self, file_path: str) -> List[str]:
        """
        查找文件专家（修改过该文件的开发者/会话）

        Args:
            file_path: 文件路径

        Returns:
            专家（会话/用户）列表
        """
        if self._graph is None:
            return []

        # 查找所有指向该文件的 "modifies" 关系
        experts = []
        # 注意: networkx 的 edges(data=True) 返回 (u, v, d)
        # 我们需要在内存图中查找
        if self._graph.has_node(file_path):
            for source in self._graph.predecessors(file_path):
                edge_data = self._graph.get_edge_data(source, file_path)
                if edge_data and edge_data.get("relation") == "modifies":
                    experts.append(source)

        return list(set(experts))

    def add_event_relations(self, event: Event) -> None:
        """
        从 Event 中提取并添加关系

        注意：通常 EventIndex.add() 已经处理了这些关系的持久化。
        此方法用于 GraphStore 独立使用场景，或者确保内存图同步更新。
        """
        if self._graph is None:
            return

        conn = self._get_conn()
        try:
            # 添加 Event 节点
            event_type_str = getattr(event.type, "value", str(event.type))
            node_data = {"event_type": event_type_str, "timestamp": event.timestamp.isoformat()}

            # 内存更新
            self._graph.add_node(event.id, type="event", **node_data)
            # DB 更新
            self._upsert_node(conn, event.id, "event", node_data)

            # Event -> Files
            for file in event.related_files:
                # 确保 file 节点存在
                if file not in self._graph:
                    self._graph.add_node(file, type="file")
                    self._upsert_node(conn, file, "file", {})

                self._graph.add_edge(event.id, file, relation="modifies")
                self._upsert_edge(conn, event.id, file, "modifies")

            # File 共现关系
            files = event.related_files
            for i, f1 in enumerate(files):
                for f2 in files[i + 1 :]:
                    self._graph.add_edge(f1, f2, relation="co_modified")
                    self._upsert_edge(conn, f1, f2, "co_modified")

            # Event -> Entities
            for entity in event.entities:
                # 直接复用当前 conn，避免 add_entity 内部再开连接导致 database is locked
                entity_id = entity.name
                entity_type = entity.type
                if entity_id not in self._graph:
                    self._graph.add_node(entity_id, type=entity_type, context=entity.context)
                    self._upsert_node(conn, entity_id, entity_type, {"context": entity.context})

                self._graph.add_edge(event.id, entity_id, relation="mentions")
                self._upsert_edge(conn, event.id, entity_id, "mentions")

            conn.commit()
        finally:
            conn.close()

    def get_file_history(self, file_path: str, limit: int = 10) -> List[str]:
        """
        获取文件的修改历史（Event IDs）

        Args:
            file_path: 文件路径
            limit: 返回数量限制

        Returns:
            Event ID 列表
        """
        if self._graph is None:
            return []

        events = []
        if self._graph.has_node(file_path):
            for source in self._graph.predecessors(file_path):
                edge_data = self._graph.get_edge_data(source, file_path)
                if edge_data and edge_data.get("relation") == "modifies":
                    node_data = self._graph.nodes[source]
                    if node_data.get("type") == "event":
                        events.append((source, node_data.get("timestamp", "")))

        # 按时间排序
        events.sort(key=lambda x: x[1], reverse=True)
        return [e[0] for e in events[:limit]]

    def get_causal_chain(self, target_id: str, depth: int = 3) -> List[str]:
        """
        追溯 target_id 的因果前置事件链（只看入边，BFS 层序）。

        约束：
        - 仅允许 CAUSAL_RELATIONS_SET 内的关系类型
        - 必须使用 SQLite 表回溯，禁止依赖内存 DiGraph
        - 返回值排除 target_id 自身
        - 查询顺序固定，避免 Flaky：created_at DESC, source ASC, relation ASC
        """
        if depth <= 0:
            return []

        from collections import deque

        # 延迟导入，避免 graph_store <-> causal_engine 顶层循环依赖
        from dimcause.reasoning.causal_engine import CAUSAL_RELATIONS_SET

        relations = sorted(CAUSAL_RELATIONS_SET)
        if not relations:
            return []

        visited = {target_id}
        ordered_sources: List[str] = []
        queue = deque([(target_id, 0)])

        conn = self._get_conn()
        try:
            placeholders = ", ".join(["?"] * len(relations))
            sql = f"""
                SELECT source, relation
                FROM graph_edges
                WHERE target = ? AND relation IN ({placeholders})
                ORDER BY created_at DESC, source ASC, relation ASC
            """

            while queue:
                current_id, level = queue.popleft()
                if level >= depth:
                    continue

                cursor = conn.execute(sql, [current_id, *relations])
                for row in cursor:
                    source_id = row["source"]
                    # 按契约：仅用前置 source 作为 event_id 候选，且排除 target/self
                    if source_id in visited:
                        continue
                    visited.add(source_id)
                    ordered_sources.append(source_id)
                    queue.append((source_id, level + 1))
        finally:
            conn.close()

        return ordered_sources

    def stats(self) -> Dict[str, int]:
        """图统计信息"""
        if self._graph is None:
            return {"nodes": 0, "edges": 0}

        return {
            "nodes": self._graph.number_of_nodes(),
            "edges": self._graph.number_of_edges(),
        }

    def get_event_metadata(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        从 events 表获取事件元数据 (用于 SearchEngine)

        Args:
            event_id: 事件 ID

        Returns:
            Dict or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            # events table might not exist if only GraphStore initialized
            return None
        finally:
            conn.close()


# 便捷函数
def create_graph_store(path: Optional[str] = None) -> GraphStore:
    """创建图存储实例"""
    return GraphStore(db_path=path or "~/.dimcause/index.db")
