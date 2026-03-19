# Security Baseline: SEC-1.1 / SEC-1.2 (Level A) – EventIndex consistency

import json
import logging
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from dimcause.core.models import Event, EventType, SemanticEvent, SourceType
from dimcause.core.ontology import get_ontology
from dimcause.core.schema_validator import (
    LegacyTypeGovernanceRecord,
    get_schema_validator,
)
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.relation_inference import to_ontology_event_class
from dimcause.utils.wal import WALEntry, WriteAheadLog


class EventIndex:
    """
    统一事件索引层 (Layer 3)

    负责维护 SQLite 索引，提供高性能查询和元数据管理。
    作为 Markdown 文件的派生数据源。
    """

    WAL_EVENT_INDEX_WRITE = "event_index_write"

    def __init__(
        self,
        db_path: str = "~/.dimcause/index.db",
        wal_manager: Optional[WriteAheadLog] = None,
        enable_wal_recovery: bool = True,
    ):
        """
        初始化索引数据库

        Args:
            db_path: 数据库路径，支持 ~ 展开
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.wal = wal_manager or WriteAheadLog(wal_path=str(self.db_path.with_suffix(".wal.log")))

        self._ensure_schema()
        if enable_wal_recovery:
            self._recover_pending_writes()
        self._backfill_query_cache()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接，配置 WAL 模式"""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,  # 增加超时时间以应对并发
            check_same_thread=False,  # 允许跨线程使用（需小心）
        )
        conn.row_factory = sqlite3.Row
        # 启用 WAL 模式提高并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        """确保表结构存在"""
        conn = self._get_conn()
        try:
            # 创建 events 表
            conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                markdown_path TEXT NOT NULL UNIQUE,
                mtime REAL NOT NULL,
                job_id TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                schema_version INTEGER NOT NULL DEFAULT 1,
                json_cache TEXT DEFAULT NULL,
                cache_updated_at REAL DEFAULT NULL
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS events_cache (
                id TEXT PRIMARY KEY,
                json_data TEXT NOT NULL,
                markdown_path TEXT NOT NULL,
                last_updated REAL NOT NULL,
                FOREIGN KEY(id) REFERENCES events(id) ON DELETE CASCADE
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS event_file_refs (
                event_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                PRIMARY KEY (event_id, file_path),
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            )
            """)

            # 创建 causal_links 表 (Phase 2)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                event_id TEXT NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            )
            """)

            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_events_date ON events(date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
                "CREATE INDEX IF NOT EXISTS idx_events_type_date ON events(type, date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)",
                "CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)",
                "CREATE INDEX IF NOT EXISTS idx_events_job_id ON events(job_id) WHERE job_id != ''",
                "CREATE INDEX IF NOT EXISTS idx_events_mtime ON events(mtime DESC)",
                "CREATE INDEX IF NOT EXISTS idx_events_cache_updated ON events_cache(last_updated DESC)",
                "CREATE INDEX IF NOT EXISTS idx_events_cache_path ON events_cache(markdown_path)",
                "CREATE INDEX IF NOT EXISTS idx_event_file_refs_path ON event_file_refs(file_path)",
                "CREATE INDEX IF NOT EXISTS idx_event_file_refs_name ON event_file_refs(file_name)",
                # 因果链索引
                "CREATE INDEX IF NOT EXISTS idx_links_source ON causal_links(source)",
                "CREATE INDEX IF NOT EXISTS idx_links_target ON causal_links(target)",
                "CREATE INDEX IF NOT EXISTS idx_links_relation ON causal_links(relation)",
                "CREATE INDEX IF NOT EXISTS idx_links_event_id ON causal_links(event_id)",
            ]

            # Phase 3.1: Graph Store Schema
            # graph_nodes 表
            conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data JSON DEFAULT '{}',
                last_updated REAL NOT NULL
            )
            """)
            indexes.extend(["CREATE INDEX IF NOT EXISTS idx_nodes_type ON graph_nodes(type)"])

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
            indexes.extend(
                [
                    "CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source)",
                    "CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target)",
                    "CREATE INDEX IF NOT EXISTS idx_edges_relation ON graph_edges(relation)",
                ]
            )

            for idx_sql in indexes:
                conn.execute(idx_sql)

            # 迁移守卫：V6.3 source_layer 路由（Task 003）
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
            if "source_chunk_id" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN source_chunk_id TEXT DEFAULT NULL")
            if "source_layer" not in existing_cols:
                conn.execute(
                    "ALTER TABLE events ADD COLUMN source_layer TEXT DEFAULT NULL "
                    "CHECK(source_layer IS NULL OR source_layer IN ('l1', 'l2'))"
                )
            if "updated_at" not in existing_cols:
                conn.execute("ALTER TABLE events ADD COLUMN updated_at REAL DEFAULT NULL")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_layer "
                "ON events(source_chunk_id, source_layer, updated_at DESC)"
            )

            conn.commit()
        finally:
            conn.close()

    def _normalize_file_ref(self, file_ref: str) -> str:
        """规范化文件引用，保留相对/绝对语义，但统一分隔符。"""
        normalized = str(file_ref).strip().replace("\\", "/")
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        return normalized

    def _collect_file_refs(self, event: Event, markdown_path: str) -> List[str]:
        refs: List[str] = []

        def _extend(raw_value: Any) -> None:
            if isinstance(raw_value, str) and raw_value.strip():
                refs.append(raw_value)
            elif isinstance(raw_value, list):
                for item in raw_value:
                    if isinstance(item, str) and item.strip():
                        refs.append(item)

        _extend(getattr(event, "related_files", []) or [])
        _extend(event.metadata.get("related_files"))
        _extend(event.metadata.get("file_path"))
        refs.append(str(markdown_path))

        deduped: List[str] = []
        seen = set()
        for item in refs:
            normalized = self._normalize_file_ref(item)
            if not normalized or normalized in seen:
                continue
            deduped.append(normalized)
            seen.add(normalized)
        return deduped

    def _sync_query_cache(
        self,
        conn: sqlite3.Connection,
        event: Event,
        markdown_path: str,
        cache_updated_at: float,
    ) -> None:
        cache_path = str(Path(markdown_path).resolve())
        conn.execute(
            """
            INSERT OR REPLACE INTO events_cache (id, json_data, markdown_path, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (event.id, event.model_dump_json(), cache_path, cache_updated_at),
        )

        conn.execute("DELETE FROM event_file_refs WHERE event_id = ?", (event.id,))
        file_refs = self._collect_file_refs(event, markdown_path)
        if file_refs:
            conn.executemany(
                """
                INSERT OR REPLACE INTO event_file_refs (event_id, file_path, file_name)
                VALUES (?, ?, ?)
                """,
                [(event.id, file_ref, Path(file_ref).name or file_ref) for file_ref in file_refs],
            )

    def _backfill_query_cache(self) -> None:
        """为历史事件补齐 events_cache / event_file_refs。"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """
                SELECT e.id, e.json_cache, e.markdown_path, e.cache_updated_at
                FROM events e
                LEFT JOIN events_cache c ON c.id = e.id
                WHERE e.json_cache IS NOT NULL
                  AND (
                    c.id IS NULL
                    OR NOT EXISTS (
                        SELECT 1 FROM event_file_refs r WHERE r.event_id = e.id
                    )
                  )
                """
            ).fetchall()

            for row in rows:
                try:
                    event = Event.model_validate_json(row["json_cache"])
                except Exception:
                    continue
                cache_updated_at = row["cache_updated_at"] or time.time()
                self._sync_query_cache(conn, event, row["markdown_path"], cache_updated_at)

            if rows:
                conn.commit()
        finally:
            conn.close()

    def _is_cache_fresh(self, row: Dict[str, Any], cache_updated_at: Optional[float]) -> bool:
        if cache_updated_at is None:
            return False

        row_cache_updated_at = row.get("cache_updated_at")
        if (
            row_cache_updated_at is not None
            and abs(row_cache_updated_at - cache_updated_at) > 0.001
        ):
            return False

        path = Path(row["markdown_path"])
        if path.exists():
            current_mtime = path.stat().st_mtime
            if abs(current_mtime - row["mtime"]) > 0.001:
                return False
        return True

    # =========================================================================
    # 查询接口 (Read)
    # =========================================================================

    def _build_query_sql(
        self,
        base_sql: str,
        type: Optional[Union[str, EventType]] = None,
        source: Optional[Union[str, SourceType]] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Tuple[str, List[Any]]:
        """构建查询 SQL 和参数"""
        sql = base_sql
        params: List[Any] = []

        if type:
            sql += " AND type = ?"
            # Fix: Handle both Enum and str to prevent AttributeError
            type_val = type.value if hasattr(type, "value") else str(type)
            params.append(type_val)

        if source:
            sql += " AND source = ?"
            params.append(str(source.value if isinstance(source, SourceType) else source))

        if status:
            sql += " AND status = ?"
            params.append(status)

        if date_from:
            sql += " AND date >= ?"
            params.append(date_from)

        if date_to:
            sql += " AND date <= ?"
            params.append(date_to)

        if job_id:
            sql += " AND job_id = ?"
            params.append(job_id)

        return sql, params

    def query(
        self,
        type: Optional[Union[str, EventType]] = None,
        source: Optional[Union[str, SourceType]] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        统一查询接口

        返回: 元数据字典列表
        """
        base_sql = "SELECT * FROM events WHERE 1=1"
        query_sql, params = self._build_query_sql(
            base_sql, type, source, status, date_from, date_to, job_id
        )

        # 默认按时间倒序
        query_sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_conn()
        try:
            cursor = conn.execute(query_sql, params)
            return [dict(row) for row in cursor]
        finally:
            conn.close()

    def get_stats_daily(self, date_from: Optional[str] = None) -> Dict[str, int]:
        """统计每日事件数量"""
        query_sql = "SELECT date, COUNT(*) as count FROM events WHERE 1=1"
        params = []
        if date_from:
            query_sql += " AND date >= ?"
            params.append(date_from)

        query_sql += " GROUP BY date ORDER BY date ASC"

        conn = self._get_conn()
        try:
            cursor = conn.execute(query_sql, params)
            return {row["date"]: row["count"] for row in cursor}
        finally:
            conn.close()

    def get_stats_by_type(self, date_from: Optional[str] = None) -> Dict[str, int]:
        """统计每种类型的事件数量"""
        query_sql = "SELECT type, COUNT(*) as count FROM events WHERE 1=1"
        params = []
        if date_from:
            query_sql += " AND date >= ?"
            params.append(date_from)

        query_sql += " GROUP BY type ORDER BY count DESC"

        conn = self._get_conn()
        try:
            cursor = conn.execute(query_sql, params)
            return {row["type"]: row["count"] for row in cursor}
        finally:
            conn.close()

    def get_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询单个事件元数据"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_path(self, markdown_path: str) -> Optional[Dict[str, Any]]:
        """按文件路径查询"""
        # 统一路径格式为字符串
        path_str = str(Path(markdown_path).resolve())
        # 在实际存储中我们可能存储的是绝对路径，或者相对于 data_dir 的路径
        # 这里假设存的是绝对路径，或者调用者保证传入的 path 格式一致

        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM events WHERE markdown_path = ?", (path_str,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_file(
        self,
        file_path: str,
        limit: int = 50,
        type_filter: Optional[str] = None,
        time_window_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询与指定源文件相关的事件 (H2 Hybrid Timeline)

        Args:
            file_path: 文件相对路径 (e.g. src/dimcause/cli.py)
            limit: 返回数量限制
            type_filter: (H1) 按事件类型过滤 (e.g. "decision", "git_commit")
            time_window_days: 时间窗口过滤（天数），只返回该天数范围内的事件

        策略:
            优先使用 event_file_refs 精确/后缀匹配，必要时回退到 legacy LIKE 查询。
        """
        search_term = self._normalize_file_ref(str(file_path))
        file_name = Path(search_term).name or search_term

        conn = self._get_conn()
        try:
            ref_query_sql = """
                SELECT DISTINCT e.* FROM events e
                JOIN event_file_refs r ON r.event_id = e.id
                WHERE (
                    r.file_path = ?
                    OR r.file_path LIKE ?
                    OR r.file_name = ?
                )
            """
            ref_params: List[Any] = [search_term, f"%/{search_term}", file_name]

            if type_filter:
                ref_query_sql += " AND e.type = ?"
                ref_params.append(type_filter)

            if time_window_days is not None:
                ref_query_sql += " AND e.timestamp >= datetime('now', ?)"
                ref_params.append(f"-{time_window_days} days")

            ref_query_sql += " ORDER BY e.timestamp DESC LIMIT ?"
            ref_params.append(limit)

            results = [dict(row) for row in conn.execute(ref_query_sql, ref_params)]
            seen_ids = {row["id"] for row in results}

            if len(results) < limit:
                legacy_query_sql = """
                    SELECT * FROM events
                    WHERE (json_cache LIKE ? OR summary LIKE ?)
                """
                legacy_params: List[Any] = [f"%{search_term}%", f"%{search_term}%"]

                if seen_ids:
                    placeholders = ", ".join(["?"] * len(seen_ids))
                    legacy_query_sql += f" AND id NOT IN ({placeholders})"
                    legacy_params.extend(seen_ids)

                if type_filter:
                    legacy_query_sql += " AND type = ?"
                    legacy_params.append(type_filter)

                if time_window_days is not None:
                    legacy_query_sql += " AND timestamp >= datetime('now', ?)"
                    legacy_params.append(f"-{time_window_days} days")

                legacy_query_sql += " ORDER BY timestamp DESC LIMIT ?"
                legacy_params.append(max(limit - len(results), 0))
                results.extend(dict(row) for row in conn.execute(legacy_query_sql, legacy_params))

            return results[:limit]
        finally:
            conn.close()

    # 用户友好访问/兼容性的别名
    get_events_by_file = get_by_file

    def get_neighbors(self, event_id: str, n: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取事件的前后邻居

        Args:
            event_id: 中心事件 ID
            n: 前后各取多少条

        Returns:
            Dict: {"prev": [...], "next": [...]}
        """
        conn = self._get_conn()
        try:
            # 获取当前事件时间戳
            cursor = conn.execute("SELECT timestamp FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return {"prev": [], "next": []}

            current_ts = row["timestamp"]

            # 获取前序事件（早于当前时间）
            cursor = conn.execute(
                "SELECT * FROM events WHERE timestamp < ? ORDER BY timestamp DESC LIMIT ?",
                (current_ts, n),
            )
            prev_events = [dict(r) for r in cursor]
            # 反转以显示通向事件的时间顺序
            prev_events.reverse()

            # 获取后序事件（晚于当前时间）
            cursor = conn.execute(
                "SELECT * FROM events WHERE timestamp > ? ORDER BY timestamp ASC LIMIT ?",
                (current_ts, n),
            )
            next_events = [dict(r) for r in cursor]

            return {"prev": prev_events, "next": next_events}
        finally:
            conn.close()

    def count(self, **filters) -> int:
        """统计符合条件的事件数量"""
        # 复用 _build_query_sql 逻辑
        base_sql = "SELECT COUNT(*) FROM events WHERE 1=1"

        # 提取参数
        type_val = filters.get("type")
        source_val = filters.get("source")
        status_val = filters.get("status")
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        job_id = filters.get("job_id")

        sql, params = self._build_query_sql(
            base_sql,
            type=type_val,
            source=source_val,
            status=status_val,
            date_from=date_from,
            date_to=date_to,
            job_id=job_id,
        )

        conn = self._get_conn()
        try:
            return conn.execute(sql, params).fetchone()[0]
        finally:
            conn.close()

    def get_links(self, event_id: str) -> List[CausalLink]:
        """
        获取指定 Event 定义的因果链

        Args:
            event_id: 事件 ID

        Returns:
            List[CausalLink]
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM causal_links WHERE event_id = ?", (event_id,))
            links = []
            for row in cursor:
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    meta = {}

                links.append(
                    CausalLink(
                        source=row["source"],
                        target=row["target"],
                        relation=row["relation"],
                        weight=row["weight"],
                        metadata=meta,
                    )
                )
            return links
        finally:
            conn.close()

    @staticmethod
    def _serialize_link(link: CausalLink) -> Dict[str, Any]:
        return asdict(link)

    @staticmethod
    def _merge_links(existing: List[CausalLink], new_links: List[CausalLink]) -> List[CausalLink]:
        merged: Dict[Tuple[str, str, str], CausalLink] = {}

        for link in [*existing, *new_links]:
            key = (link.source, link.target, link.relation)
            if key not in merged:
                merged[key] = CausalLink(
                    source=link.source,
                    target=link.target,
                    relation=link.relation,
                    weight=link.weight,
                    metadata=dict(link.metadata or {}),
                )
                continue

            current = merged[key]
            current.weight = max(current.weight, link.weight)
            current.metadata.update(link.metadata or {})

        return list(merged.values())

    def upsert_links(self, event_id: str, links: List[CausalLink]) -> bool:
        """
        Merge outgoing links into a source event and persist them through SemanticEvent.

        `event_id` 必须是这些 links 的 source owner；否则 ontology domain 无法自洽。
        """
        if not links:
            return True

        event = self.load_event(event_id)
        row = self.get_by_id(event_id)
        if event is None or row is None:
            return False

        source_uri = (
            event.uri
            if isinstance(event, SemanticEvent) and event.uri
            else f"dev://event/{event.id}"
        )
        for link in links:
            if link.source not in {event_id, source_uri}:
                raise ValueError(
                    f"Link source {link.source} does not match owner event {event_id}/{source_uri}"
                )

        merged_links = self._merge_links(self.get_links(event_id), links)
        payload = event.model_dump(mode="json")
        payload["uri"] = source_uri
        payload["causal_links"] = [self._serialize_link(link) for link in merged_links]
        semantic_event = SemanticEvent.model_validate(payload)

        return self.add(
            semantic_event,
            row["markdown_path"],
            source_chunk_id=row.get("source_chunk_id"),
            source_layer=row.get("source_layer"),
        )

    def _deserialize_event_data(self, event_id: str, data: Dict[str, Any]) -> Event:
        payload = dict(data)
        links = self.get_links(event_id)
        if links and not payload.get("causal_links"):
            payload["causal_links"] = [self._serialize_link(link) for link in links]

        if payload.get("uri") or payload.get("causal_links"):
            return SemanticEvent.model_validate(payload)

        return Event.model_validate(payload)

    # =========================================================================
    # 加载接口 (Load)
    # =========================================================================

    def load_event(self, event_id: str) -> Optional[Event]:
        """
        加载完整 Event 对象

        策略:
        1. 尝试从 json_cache 加载
        2. 如果 cache 存在且有效，直接反序列化
        3. 如果 cache 缺失或失效（基于 mtime 检查），读取 Markdown
        """
        row = self.get_by_id(event_id)
        if not row:
            return None

        # 1. 尝试缓存
        if row["json_cache"]:
            try:
                if self._is_cache_fresh(row, row["cache_updated_at"]):
                    data = json.loads(row["json_cache"])
                    return self._deserialize_event_data(event_id, data)
            except Exception:
                pass

        conn = self._get_conn()
        try:
            cache_row = conn.execute(
                "SELECT json_data, last_updated FROM events_cache WHERE id = ?", (event_id,)
            ).fetchone()
        finally:
            conn.close()

        if cache_row:
            try:
                if self._is_cache_fresh(row, cache_row["last_updated"]):
                    data = json.loads(cache_row["json_data"])
                    return self._deserialize_event_data(event_id, data)
            except Exception:
                pass

        # 2. 读取文件
        path = Path(row["markdown_path"])
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            event = Event.from_markdown(content, file_path=str(path))
            links = self.get_links(event_id)
            if links:
                payload = event.model_dump(mode="json")
                payload["uri"] = f"dev://event/{event.id}"
                payload["causal_links"] = [self._serialize_link(link) for link in links]
                event = SemanticEvent.model_validate(payload)

            # 3. 异步更新缓存 (这里同步做简单的)
            self.update_cache(event_id, event)
            return event
        except Exception as e:
            print(f"File load failed for {path}: {e}")
            return None

    # =========================================================================
    # 写入接口 (Write)
    # =========================================================================

    def _new_wal_op_id(self, event_id: str) -> str:
        """为每次写入生成唯一 WAL 操作 ID，避免同 event_id 多次更新互相覆盖。"""
        return f"event-index:{event_id}:{time.time_ns()}"

    def _build_wal_payload(
        self,
        event: Event,
        markdown_path: str,
        source_chunk_id: Optional[str],
        source_layer: Optional[str],
        write_mode: str,
    ) -> Dict[str, Any]:
        return {
            "_dimcause_wal_op": self.WAL_EVENT_INDEX_WRITE,
            "write_mode": write_mode,
            "event": event.model_dump(mode="json"),
            "markdown_path": str(Path(markdown_path).resolve()),
            "source_chunk_id": source_chunk_id,
            "source_layer": source_layer,
        }

    def _replay_wal_entry(self, entry: WALEntry) -> None:
        """重放 EventIndex 待完成写入。"""
        payload = entry.data or {}
        if payload.get("_dimcause_wal_op") != self.WAL_EVENT_INDEX_WRITE:
            return

        raw_event = payload.get("event")
        markdown_path = payload.get("markdown_path")
        write_mode = payload.get("write_mode", "add")
        source_chunk_id = payload.get("source_chunk_id")
        source_layer = payload.get("source_layer")

        if not isinstance(raw_event, dict) or not markdown_path:
            self.wal.mark_failed(
                entry.id,
                "invalid event_index WAL payload",
                retry_count=entry.retry_count + 1,
            )
            return

        event = Event.model_validate(raw_event)
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if write_mode == "add_if_not_exists":
                cursor = conn.execute("SELECT 1 FROM events WHERE id = ?", (event.id,))
                if cursor.fetchone():
                    conn.rollback()
                    self.wal.mark_completed(entry.id)
                    return

            self._add_to_conn(conn, event, markdown_path, source_chunk_id, source_layer)
            conn.commit()
            self.wal.mark_completed(entry.id)
        except Exception as e:
            conn.rollback()
            self.wal.mark_failed(entry.id, str(e), retry_count=entry.retry_count + 1)
        finally:
            conn.close()

    def _recover_pending_writes(self) -> None:
        """启动时恢复 EventIndex 自己的未完成写入。"""
        if not self.wal:
            return

        try:
            pending_entries = self.wal.recover_pending()
        except Exception as e:
            logging.getLogger(__name__).warning("EventIndex WAL recovery skipped: %s", e)
            return

        for entry in pending_entries:
            if entry.data.get("_dimcause_wal_op") != self.WAL_EVENT_INDEX_WRITE:
                continue
            self._replay_wal_entry(entry)

    def _add_to_conn(
        self,
        conn,
        event: Event,
        markdown_path: str,
        source_chunk_id: Optional[str] = None,
        source_layer: Optional[str] = None,
    ) -> None:
        import json

        path_obj = Path(markdown_path).resolve()
        mtime = path_obj.stat().st_mtime if path_obj.exists() else time.time()
        cache_updated_at = time.time()

        tags_str = ",".join(event.tags)
        json_cache = event.model_dump_json()

        if isinstance(event, SemanticEvent) and event.causal_links:
            ontology = get_ontology()
            type_val = getattr(event.type, "value", str(event.type))
            event_type_str = to_ontology_event_class(event) or type_val.capitalize()

            for link in event.causal_links:
                rel_def = ontology.get_relation(link.relation)
                if not rel_def:
                    continue
                if rel_def.domain != "Any" and rel_def.domain != event_type_str:
                    raise ValueError(
                        f"Ontology Violation: Event {event.id} ({event_type_str}) "
                        f"cannot have relation '{link.relation}' (Domain: {rel_def.domain})"
                    )

        event_type_str = getattr(event.type, "value", str(event.type))
        graph_node_id = event.uri if isinstance(event, SemanticEvent) and event.uri else event.id

        conn.execute(
            """INSERT OR REPLACE INTO graph_nodes (id, type, data, last_updated)
            VALUES (?, ?, ?, ?)""",
            (graph_node_id, event_type_str, json_cache, time.time()),
        )

        conn.execute(
            """INSERT OR REPLACE INTO events (
                id, type, source, timestamp, date, summary, tags,
                markdown_path, mtime, job_id, status,
                schema_version, json_cache, cache_updated_at,
                source_chunk_id, source_layer, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id,
                getattr(event.type, "value", str(event.type)),
                getattr(event.source, "value", str(event.source)),
                event.timestamp.isoformat(),
                event.timestamp.strftime("%Y-%m-%d"),
                event.summary,
                tags_str,
                str(path_obj),
                mtime,
                event.metadata.get("job_id", ""),
                event.metadata.get("status", "active"),
                1,  # schema_version
                json_cache,
                cache_updated_at,
                source_chunk_id,
                source_layer,
                cache_updated_at,
            ),
        )
        self._sync_query_cache(conn, event, str(path_obj), cache_updated_at)

        if isinstance(event, SemanticEvent):
            cursor = conn.execute(
                "SELECT source, target, relation FROM causal_links WHERE event_id = ?",
                (event.id,),
            )
            old_links = cursor.fetchall()
            for row in old_links:
                conn.execute(
                    "DELETE FROM graph_edges WHERE source=? AND target=? AND relation=?",
                    (row[0], row[1], row[2]),
                )
            conn.execute("DELETE FROM causal_links WHERE event_id = ?", (event.id,))

            if event.causal_links:
                links_data = []
                for link in event.causal_links:
                    links_data.append(
                        (
                            link.source,
                            link.target,
                            link.relation,
                            link.weight,
                            json.dumps(link.metadata),
                            event.id,
                        )
                    )
                    conn.execute(
                        """INSERT OR IGNORE INTO graph_nodes (id, type, data, last_updated)
                        VALUES (?, 'unknown', '{}', ?)""",
                        (link.target, time.time()),
                    )
                    conn.execute(
                        """INSERT OR REPLACE INTO graph_edges (source, target, relation, weight, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            link.source,
                            link.target,
                            link.relation,
                            link.weight,
                            json.dumps(link.metadata),
                            mtime,
                        ),
                    )
                conn.executemany(
                    """INSERT INTO causal_links (source, target, relation, weight, metadata, event_id)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    links_data,
                )

    def add(
        self,
        event: Event,
        markdown_path: str,
        source_chunk_id: Optional[str] = None,
        source_layer: Optional[str] = None,
    ) -> bool:
        """添加/更新单个事件到索引"""
        # SchemaValidator 卡口：验证 Event.type 是否符合本体定义
        validator = get_schema_validator()
        validation = validator.validate(event)
        if validation.is_legacy:
            event.metadata.setdefault(
                "_schema_legacy",
                {
                    "type": validation.input_type,
                    "canonical_class": validation.ontology_class,
                    "status": validation.policy.status if validation.policy else "legacy-write",
                },
            )

        wal_op_id = self._new_wal_op_id(event.id)
        wal_payload = self._build_wal_payload(
            event,
            markdown_path,
            source_chunk_id,
            source_layer,
            write_mode="add",
        )
        conn = self._get_conn()
        try:
            self.wal.append_pending(wal_op_id, wal_payload)
            conn.execute("BEGIN IMMEDIATE")
            self._add_to_conn(conn, event, markdown_path, source_chunk_id, source_layer)
            conn.commit()
            self.wal.mark_completed(wal_op_id)
            return True
        except Exception as e:
            print(f"Index add failed: {e}")
            conn.rollback()
            self.wal.mark_failed(wal_op_id, str(e))
            return False
        finally:
            conn.close()

    def remove(self, event_id: str) -> bool:
        """从索引删除事件"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM events_cache WHERE id = ?", (event_id,))
            conn.execute("DELETE FROM event_file_refs WHERE event_id = ?", (event_id,))
            cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            # 由于开启了 FOREIGN_KEYS=ON 和 ON DELETE CASCADE，causal_links 会自动删除
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_cache(self, event_id: str, event: Event) -> None:
        """单独更新缓存"""
        conn = self._get_conn()
        try:
            json_cache = event.model_dump_json()
            cache_updated_at = time.time()
            row = conn.execute(
                "SELECT markdown_path FROM events WHERE id = ? LIMIT 1", (event_id,)
            ).fetchone()
            current_mtime = None
            if row:
                cache_path = Path(row["markdown_path"])
                if cache_path.exists():
                    current_mtime = cache_path.stat().st_mtime
            conn.execute(
                """
                UPDATE events
                SET json_cache = ?, cache_updated_at = ?, mtime = COALESCE(?, mtime)
                WHERE id = ?
            """,
                (json_cache, cache_updated_at, current_mtime, event_id),
            )
            if row:
                self._sync_query_cache(conn, event, row["markdown_path"], cache_updated_at)
            conn.commit()
        finally:
            conn.close()

    def invalidate_cache(self, event_id: str) -> None:
        """使缓存失效"""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE events
                SET json_cache = NULL, cache_updated_at = NULL
                WHERE id = ?
            """,
                (event_id,),
            )
            conn.execute("DELETE FROM events_cache WHERE id = ?", (event_id,))
            conn.execute("DELETE FROM event_file_refs WHERE event_id = ?", (event_id,))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # 同步维护 (Sync)
    # =========================================================================

    def sync(
        self,
        scan_paths: List[Union[str, Path]],
        base_docs_dir: Optional[Union[str, Path]] = None,
        base_data_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, int]:
        """
        增量同步：扫描目录，更新索引

        Args:
            scan_paths: 要扫描的目录或文件列表
            base_docs_dir: 基础文档目录 (默认: ./docs/logs/)
            base_data_dir: 基础数据目录 (默认: ~/.dimcause/events/)

        Returns:
            Dict: 统计信息 {"added": 0, "updated": 0, "skipped": 0, "errors": 0}

        Raises:
            ValueError: 如果 scan_paths 缺少必需的目录
        """
        # ========== 硬约束：防止误删数据源 ==========
        # EventIndex 必须同时扫描基础文档目录和基础数据目录
        # 这是对旧 indexer 行为的强制兼容要求

        # 规范化传入的路径
        normalized_paths = {str(Path(p).resolve()) for p in scan_paths}

        # 定义必需的目录 (支持依赖注入)
        project_root = Path.cwd()

        # Resolve defaults if not provided
        docs_dir = (
            Path(base_docs_dir).resolve()
            if base_docs_dir
            else (project_root / "docs" / "logs").resolve()
        )
        data_dir = (
            Path(base_data_dir).expanduser().resolve()
            if base_data_dir
            else (Path.home() / ".dimcause" / "events").resolve()
        )

        required_dirs = {
            str(docs_dir): "docs/logs/ (or configured docs_dir)",
            str(data_dir): "~/.dimcause/events/ (or configured data_dir)",
        }

        # 检查是否包含必需目录
        missing_dirs = []
        for required_path, display_name in required_dirs.items():
            # 检查是否有路径是必需目录或其父目录
            found = any(
                required_path.startswith(normalized) or normalized.startswith(required_path)
                for normalized in normalized_paths
            )
            if not found and Path(required_path).exists():
                # 只有当目录存在时才要求必须扫描
                missing_dirs.append(display_name)

        if missing_dirs:
            raise ValueError(
                f"EventIndex.sync() 缺少必需的数据源目录: {', '.join(missing_dirs)}. "
                f"必须同时扫描 docs/logs/ 和 ~/.dimcause/events/ 以保持与旧 indexer 的兼容性。"
                f"当前传入: {scan_paths}"
            )

        # ========== 原有逻辑 ==========
        stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}

        for path in scan_paths:
            path_obj = Path(path).resolve()

            if path_obj.is_file():
                if path_obj.suffix == ".md":
                    self._sync_file(path_obj, stats)
            elif path_obj.is_dir():
                for md_file in path_obj.rglob("*.md"):
                    self._sync_file(md_file, stats)

        return stats

    def _sync_file(self, path: Path, stats: Dict[str, int]) -> None:
        """处理单个文件的同步逻辑"""
        try:
            current_mtime = path.stat().st_mtime

            # 检查现有记录
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT mtime, id FROM events WHERE markdown_path = ?", (str(path),)
                ).fetchone()
            finally:
                conn.close()

            # 如果未更改则跳过
            if row and abs(row["mtime"] - current_mtime) < 0.001:
                stats["skipped"] += 1
                return

            # 解析并更新
            try:
                # 使用 errors='replace' 处理无法解码的字符
                content = path.read_text(encoding="utf-8", errors="replace")

                # 只处理符合 Frontmatter 格式的文件
                if not content.startswith("---"):
                    return

                event = Event.from_markdown(content, file_path=str(path))

                # 添加到索引
                if self.add(event, str(path)):
                    if row:
                        stats["updated"] += 1
                    else:
                        stats["added"] += 1
                else:
                    stats["errors"] += 1

            except UnicodeDecodeError:
                # 跳过无法解码的文件（可能是二进制或非 UTF-8 文件）
                # 不打印错误，因为可能扫描到系统文件
                stats["skipped"] += 1
                return
            except Exception as e:
                # 解析失败视为错误 (或者可以选择忽略非 Event 文件)
                # 只在调试模式下打印错误
                if path.parent.name not in [".gemini", "antigravity", "Cellar"]:
                    print(f"Failed to parse {path}: {e}")
                stats["errors"] += 1

        except Exception as e:
            # 静默跳过系统文件或缓存文件
            if path.parent.name not in [".gemini", "antigravity", "Cellar"]:
                print(f"Sync error for {path}: {e}")
            stats["errors"] += 1

    def rebuild(self) -> Dict[str, int]:
        """完全重建索引"""
        # 清空 events 表
        conn = self._get_conn()
        conn.execute("DELETE FROM events")
        conn.commit()
        conn.close()

        # 调用 sync (传入空路径列表，由上层调用者负责传入路径或 rebuild_event_index 函数处理)
        # 注意：EventIndex.rebuild 自身逻辑需修正以适配 sync 签名
        return self.sync(scan_paths=[])

    def migrate_v4(self) -> Dict[str, int]:
        """
        Phase 3.1 迁移: 从 events/causal_links 填充 graph_nodes 和 graph_edges 表。
        """
        stats = {"nodes": 0, "edges": 0}
        conn = self._get_conn()
        try:
            # 1. 迁移节点 (Events -> graph_nodes)
            logging.getLogger(__name__).info("正在迁移 Events 到 Graph Nodes...")
            cursor = conn.execute("SELECT count(*) FROM events")
            total_events = cursor.fetchone()[0]

            # 插入或更新 graph_nodes
            # 我们将 'json_cache' 作为 'data' 字段存储
            conn.execute("""
            INSERT OR REPLACE INTO graph_nodes (id, type, data, last_updated)
            SELECT
                id,
                type,
                json_cache,
                mtime
            FROM events
            WHERE json_cache IS NOT NULL
            """)
            stats["nodes"] = total_events

            # 2. 迁移边 (causal_links -> graph_edges)
            logging.getLogger(__name__).info("正在迁移 Causal Links 到 Graph Edges...")

            # 由于 graph_edges 没有 event_id 字段，我们直接投影 causal_links
            # created_at 来自父事件的时间戳 (或 mtime)
            conn.execute("""
            INSERT OR REPLACE INTO graph_edges (source, target, relation, weight, metadata, created_at)
            SELECT
                cl.source,
                cl.target,
                cl.relation,
                cl.weight,
                cl.metadata,
                e.mtime
            FROM causal_links cl
            JOIN events e ON cl.event_id = e.id
            """)

            cursor = conn.execute("SELECT count(*) FROM graph_edges")
            stats["edges"] = cursor.fetchone()[0]

            conn.commit()
            return stats
        except Exception as e:
            logging.getLogger(__name__).error(f"迁移失败: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # =========================================================================
    # V6.3 COALESCE 查询（Task 003）
    # =========================================================================

    def query_coalesced(
        self,
        type: Optional[Union[str, EventType]] = None,
        source: Optional[Union[str, SourceType]] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """COALESCE 查询：L2 优先于 L1；历史事件（无 chunk 来源）全量返回。

        路径 A：有 source_chunk_id 的流水线事件，同 chunk 中 L2 覆盖 L1。
        路径 B：source_chunk_id IS NULL 的历史事件，全量返回。
        两路 UNION ALL 后在外层应用 type/date/limit 过滤。
        """
        conn = self._get_conn()
        try:
            base_sql = """
            SELECT * FROM (
                SELECT e.* FROM events e
                WHERE e.source_chunk_id IS NOT NULL
                  AND (
                    (e.source_layer = 'l2')
                    OR
                    (e.source_layer = 'l1' AND NOT EXISTS (
                        SELECT 1 FROM events e2
                        WHERE e2.source_chunk_id = e.source_chunk_id
                          AND e2.source_layer = 'l2'))
                  )
                UNION ALL
                SELECT e.* FROM events e
                WHERE e.source_chunk_id IS NULL
            ) WHERE 1=1
            """
            sql, params = self._build_query_sql(
                base_sql,
                type=type,
                source=source,
                status=status,
                date_from=date_from,
                date_to=date_to,
                job_id=job_id,
            )
            sql += " ORDER BY date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_representative_events(self, chunk_ids: List[str]) -> List[Dict]:
        """per-chunk per-type 代表事件：同 chunk 同 type 有 L2 时只返回 L2。

        用于将同一 chunk 上 L1/L2 的提取结果去重合并，取最优层。
        """
        if not chunk_ids:
            return []
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(chunk_ids))
            sql = f"""
            SELECT * FROM events
            WHERE source_chunk_id IN ({placeholders})
              AND (
                (source_layer = 'l2')
                OR
                (source_layer = 'l1' AND NOT EXISTS (
                    SELECT 1 FROM events e2
                    WHERE e2.source_chunk_id = events.source_chunk_id
                      AND e2.type = events.type
                      AND e2.source_layer = 'l2'))
              )
            """
            rows = conn.execute(sql, chunk_ids).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # =========================================================================
    # Task 004: L1/L2 流水线支持方法
    # =========================================================================

    def add_if_not_exists(
        self,
        event: Event,
        markdown_path: str,
        source_chunk_id: Optional[str] = None,
        source_layer: Optional[str] = None,
    ) -> bool:
        """
        仅当 event_id 不存在时写入（L1 幂等语义）。
        使用 BEGIN IMMEDIATE 锁以消除 TOCTOU 竞态条件。
        已存在则跳过，返回 False。
        """
        # SchemaValidator 卡口：验证 Event.type 是否符合本体定义
        validator = get_schema_validator()
        validation = validator.validate(event)
        if validation.is_legacy:
            event.metadata.setdefault(
                "_schema_legacy",
                {
                    "type": validation.input_type,
                    "canonical_class": validation.ontology_class,
                    "status": validation.policy.status if validation.policy else "legacy-write",
                },
            )

        wal_op_id = self._new_wal_op_id(event.id)
        wal_payload = self._build_wal_payload(
            event,
            markdown_path,
            source_chunk_id,
            source_layer,
            write_mode="add_if_not_exists",
        )
        conn = self._get_conn()
        try:
            self.wal.append_pending(wal_op_id, wal_payload)
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("SELECT 1 FROM events WHERE id = ?", (event.id,))
            if cursor.fetchone():
                conn.rollback()
                self.wal.mark_completed(wal_op_id)
                return False
            self._add_to_conn(conn, event, markdown_path, source_chunk_id, source_layer)
            conn.commit()
            self.wal.mark_completed(wal_op_id)
            return True
        except Exception as e:
            print(f"Index add_if_not_exists failed: {e}")
            conn.rollback()
            self.wal.mark_failed(wal_op_id, str(e))
            return False
        finally:
            conn.close()

    def delete_by_chunk_layer(self, chunk_id: str, layer: str) -> int:
        """
        删除指定 chunk 的指定 layer 全部事件。

        用于 L2 重跑前清理旧 L2 事件。
        注意：不会级联删除 graph_nodes/graph_edges。

        Returns:
            int: 删除的行数
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM events WHERE source_chunk_id = ? AND source_layer = ?",
                (chunk_id, layer),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_legacy_type_counts(self) -> Dict[str, int]:
        """统计当前索引中各 legacy 类型的存量，供治理迁移使用。"""
        validator = get_schema_validator()
        legacy_types = sorted(validator.legacy_types)
        if not legacy_types:
            return {}

        placeholders = ", ".join(["?"] * len(legacy_types))
        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"""
                SELECT type, COUNT(*) AS count
                FROM events
                WHERE type IN ({placeholders})
                GROUP BY type
                ORDER BY count DESC, type ASC
                """,
                legacy_types,
            ).fetchall()
            return {row["type"]: row["count"] for row in rows}
        finally:
            conn.close()

    def get_legacy_governance_report(
        self, include_zero: bool = False
    ) -> List[LegacyTypeGovernanceRecord]:
        """输出 legacy 类型治理报告，合并策略定义与当前库存。"""
        validator = get_schema_validator()
        counts = self.get_legacy_type_counts()
        report: List[LegacyTypeGovernanceRecord] = []

        for policy_record in validator.list_legacy_policies():
            count = counts.get(policy_record.type_name, 0)
            if not include_zero and count == 0:
                continue
            report.append(
                LegacyTypeGovernanceRecord(
                    type_name=policy_record.type_name,
                    canonical_class=policy_record.canonical_class,
                    status=policy_record.status,
                    allow_write=policy_record.allow_write,
                    note=policy_record.note,
                    count=count,
                )
            )

        return report
