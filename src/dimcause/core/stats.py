"""
统计模块

功能:
1. 日志统计 (数量、完成率等)
2. Token 消耗估算
3. 活动趋势分析
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def get_root_dir() -> Path:
    """获取项目根目录"""
    from dimcause.utils.config import get_config

    return get_config().root_dir


def get_logs_dir() -> Path:
    """获取日志目录"""
    return get_root_dir() / "docs" / "logs"


def get_stats() -> dict:
    """
    获取基本统计信息

    Returns:
        统计数据字典
    """
    logs_dir = get_logs_dir()
    index_db = logs_dir / ".index.db"

    stats = {
        "total_logs": 0,
        "active_days": 0,
        "completed_jobs": 0,
        "recent_activity": [],
    }

    # 从数据库统计
    if index_db.exists():
        try:
            conn = sqlite3.connect(index_db)

            # 总日志数
            cursor = conn.execute("SELECT COUNT(*) FROM logs")
            stats["total_logs"] = cursor.fetchone()[0]

            # 活跃天数
            cursor = conn.execute("SELECT COUNT(DISTINCT date) FROM logs")
            stats["active_days"] = cursor.fetchone()[0]

            # 已完成任务
            cursor = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE type = 'job-end' AND status = 'done'"
            )
            stats["completed_jobs"] = cursor.fetchone()[0]

            # 近期活动
            cursor = conn.execute("""
                SELECT date, job_id, description
                FROM logs
                ORDER BY date DESC
                LIMIT 5
            """)
            for row in cursor.fetchall():
                date, job_id, desc = row
                activity = f"[{date}] {job_id or 'daily'}"
                if desc:
                    activity += f" - {desc[:40]}"
                stats["recent_activity"].append(activity)

            conn.close()
        except Exception:
            pass

    # 回退: 扫描文件
    if stats["total_logs"] == 0:
        for _end_file in logs_dir.rglob("**/end.md"):
            stats["total_logs"] += 1

    return stats


def get_token_stats() -> dict:
    """
    获取 Token 消耗统计

    基于捕获的对话内容估算 Token 数量。
    使用简化的估算: 1 token ≈ 4 个字符 (英文) 或 1.5 个字符 (中文)

    Returns:
        Token 统计字典
    """
    logs_dir = get_logs_dir()
    capture_dir = logs_dir / "captures"

    stats = {
        "today": 0,
        "week": 0,
        "month": 0,
        "by_model": {},
    }

    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # 扫描捕获的内容
    if capture_dir.exists():
        for capture_file in capture_dir.rglob("*.md"):
            try:
                content = capture_file.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)

                # 从文件名提取日期
                file_date = _extract_date_from_path(capture_file)
                if file_date:
                    if file_date == today:
                        stats["today"] += tokens
                    if file_date >= week_ago:
                        stats["week"] += tokens
                    if file_date >= month_ago:
                        stats["month"] += tokens

                # 尝试检测模型
                model = _detect_model(content)
                if model:
                    stats["by_model"][model] = stats["by_model"].get(model, 0) + tokens
            except Exception:
                pass

    # 如果没有 capture 目录，从日志内容估算
    if stats["month"] == 0:
        for log_file in logs_dir.rglob("**/*.md"):
            if log_file.name in ["INDEX.md", "INDEX_ARCHIVE.md"]:
                continue
            try:
                content = log_file.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)

                file_date = _extract_date_from_path(log_file)
                if file_date:
                    if file_date == today:
                        stats["today"] += tokens
                    if file_date >= week_ago:
                        stats["week"] += tokens
                    if file_date >= month_ago:
                        stats["month"] += tokens
            except Exception:
                pass

    return stats


def estimate_tokens(text: str) -> int:
    """
    估算文本的 Token 数量

    使用简化规则:
    - 英文: 约 4 字符 = 1 token
    - 中文: 约 1.5 字符 = 1 token
    - 代码: 约 3 字符 = 1 token

    Args:
        text: 要估算的文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0

    # 分离中文和其他字符
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - chinese_chars

    # 估算 token 数
    chinese_tokens = chinese_chars / 1.5
    other_tokens = other_chars / 4

    return int(chinese_tokens + other_tokens)


def _extract_date_from_path(filepath: Path) -> Optional[datetime.date]:
    """从文件路径提取日期"""
    path_str = str(filepath)

    # 尝试匹配 YYYY/MM-DD 格式
    match = re.search(r"(\d{4})/(\d{2})-(\d{2})", path_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError:
            pass

    # 尝试匹配 YYYY-MM-DD 格式
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", path_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError:
            pass

    return None


def _detect_model(content: str) -> Optional[str]:
    """从内容检测使用的 AI 模型"""
    content_lower = content.lower()

    patterns = [
        (r"claude|anthropic", "Claude"),
        (r"gpt-4|openai", "GPT-4"),
        (r"gpt-3\.5", "GPT-3.5"),
        (r"gemini|google", "Gemini"),
        (r"antigravity", "Antigravity"),
    ]

    for pattern, model_name in patterns:
        if re.search(pattern, content_lower):
            return model_name

    return None


def get_activity_trend(days: int = 30) -> list[dict]:
    """
    获取活动趋势数据

    Args:
        days: 统计天数

    Returns:
        每日活动数据列表
    """
    logs_dir = get_logs_dir()
    index_db = logs_dir / ".index.db"

    trend = []

    if index_db.exists():
        try:
            conn = sqlite3.connect(index_db)
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            cursor = conn.execute(
                """
                SELECT date, COUNT(*) as count
                FROM logs
                WHERE date >= ?
                GROUP BY date
                ORDER BY date
            """,
                (cutoff,),
            )

            for row in cursor.fetchall():
                trend.append(
                    {
                        "date": row[0],
                        "count": row[1],
                    }
                )

            conn.close()
        except Exception:
            pass

    return trend
