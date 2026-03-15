"""
ChunkStore：chunks.db 的单一访问入口。

每线程独享 SQLite 连接（实例级 TLS 缓存），WAL 模式，autocommit（isolation_level=None）。
状态机（FSM）：raw → embedded → extracted（单向不可逆）。
"""

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from dimcause.core.schema import ChunkRecord

# FSM 合法转换表（单向，不可逆）
VALID_TRANS: dict[str, list[str]] = {
    "raw": ["embedded"],
    "embedded": ["extracted"],
}


class ChunkStore:
    """chunks.db 的单一访问入口，每线程独享 SQLite 连接（TLS 缓存）。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()  # 实例级 TLS，避免多实例同线程共用连接
        self._ensure_schema()

    # ──────────────────────────────────────────
    # 静态工具
    # ──────────────────────────────────────────

    @staticmethod
    def make_chunk_id(source_event_id: str, content: str) -> str:
        """确定性 chunk ID：'chk_' + sha256(source_event_id:content[:64])[:16]"""
        key = f"{source_event_id}:{content[:64]}"
        return "chk_" + hashlib.sha256(key.encode()).hexdigest()[:16]

    # ──────────────────────────────────────────
    # 连接管理
    # ──────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """TLS 缓存连接，WAL 模式，autocommit。timeout=10.0 在 connect() 参数传。"""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10.0,
                isolation_level=None,  # 在 connect() 参数传，不是连接后赋值
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.execute("BEGIN")
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id           TEXT PRIMARY KEY,
                    source_event_id    TEXT NOT NULL,
                    session_id         TEXT NOT NULL,
                    content            TEXT,
                    status             TEXT NOT NULL DEFAULT 'raw'
                                       CHECK(status IN ('raw', 'embedded', 'extracted')),
                    confidence         TEXT DEFAULT 'low'
                                       CHECK(confidence IS NULL OR confidence IN ('low', 'high')),
                    needs_extraction   BOOLEAN DEFAULT 1,
                    embedding_version  INTEGER DEFAULT 0,
                    extraction_version INTEGER DEFAULT 0,
                    retry_count        INTEGER DEFAULT 0,
                    extraction_failed  BOOLEAN DEFAULT 0,
                    event_ids          TEXT DEFAULT '[]',
                    last_error         TEXT,
                    created_at         REAL NOT NULL,
                    updated_at         REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_needs ON chunks(needs_extraction)"
                " WHERE needs_extraction = 1"
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ──────────────────────────────────────────
    # 写操作
    # ──────────────────────────────────────────

    def add_chunk(self, chunk: ChunkRecord) -> None:
        """INSERT OR IGNORE（幂等）。event_ids 序列化为 JSON。时间戳使用调用方传入的值。"""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                chunk.chunk_id,
                chunk.source_event_id,
                chunk.session_id,
                chunk.content,
                chunk.status,
                chunk.confidence,
                int(chunk.needs_extraction),
                chunk.embedding_version,
                chunk.extraction_version,
                chunk.retry_count,
                int(chunk.extraction_failed),
                json.dumps(chunk.event_ids),
                chunk.last_error,
                chunk.created_at,
                chunk.updated_at,
            ),
        )

    def update_status(self, chunk_id: str, new_status: str) -> None:
        """Read-before-Write：先 SELECT 当前状态，校验 FSM，再 UPDATE。
        到达 extracted 时同步 needs_extraction=0。
        使用 BEGIN IMMEDIATE 排他锁，防止 TOCTOU 竞态。
        """
        conn = self._get_conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT status FROM chunks WHERE chunk_id=?", (chunk_id,)).fetchone()
            if row is None:
                raise ValueError(f"chunk_id not found: {chunk_id}")
            current = row["status"]
            if new_status not in VALID_TRANS.get(current, []):
                raise ValueError(f"FSM 非法转换: {current} → {new_status}")
            needs_extraction = 0 if new_status == "extracted" else 1
            conn.execute(
                "UPDATE chunks SET status=?, needs_extraction=?, updated_at=? WHERE chunk_id=?",
                (new_status, needs_extraction, time.time(), chunk_id),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

    # ──────────────────────────────────────────
    # 读操作
    # ──────────────────────────────────────────

    def get_chunk(self, chunk_id: str) -> Optional[ChunkRecord]:
        """按 chunk_id 查询，不存在返回 None。event_ids 反序列化为 List[str]。"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_pending_extraction(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ChunkRecord]:
        """返回 needs_extraction=1 且 extraction_failed=0 的 chunk，按 created_at 升序。
        session_id 不为 None 时只返回该 session 的结果；limit 限制最大返回条数。
        """
        conn = self._get_conn()
        sql = "SELECT * FROM chunks WHERE needs_extraction=1 AND extraction_failed=0"
        params: list = []
        if session_id is not None:
            sql += " AND session_id=?"
            params.append(session_id)
        sql += " ORDER BY created_at ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    # ──────────────────────────────────────────
    # 辅助
    # ──────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ChunkRecord:
        data = dict(row)
        data["event_ids"] = json.loads(data["event_ids"])
        data["needs_extraction"] = bool(data["needs_extraction"])
        data["extraction_failed"] = bool(data["extraction_failed"])
        return ChunkRecord(**data)

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
