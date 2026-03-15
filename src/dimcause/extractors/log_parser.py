"""
Log Parser (Task 2.0 Secondary Filter)

用于从非结构化日志内容中提取时间范围，辅助 Smart Scanning 判断。
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Common date formats in logs
# 2026-02-18 13:41:41
# [2026-02-18 13:41:41]
# 2026/02/18
DATE_PATTERNS = [
    r"(?<![/_])(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?!\.(?:md|json|txt|log))",  # ISO
    r"(?<![/_])(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})(?!\.(?:md|json|txt|log))",  # Slash
    r"(?<![/_])(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?!\.(?:md|json|txt|log))",  # ISO T
]


def extract_log_time_range(content: str) -> Optional[Tuple[datetime, datetime]]:
    """
    扫描内容，提取最早和最晚的时间戳。

    Args:
        content: 日志文本内容

    Returns:
        (min_time, max_time) 或 None
    """
    timestamps = []

    # 截取头尾各 2000 字符进行快速扫描 (性能优化)
    # 通常 header 和 footer 包含时间信息
    sample = content[:2000] + "\n" + content[-2000:] if len(content) > 4000 else content

    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, sample)
        for m in matches:
            try:
                # 尝试解析
                # 统一替换 / 为 - 和 T 为空格
                clean_ts = m.replace("/", "-").replace("T", " ")
                dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                timestamps.append(dt)
            except ValueError:
                continue

    if not timestamps:
        return None

    return (min(timestamps), max(timestamps))


def is_log_relevant(content: str, session_start: datetime, tolerance_seconds: int = 3600) -> bool:
    """
    判断日志内容是否在 Session 时间范围内 (Secondary Check)

    Args:
        content: 日志内容
        session_start: Session 启动时间
        tolerance_seconds: 容差 (默认1小时，允许早一点的 context)

    Returns:
        bool: True if relevant (content time >= session_start - tolerance)
              or True if no timestamps found (fallback to mtime)
    """
    time_range = extract_log_time_range(content)
    if not time_range:
        # 如果没找到时间戳，无法证伪，返回 True (让 mtime 决定)
        # 或者返回 None 让上层决定？
        # RFC-001: "If Content-Based Filter fails (no valid timestamps found), fallback to strictly File Metadata Filter."
        # 这里返回 False 代表 "Not Relevant by Content"?
        # 不，应该返回 True (Pass)，因为我们没有证据说它不相关。
        return True

    min_time, max_time = time_range
    cutoff = session_start - timedelta(seconds=tolerance_seconds)

    # 只要由任何内容晚于 cutoff，就认为相关
    # 例如：日志包含了昨天的回顾(早于 cutoff) 和 今天的对话(晚于 cutoff) -> Relevant
    if max_time >= cutoff:
        return True

    return False
