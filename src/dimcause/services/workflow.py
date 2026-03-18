"""
工作流业务逻辑 (从 CLI 抽取)

这个模块包含纯业务逻辑，不包含任何 UI/交互代码。
便于测试和复用。
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """工作流执行结果"""

    success: bool
    message: str
    data: Optional[dict] = None


# === 日志模板 ===

DAILY_START_TEMPLATE = """---
id: "{session_id}"
type: session-start
created_at: "{iso_timestamp}"
date: "{date}"
status: active
---

# 🌅 会话开始: {date}

## 🎯 今日计划

- [ ]

## 🧠 上下文恢复

"""


DAILY_END_TEMPLATE = """---
id: "{session_id}"
type: session-end
created_at: "{iso_timestamp}"
date: "{date}"
status: done
description: "会话总结"
tags: []
---

# 🌙 会话结束: {date}

## 📅 今日成果 (Achievements)

### 1.
-

## 🔴 未完任务 (Pending Tasks)

| 任务 ID | 描述 | 状态 | 下一步 |
|:---|:---|:---|:---|
| | | | |

## ⭐ 代码现状 (Code Status)

## 🧩 任务详情 (Job Highlights)

## 🧱 遗留问题 (Legacy Issues)

## 🚀 明日开工指南 (Next Session Guide)

### 优先级
1.
2.
3.

"""


JOB_START_TEMPLATE = """---
type: job-start
job_id: "{job_id}"
date: "{date}"
---

# 🎯 任务开始: {job_id}

## 🏁 任务目标


## 🗺️ 实施计划


"""


JOB_END_TEMPLATE = """---
type: job-end
job_id: "{job_id}"
date: "{date}"
status: done
description: ""
tags: []
---

# ✅ 任务结束: {job_id}

## 📝 任务总结


## 🎉 完成的内容


## 🧱 遗留问题


