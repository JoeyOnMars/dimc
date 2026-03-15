"""
Migration 001: Add Event Vectors

为 MAL-SEARCH-001 添加向量存储表结构。

创建:
- event_vectors: 事件分块及其向量
- vectors_index: vec0 向量索引虚表
- vector_metadata: 向量-事件映射元数据

环境变量:
- DIMCAUSE_SKIP_EMBED_MIGRATION=1: 跳过批量向量初始化

MAL-SEARCH-001 v5.2
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 向量维度 (与 ModelConfig 一致)
# 当前临时使用 bge-small-en-v1.5 (384 维)
# 后续由 ModelFactory 动态设置
VECTOR_DIMENSION = 384


def get_db_path() -> Path:
    """获取 EventIndex 数据库路径"""
    return Path(os.path.expanduser("~/.dimcause/index.db"))


def check_vec0_available(conn: sqlite3.Connection) -> bool:
    """检查 sqlite-vec 扩展是否可用"""
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return True
    except (ImportError, Exception) as e:
        logger.warning(f"sqlite-vec 不可用: {e}")
        return False


def upgrade(conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    执行迁移：创建向量存储表结构

    Args:
        conn: 可选的数据库连接，未提供则自动创建

    Returns:
        bool: 迁移是否成功
    """
    close_conn = False
    if conn is None:
        db_path = get_db_path()
        if not db_path.exists():
            logger.error(f"数据库不存在: {db_path}")
            return False
        conn = sqlite3.connect(str(db_path))
        close_conn = True

    try:
        # 检查 vec0 可用性
        vec0_available = check_vec0_available(conn)
        if not vec0_available:
            logger.warning("sqlite-vec 不可用，将创建表结构但跳过 vec0 索引")

        cursor = conn.cursor()

        # 1. 创建 event_vectors 表
        logger.info("创建 event_vectors 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_vectors (
                event_id    TEXT    NOT NULL,
                chunk_seq   INTEGER NOT NULL,
                chunk_pos   INTEGER NOT NULL,
                chunk_text  TEXT    NOT NULL,
                embedding   BLOB    NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (event_id, chunk_seq),
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)

        # 2. 创建索引
        logger.info("创建索引 idx_event_vectors_event...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_vectors_event
            ON event_vectors(event_id)
        """)

        # 3. 创建 vec0 向量索引 (如果可用)
        if vec0_available:
            logger.info(f"创建 vectors_index vec0 虚表 ({VECTOR_DIMENSION} 维)...")
            try:
                cursor.execute(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS vectors_index
                    USING vec0(embedding float[{VECTOR_DIMENSION}])
                """)
            except sqlite3.OperationalError as e:
                logger.warning(f"创建 vec0 虚表失败: {e}")

        # 4. 创建 vector_metadata 表
        logger.info("创建 vector_metadata 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_metadata (
                rowid      INTEGER PRIMARY KEY,
                event_id   TEXT    NOT NULL,
                chunk_seq  INTEGER NOT NULL,
                UNIQUE(event_id, chunk_seq),
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)

        # 5. 创建元数据索引
        logger.info("创建索引 idx_vector_metadata_event...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vector_metadata_event
            ON vector_metadata(event_id)
        """)

        conn.commit()
        logger.info("迁移完成：表结构已创建")

        # 6. 批量向量初始化 (可跳过)
        if os.environ.get("DIMCAUSE_SKIP_EMBED_MIGRATION", "0") == "1":
            logger.info("DIMCAUSE_SKIP_EMBED_MIGRATION=1，跳过批量向量初始化")
        else:
            embed_existing_events(conn)

        return True

    except Exception as e:
        logger.error(f"迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        if close_conn:
            conn.close()


def embed_existing_events(conn: sqlite3.Connection, batch_size: int = 50) -> int:
    """
    为现有事件生成向量

    分页处理以避免内存溢出。

    Args:
        conn: 数据库连接
        batch_size: 每批处理事件数

    Returns:
        int: 处理的事件数量
    """
    logger.info("开始为现有事件生成向量...")

    cursor = conn.cursor()

    # 统计需要处理的事件数
    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE id NOT IN (SELECT DISTINCT event_id FROM event_vectors)
    """)
    total = cursor.fetchone()[0]

    if total == 0:
        logger.info("没有需要处理的事件")
        return 0

    logger.info(f"待处理事件: {total}")

    # 延迟导入以避免循环依赖
    try:
        from dimcause.extractors.chunking import EventChunker
    except ImportError as e:
        logger.warning(f"无法导入分块模块: {e}")
        return 0

    # 检查 vec0 是否可用
    vec0_available = check_vec0_available(conn)

    # 初始化 Embedding 模型
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        logger.info("正在加载 Embedding 模型 (BAAI/bge-small-en-v1.5)...")
        model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    except ImportError:
        logger.warning("缺少 sentence-transformers 或 numpy，无法生成向量。请安装依赖。")
        return 0
    except Exception as e:
        logger.error(f"模型加载失败: {e}")
        return 0
    chunker = EventChunker()
    processed = 0
    offset = 0

    while offset < total:
        # 分页读取事件
        cursor.execute(
            """
            SELECT id, type, timestamp, summary, content, source, json_cache
            FROM events
            WHERE id NOT IN (SELECT DISTINCT event_id FROM event_vectors)
            LIMIT ? OFFSET ?
        """,
            (batch_size, offset),
        )

        rows = cursor.fetchall()
        if not rows:
            break

        for row in rows:
            event_id, evt_type, timestamp, summary, content, source, json_cache = row

            try:
                # 简化 Event 对象用于分块
                # 注意: 这里使用简化版，避免完整反序列化
                event = type(
                    "SimpleEvent",
                    (),
                    {
                        "id": event_id,
                        "type": evt_type,
                        "timestamp": timestamp,
                        "summary": summary or "",
                        "content": content or "",
                        "source": source or "unknown",
                    },
                )()
                chunks = chunker.chunk_event(event)

                # 批量生成向量
                chunk_texts = [c.text for c in chunks]
                embeddings = model.encode(chunk_texts, convert_to_numpy=True)

                for i, chunk in enumerate(chunks):
                    embedding = embeddings[i].astype(np.float32).tobytes()

                    # 1. 插入元数据以获取 rowid
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO vector_metadata (event_id, chunk_seq)
                        VALUES (?, ?)
                    """,
                        (chunk.event_id, chunk.seq),
                    )
                    rowid = cursor.lastrowid

                    # 2. 插入存储表
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO event_vectors
                        (event_id, chunk_seq, chunk_pos, chunk_text, embedding)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            chunk.event_id,
                            chunk.seq,
                            chunk.pos,
                            chunk.text,
                            embedding,
                        ),
                    )

                    # 3. 插入向量索引 (vec0)
                    if vec0_available:
                        cursor.execute(
                            "INSERT INTO vectors_index(rowid, embedding) VALUES (?, ?)",
                            (rowid, embedding),
                        )

                processed += 1

            except Exception as e:
                logger.warning(f"处理事件 {event_id} 失败: {e}")

        conn.commit()
        offset += batch_size
        logger.info(f"进度: {processed}/{total} ({processed * 100 // total}%)")

    logger.info(f"批量向量初始化完成: 处理 {processed} 个事件")
    return processed


def downgrade(conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    回滚迁移：删除向量存储表结构

    Args:
        conn: 可选的数据库连接

    Returns:
        bool: 回滚是否成功
    """
    close_conn = False
    if conn is None:
        db_path = get_db_path()
        if not db_path.exists():
            return True  # 数据库不存在，视为已回滚
        conn = sqlite3.connect(str(db_path))
        close_conn = True

    try:
        cursor = conn.cursor()

        logger.info("回滚: 删除 vector_metadata 表...")
        cursor.execute("DROP TABLE IF EXISTS vector_metadata")

        logger.info("回滚: 删除 vectors_index 虚表...")
        cursor.execute("DROP TABLE IF EXISTS vectors_index")

        logger.info("回滚: 删除 event_vectors 表...")
        cursor.execute("DROP TABLE IF EXISTS event_vectors")

        conn.commit()
        logger.info("回滚完成")
        return True

    except Exception as e:
        logger.error(f"回滚失败: {e}")
        return False

    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    # 直接运行迁移
    logging.basicConfig(level=logging.INFO)

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        success = downgrade()
    else:
        success = upgrade()

    sys.exit(0 if success else 1)
