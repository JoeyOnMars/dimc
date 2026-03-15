"""
智能索引系统 (Phase 4)

特性:
1. SQLite 增量索引 (只处理变化的文件)
2. 热/冷数据分离 (可配置天数)
3. 从 SQLite 生成 Markdown 视图
4. 并发安全 (文件锁保护)
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dimcause.core.schema import parse_frontmatter
from dimcause.utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    """索引统计信息"""

    processed: int = 0
    skipped: int = 0
    errors: int = 0
    hot: int = 0
    archive: int = 0


@dataclass
class InferredLogRecord:
    """从标准日志路径保守推断出的最小索引记录。"""

    type: str
    job_id: str
    date: str
    status: str
    description: str
    tags: list[str]


def get_logs_dir() -> Path:
    """获取日志目录"""
    return get_config().logs_dir


def get_index_db() -> Path:
    """获取索引数据库路径"""
    return get_config().index_db


def init_db(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """初始化 SQLite 数据库"""
    if conn is None:
        db_path = get_index_db()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            mtime REAL,
            type TEXT,
            job_id TEXT,
            date TEXT,
            status TEXT,
            description TEXT,
            tags TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON logs(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON logs(type)")
    conn.commit()
    return conn


def scan_log_files() -> list[Path]:
    """扫描所有需要索引的日志文件"""
    logs_dir = get_logs_dir()
    files = []

    # 扫描 daily end.md
    files.extend(logs_dir.glob("*/*/end.md"))

    # 扫描 job end.md
    files.extend(logs_dir.glob("*/*/jobs/*/end.md"))

    return files


def scan_task_files() -> list[Path]:
    """扫描所有 Task 文件 (Phase 1 重构: 统一索引)"""
    import os

    # Task 数据存储在 ~/.dimcause/events
    events_dir = Path(os.path.expanduser("~/.dimcause/events"))
    if not events_dir.exists():
        return []

    files = []
    # 扫描所有 .md 文件
    files.extend(events_dir.glob("**/*.md"))

    return files


def update_index() -> dict:
    """
    增量更新索引 (并发安全)

    Returns:
        统计信息字典
    """
    from dimcause.utils.lock import with_lock

    logs_dir = get_logs_dir()
    stats = IndexStats()

    # 使用锁保护整个索引过程
    with with_lock("index-update"):
        db_path = get_index_db()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 使用上下文管理器确保连接正确关闭
        with sqlite3.connect(db_path) as conn:
            init_db(conn)

            # 获取已索引文件
            cursor = conn.execute("SELECT path, mtime FROM logs")
            indexed = {row[0]: row[1] for row in cursor}

            # Phase 1 重构: 同时扫描日志和任务文件
            all_files = list(scan_log_files()) + list(scan_task_files())

            for log_file in all_files:
                # Phase 1: 处理来自不同数据源的文件
                try:
                    rel_path = str(log_file.relative_to(logs_dir))
                except ValueError:
                    # 文件不在 logs_dir 下，使用绝对路径作为标识
                    rel_path = str(log_file)

                try:
                    current_mtime = log_file.stat().st_mtime
                except OSError as e:
                    print(f"Cannot stat file {rel_path}: {e}")
                    stats.errors += 1
                    continue

                # 跳过未修改的文件
                if rel_path in indexed and indexed[rel_path] >= current_mtime:
                    stats.skipped += 1
                    continue

                # 解析并索引
                try:
                    content = log_file.read_text(encoding="utf-8")
                    meta = parse_frontmatter(content)

                    if meta is None:
                        inferred = _infer_log_record_from_path(rel_path, content)
                        if inferred is None:
                            # Schema 验证失败，且无法从标准日志路径安全推断，跳过此文件
                            logger.warning(f"Failed to parse frontmatter: {rel_path}")
                            stats.errors += 1
                            continue

                        conn.execute(
                            """
                            INSERT OR REPLACE INTO logs
                            (path, mtime, type, job_id, date, status, description, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                rel_path,
                                current_mtime,
                                inferred.type,
                                inferred.job_id,
                                inferred.date,
                                inferred.status,
                                inferred.description,
                                ",".join(inferred.tags),
                            ),
                        )
                    else:
                        # Phase 1: 处理 type_hint (用于 events 目录的文件)
                        event_type = getattr(meta.type, "value", str(meta.type))
                        if event_type == "unknown":
                            # 尝试从原始 frontmatter 获取 type_hint
                            import re

                            match = re.search(r"^type_hint:\s*(.+)$", content, re.MULTILINE)
                            if match:
                                event_type = match.group(1).strip()

                        conn.execute(
                            """
                            INSERT OR REPLACE INTO logs
                            (path, mtime, type, job_id, date, status, description, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                rel_path,
                                current_mtime,
                                event_type,  # 使用 type_hint 如果 type 是 unknown
                                getattr(meta, "job_id", ""),
                                str(meta.date),
                                getattr(meta.status, "value", str(meta.status)),
                                meta.description,
                                ",".join(meta.tags),
                            ),
                        )

                    stats.processed += 1
                    logger.debug(f"Indexed: {rel_path}")
                except UnicodeDecodeError as e:
                    print(f"Encoding error in {rel_path}: {e}")
                    stats.errors += 1
                except Exception as e:
                    print(f"Failed to index {rel_path}: {e}")
                    stats.errors += 1

            conn.commit()

            # 生成 Markdown 视图
            md_stats = generate_markdown_views(conn)
            stats.hot = md_stats["hot"]
            stats.archive = md_stats["archive"]

    logger.info(
        f"Index updated: {stats.processed} processed, {stats.skipped} skipped, {stats.errors} errors"
    )

    return {
        "processed": stats.processed,
        "skipped": stats.skipped,
        "errors": stats.errors,
        "hot": stats.hot,
        "archive": stats.archive,
    }


def _extract_date_from_path(rel_path: str) -> str:
    """从路径提取日期 (如 2026/01-15/end.md -> 2026-01-15)"""
    import re

    match = re.search(r"(\d{4})/(\d{2}-\d{2})", rel_path)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return ""


def _extract_summary_from_content(content: str, fallback: str) -> str:
    """从正文提取一行简短描述，避免把整个文件塞进索引摘要。"""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return fallback

    summary = lines[0]
    if len(summary) > 120:
        summary = summary[:117] + "..."
    return summary


def _infer_log_record_from_path(rel_path: str, content: str) -> Optional[InferredLogRecord]:
    """
    从标准日志路径保守推断索引记录。

    只覆盖 logs 目录里的结构化 end.md：
    - YYYY/MM-DD/end.md -> session-end
    - YYYY/MM-DD/jobs/<job_id>/end.md -> job-end
    """
    normalized = Path(rel_path).as_posix()
    date = _extract_date_from_path(normalized)
    if not date or not normalized.endswith("/end.md"):
        return None

    parts = Path(normalized).parts
    if len(parts) == 3:
        return InferredLogRecord(
            type="session-end",
            job_id="",
            date=date,
            status="active",
            description=_extract_summary_from_content(content, "Session end log"),
            tags=["inferred", "frontmatter-missing"],
        )

    if len(parts) == 5 and parts[2] == "jobs":
        job_id = parts[3].strip().lower().replace(" ", "-").replace("_", "-")
        if not job_id:
            return None

        return InferredLogRecord(
            type="job-end",
            job_id=job_id,
            date=date,
            status="active",
            description=_extract_summary_from_content(content, f"Job {job_id} end log"),
            tags=["inferred", "frontmatter-missing"],
        )

    return None


def generate_markdown_views(conn: sqlite3.Connection) -> dict:
    """从 SQLite 生成 INDEX.md 和 INDEX_ARCHIVE.md"""
    logs_dir = get_logs_dir()
    threshold = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Hot Index (最近7天)
    cursor = conn.execute(
        """
        SELECT date, job_id, status, description, tags, path
        FROM logs
        WHERE date >= ? AND type IN ('job-end', 'session-end')
        ORDER BY date DESC, job_id
    """,
        (threshold,),
    )
    hot_rows = cursor.fetchall()

    hot_content = _generate_table(
        "🔥 Active Context (Last 7 Days)",
        "> High-resolution index for immediate context.",
        hot_rows,
        detailed=True,
    )
    hot_content += "\n---\n*For older history, see [INDEX_ARCHIVE.md](INDEX_ARCHIVE.md)*\n"
    (logs_dir / "INDEX.md").write_text(hot_content, encoding="utf-8")

    # Archive (7天前)
    cursor = conn.execute(
        """
        SELECT date, job_id, status, description, tags, path
        FROM logs
        WHERE date < ? AND type IN ('job-end', 'session-end')
        ORDER BY date DESC, job_id
    """,
        (threshold,),
    )
    archive_rows = cursor.fetchall()

    if archive_rows:
        archive_content = _generate_table(
            "🏛️ Knowledge Archive (Older than 7 days)",
            "> Low-resolution index for long-term recall.",
            archive_rows,
            detailed=False,
        )
        (logs_dir / "INDEX_ARCHIVE.md").write_text(archive_content, encoding="utf-8")

    return {"hot": len(hot_rows), "archive": len(archive_rows)}


def _generate_table(title: str, subtitle: str, rows: list, detailed: bool = True) -> str:
    """生成 Markdown 表格"""
    lines = [
        f"# {title}",
        subtitle,
        "",
        "| Date | Job | Status | Summary | Tags |",
        "|------|-----|--------|---------|------|",
    ]

    current_date = ""
    for date, job_id, status, desc, tags, path in rows:
        date_display = f"**{date}**" if date != current_date else ""
        current_date = date

        summary = desc if detailed else (desc.split(".")[0] if desc else "")
        if len(summary) > 80:
            summary = summary[:77] + "..."

        tags_str = ", ".join(f"`{t}`" for t in tags.split(",") if t)
        job_display = job_id or "daily"
        link = f"[{job_display}]({path})"

        lines.append(f"| {date_display} | {link} | {status} | {summary} | {tags_str} |")

    return "\n".join(lines)


def rebuild_index() -> dict:
    """强制重建索引 (删除旧数据)"""
    db_path = get_index_db()
    if db_path.exists():
        db_path.unlink()
    return update_index()


def query_index(
    days: int = 7,
    status: Optional[str] = None,
    job_id: Optional[str] = None,
    type: Optional[str] = None,
) -> list[dict]:
    """
    查询索引 (Phase 1 重构: 支持 type 过滤)

    Args:
        days: 查询最近多少天
        status: 按状态过滤
        job_id: 按 job_id 过滤 (支持模糊匹配)
        type: 按类型过滤 (如 'task', 'job-end', 'session-end')
    """
    conn = init_db()
    threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    query = "SELECT * FROM logs WHERE date >= ?"
    params = [threshold]

    if status:
        query += " AND status = ?"
        params.append(status)

    if job_id:
        query += " AND job_id LIKE ?"
        params.append(f"%{job_id}%")

    # Phase 1: 支持按类型过滤
    if type:
        query += " AND type = ?"
        params.append(type)

    query += " ORDER BY date DESC"

    cursor = conn.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    results = []

    for row in cursor:
        results.append(dict(zip(columns, row, strict=False)))

    conn.close()
    return results