"""


# === 目录和路径工具 ===


def get_root_dir() -> Path:
    """获取项目根目录"""
    from dimcause.utils.config import get_config

    return get_config().root_dir


def get_logs_dir() -> Path:
    """获取日志目录"""
    from dimcause.utils.config import get_config

    return get_config().logs_dir


def get_today_str() -> str:
    """获取今天的日期字符串"""
    tz_name = os.environ.get("TZ", "Asia/Shanghai")
    try:
        import pytz

        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%Y-%m-%d")


def get_today_dir() -> Path:
    """获取今天的日志目录"""
    tz_name = os.environ.get("TZ", "Asia/Shanghai")
    try:
        import pytz

        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    year_str = now.strftime("%Y")
    day_str = now.strftime("%m-%d")
    return get_logs_dir() / year_str / day_str


# === 日志创建工作流 ===


def create_daily_log(log_type: str) -> WorkflowResult:
    """
    创建每日日志 (start.md 或 end.md)

    Args:
        log_type: "start" 或 "end"

    Returns:
        WorkflowResult 包含成功状态和消息
    """
    from dimcause.utils.state import get_root_dir, resolve_session_path

    try:
        # Resolve path based on Architecture V6.0 (Session-Centric)
        log_file, seq_id = resolve_session_path(log_type)
    except Exception as e:
        return WorkflowResult(success=False, message=f"Failed to resolve log path: {e}")

    if log_file.exists() and log_file.stat().st_size > 0:
        rel_path = log_file.relative_to(get_root_dir())
        return WorkflowResult(
            success=False, message=f"日志已存在: {rel_path}", data={"path": str(log_file)}
        )

    # Ensure parent dir exists (e.g. 2026/02-14)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Calculate session ID: YYYY-MM-DD-SEQ
    session_date = log_file.parent.name  # 02-14
    session_year = log_file.parent.parent.name  # 2026

    # ISO Time
    now = datetime.now().astimezone()
    iso_timestamp = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")  # Use current date for display

    # ID uses directory date for consistency
    full_date_id = f"{session_year}-{session_date}"
    session_id = f"{full_date_id}-{seq_id}"

    if log_type == "start":
        template = DAILY_START_TEMPLATE.format(
            session_id=session_id, iso_timestamp=iso_timestamp, date=date_str
        )
    else:
        template = DAILY_END_TEMPLATE.format(
            session_id=session_id, iso_timestamp=iso_timestamp, date=date_str
        )

    log_file.write_text(template, encoding="utf-8")

    return WorkflowResult(
        success=True, message=f"日志已创建: {log_file.name}", data={"path": str(log_file)}
    )


def create_job_log(job_id: str, log_type: str) -> WorkflowResult:
    """
    创建 Job 日志 (start.md 或 end.md)

    Args:
        job_id: 任务 ID
        log_type: "start" 或 "end"

    Returns:
        WorkflowResult 包含成功状态和消息
    """
    # 标准化 job_id
    job_id = job_id.lower().replace(" ", "-")

    today_dir = get_today_dir()
    job_dir = today_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = "job-start.md" if log_type == "start" else "job-end.md"
    log_file = job_dir / filename

    if log_file.exists() and log_type == "start":
        return WorkflowResult(
            success=False, message=f"任务已存在: {job_id}", data={"path": str(log_file)}
        )

    date_str = get_today_str()

    if log_type == "start":
        template = JOB_START_TEMPLATE.format(job_id=job_id, date=date_str)
    else:
        template = JOB_END_TEMPLATE.format(job_id=job_id, date=date_str)

    log_file.write_text(template, encoding="utf-8")

    return WorkflowResult(
        success=True,
        message=f"{'开始' if log_type == 'start' else '结束'}任务: {job_id}",
        data={"path": str(log_file), "job_id": job_id},
    )


# === 完整工作流 ===


def start_daily_workflow() -> WorkflowResult:
    """
    执行完整的开工工作流

    包括:
    1. 检查待合并分支
    2. 检查未闭合任务
    3. 加载上下文
    4. 创建 start.md

    Returns:
        WorkflowResult 包含上下文信息
    """
    from dimcause.core.context import load_context
    from dimcause.utils.state import check_orphan_jobs, check_pending_merge

    context_info = {
        "pending_merge": None,
        "orphan_jobs": [],
        "recent_entries": [],
        "todos": [],
    }

    # 1. 检查待合并分支
    pending = check_pending_merge()
    if pending:
        context_info["pending_merge"] = pending

    # 2. 检查未闭合任务
    orphans = check_orphan_jobs(days=3)
    if orphans:
        context_info["orphan_jobs"] = [o["id"] for o in orphans]

    # 3. 加载上下文
    ctx = load_context()
    context_info["recent_entries"] = [
        {"date": e.date, "job": e.job, "status": e.status} for e in ctx.recent_entries[:5]
    ]
    context_info["todos"] = ctx.todos[:5]

    # 4. 创建日志
    result = create_daily_log("start")

    return WorkflowResult(success=result.success, message=result.message, data=context_info)


def end_daily_workflow(skip_git: bool = True) -> WorkflowResult:
    """
    执行完整的收工工作流

    包括:
    1. 创建 end.md
    2. 更新索引
    3. (可选) Git 提交

    Args:
        skip_git: 是否跳过 git 操作

    Returns:
        WorkflowResult
    """
    from dimcause.core.indexer import update_index

    # 1. 创建日志
    result = create_daily_log("end")
    if not result.success:
        return result

    # 2. 更新索引
    try:
        stats = update_index()
        index_info = {
            "processed": stats["processed"],
            "skipped": stats["skipped"],
        }
    except Exception as e:
        logger.warning(f"Index update failed: {e}")
        index_info = {"error": str(e)}

    return WorkflowResult(
        success=True,
        message="收工日志已创建",
        data={
            "log_path": result.data.get("path") if result.data else None,
            "index": index_info,
            "skip_git": skip_git,
        },
    )


def start_job_workflow(job_id: str) -> WorkflowResult:
    """
    开始一个新任务

    Args:
        job_id: 任务 ID

    Returns:
        WorkflowResult
    """
    from dimcause.utils.state import record_job_start

    result = create_job_log(job_id, "start")
    if result.success:
        record_job_start(result.data.get("job_id", job_id))

    return result


def end_job_workflow(job_id: Optional[str] = None) -> WorkflowResult:
    """
    结束一个任务

    Args:
        job_id: 任务 ID (可选，自动检测)

    Returns:
        WorkflowResult
    """
    from dimcause.utils.state import get_active_job, record_job_end

    if job_id is None:
        job_info = get_active_job()
        if not job_info:
            return WorkflowResult(
                success=False,
                message="未检测到进行中的任务",
                data={"hint": "请指定任务 ID: dimc job-end <job-id>"},
            )
        job_id = job_info[0]  # get_active_job returns (job_id, path) tuple

    result = create_job_log(job_id, "end")
    if result.success:
        record_job_end()

    return result


# === 查询工作流 ===


def get_context_summary() -> dict:
    """
    获取上下文摘要信息

    Returns:
        包含上下文信息的字典
    """
    from dimcause.core.context import load_context

    ctx = load_context()

    return {
        "pending_merge": ctx.pending_merge,
        "orphan_jobs": ctx.orphan_jobs,
        "recent_entries": [
            {
                "date": e.date,
                "job": e.job,
                "status": e.status,
            }
            for e in ctx.recent_entries[:10]
        ],
        "todos": ctx.todos[:10],
        "has_todos": len(ctx.todos) > 0,
    }


def run_index(rebuild: bool = False) -> dict:
    """
    运行索引更新

    Args:
        rebuild: 是否重建索引

    Returns:
        索引统计信息
    """
    from dimcause.core.indexer import rebuild_index, update_index

    if rebuild:
        stats = rebuild_index()
    else:
        stats = update_index()

    return {
        "processed": stats["processed"],
        "skipped": stats["skipped"],
        "errors": stats["errors"],
        "hot": stats["hot"],
        "archive": stats["archive"],
    }


def get_stats_summary() -> dict:
    """
    获取统计摘要

    Returns:
        统计信息字典
    """
    from dimcause.core.stats import get_stats, get_token_stats

    basic = get_stats()
    tokens = get_token_stats()

    return {
        "total_logs": basic.get("total_logs", 0),
        "recent_days": basic.get("days_active", 0),
        "recent_jobs": basic.get("jobs_completed", 0),
        "recent_activity": basic.get("recent_activity", []),
        "tokens_today": tokens.get("today", 0),
        "tokens_month": tokens.get("month", 0),
    }
