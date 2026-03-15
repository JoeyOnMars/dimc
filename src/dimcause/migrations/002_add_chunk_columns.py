"""
Migration 002: Add Chunk Columns

V6.3 Local-First 提取流水线所需列迁移（定案 8/9/10/26）。

为 events 表新增：
- source_chunk_id TEXT DEFAULT NULL       (来源 chunk 的 SHA256 ID)
- source_layer    TEXT DEFAULT NULL       (提取层：'l1' | 'l2' | NULL=历史事件)
- related_event_ids TEXT DEFAULT '[]'    (外键因果引用，JSON 数组，P博士裁定字段名)

CREATE INDEX：
- idx_chunk_layer ON events(source_chunk_id, source_layer, updated_at DESC)

字段名：P博士裁定（2026-02-23）统一使用 related_event_ids，
        对应 models.py Event.related_event_ids: List[str]。

V6.3 定案 8/9/10/26
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """获取 EventIndex 数据库路径"""
    return Path(os.path.expanduser("~/.dimcause/index.db"))


def upgrade(conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    执行迁移：为 events 表新增 chunk 相关列及索引

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
        # 读取当前列集合（PRAGMA table_info 守卫，防重复执行）
        cols = {row[1] for row in conn.execute("PRAGMA table_info(events)")}

        if "source_chunk_id" not in cols:
            logger.info("events 表新增 source_chunk_id 列...")
            conn.execute("ALTER TABLE events ADD COLUMN source_chunk_id TEXT DEFAULT NULL")

        if "source_layer" not in cols:
            logger.info("events 表新增 source_layer 列（CHECK 约束）...")
            conn.execute(
                "ALTER TABLE events ADD COLUMN source_layer TEXT DEFAULT NULL "
                "CHECK(source_layer IS NULL OR source_layer IN ('l1', 'l2'))"
            )

        if "related_event_ids" not in cols:
            logger.info("events 表新增 related_event_ids 列...")
            conn.execute("ALTER TABLE events ADD COLUMN related_event_ids TEXT DEFAULT '[]'")

        # 复合索引：L2 优先查询使用（COALESCE 过滤路径）
        logger.info("创建 idx_chunk_layer 索引...")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunk_layer "
            "ON events(source_chunk_id, source_layer, updated_at DESC)"
        )

        conn.commit()
        logger.info("migration 002 完成")
        return True

    except Exception as e:
        logger.error(f"migration 002 失败: {e}")
        conn.rollback()
        return False

    finally:
        if close_conn:
            conn.close()


def downgrade(conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    回滚迁移：删除索引（SQLite 不支持 DROP COLUMN，列无法回滚）

    注：SQLite 不支持 ALTER TABLE DROP COLUMN（3.35 以下），
    因此 downgrade 只删除索引，列保留但不使用。
    """
    close_conn = False
    if conn is None:
        db_path = get_db_path()
        if not db_path.exists():
            return True
        conn = sqlite3.connect(str(db_path))
        close_conn = True

    try:
        logger.info("回滚: 删除 idx_chunk_layer 索引...")
        conn.execute("DROP INDEX IF EXISTS idx_chunk_layer")
        conn.commit()
        logger.info("migration 002 回滚完成（列保留，索引已删除）")
        return True

    except Exception as e:
        logger.error(f"migration 002 回滚失败: {e}")
        return False

    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        success = downgrade()
    else:
        success = upgrade()

    sys.exit(0 if success else 1)
