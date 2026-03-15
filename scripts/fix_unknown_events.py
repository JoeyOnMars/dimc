#!/usr/bin/env python3
"""
Fix 'unknown' event types in historical data (Markdown only).
1. Scans DB for type='unknown'
2. Infers correct type/timestamp
3. Updates Markdown files
"""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path


def infer_type(content: str, summary: str) -> str:
    content_lower = (content + " " + summary).lower()

    # Task / Session (High Priority)
    if any(
        kw in content_lower
        for kw in [
            "session:",
            "wrap-up",
            "job end",
            "job start",
            "job:",
            "task:",
            "roadmap",
            "plan:",
            "todo",
            "会话",
            "总结",
            "汇报",
            "任务",
            "计划",
            "收工",
            "开工",
        ]
    ):
        return "task"

    # AI Conversation
    if any(
        kw in content_lower
        for kw in [
            "ai conversation",
            "chat",
            "prompt",
            "user request",
            "assistant",
            "对话",
            "提问",
            "ai回复",
            "claude",
            "gpt",
            "llm",
        ]
    ):
        return "ai_conversation"

    # Git Commit / Diff
    if any(
        kw in content_lower
        for kw in [
            "git commit",
            "merge branch",
            "feat:",
            "fix:",
            "chore:",
            "docs:",
            "提交",
            "合并",
            "代码提交",
        ]
    ):
        return "git_commit"

    # Decision
    if any(
        kw in content_lower
        for kw in [
            "decide",
            "decision",
            "choose",
            "selected",
            "adopting",
            "决定",
            "决策",
            "选择",
            "采用",
            "方案",
        ]
    ):
        return "decision"

    # Test / Diagnostic
    if any(
        kw in content_lower
        for kw in [
            "test",
            "debug",
            "audit",
            "verify",
            "check",
            "error",
            "fail",
            "测试",
            "调试",
            "验证",
            "检查",
            "错误",
            "失败",
            "排查",
            "报错",
        ]
    ):
        return "diagnostic"

    # Code Change
    if any(
        kw in content_lower
        for kw in [
            "refactor",
            "update code",
            "modify",
            "implementation",
            "重构",
            "修改",
            "实现",
            "更新",
            "优化",
        ]
    ):
        return "code_change"

    # Research / Reasoning
    if any(
        kw in content_lower
        for kw in [
            "research",
            "study",
            "learn",
            "reasoning",
            "why",
            "调研",
            "研究",
            "学习",
            "分析",
            "因为",
            "仅仅是",
        ]
    ):
        return "reasoning"

    return "unknown"


def infer_timestamp_from_path(path_str: str) -> datetime:
    """提取时间戳: event_20260120162601_..."""
    basename = os.path.basename(path_str)
    # Match patterns: event_YYYYMMDDHHMMSS or evt_ai_YYYYMMDDHHMMSS
    match = re.search(r"(\d{14})", basename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return None


def update_markdown(file_path: Path, new_type: str, new_ts: datetime) -> bool:
    if not file_path.exists():
        return False

    content = file_path.read_text(encoding="utf-8")

    content_new = content

    # Regex replace frontmatter TYPE
    # type: unknown -> type: new_type
    # Also handle legacy types: session-end, job-start, job-end, ...
    if new_type != "unknown":
        # Replace 'type: unknown' OR 'type: session-.*' OR 'type: job-.*'
        pattern = r"^type:\s*(unknown|session-[\w-]+|job-[\w-]+)"
        content_new = re.sub(pattern, f"type: {new_type}", content_new, flags=re.MULTILINE)

    # Regex replace frontmatter TIMESTAMP
    if new_ts:
        ts_iso = new_ts.isoformat()
        if re.search(r"^timestamp:", content, flags=re.MULTILINE):
            # Only replace if it matches "now" or "sync time" pattern?
            # Actually, trust filename more than existing timestamp for these unknown events
            content_new = re.sub(
                r"^timestamp:.*", f"timestamp: {ts_iso}", content_new, flags=re.MULTILINE
            )

    if content != content_new:
        file_path.write_text(content_new, encoding="utf-8")
        return True
    return False


def main():
    db_path = os.path.expanduser("~/.dimcause/index.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all unknown events (content is NOT in DB, read from file)
    cursor.execute("SELECT id, markdown_path, summary, timestamp FROM events WHERE type='unknown'")
    rows = cursor.fetchall()

    print(f"Found {len(rows)} unknown events.")

    fixed_count = 0

    for row in rows:
        evt_id, md_path, summary, curr_ts = row

        if not md_path or not os.path.exists(md_path):
            print(f"Skipping {evt_id}: File not found {md_path}")
            continue

        # Read content for inference
        try:
            content = Path(md_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"Skipping {evt_id}: Read error {e}")
            continue

        new_type = infer_type(content, summary or "")
        new_ts = infer_timestamp_from_path(md_path)

        changes = []
        if new_type != "unknown":
            changes.append(f"type -> {new_type}")
        if new_ts:
            changes.append(f"ts -> {new_ts}")

        if changes:
            print(f"Fixing {evt_id}: {', '.join(changes)}")
            if update_markdown(Path(md_path), new_type, new_ts):
                fixed_count += 1
        else:
            print(f"Skipping {evt_id}: Could not infer (summary: {summary[:30]}...)")

    conn.close()
    print(f"Done. Updated {fixed_count} markdown files.")
    print("Run 'dimc index' to sync DB.")


if __name__ == "__main__":
    main()
