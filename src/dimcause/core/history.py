"""
Core History Module

Responsible for retrieving and aggregating history context (Git + Dimcause Events).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dimcause.utils.git import run_git


@dataclass
class GitCommit:
    """Represents a single commit in file history (or a generic Event in H2 Timeline)"""

    hash: str
    date: str
    message: str
    author: str
    type: str = "git_commit"  # H2: Distinguish event types
    files_changed: int = 0
    context_events: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None  # H2: Store raw event metadata
    from_causal_chain: bool = False

    def __post_init__(self):
        if self.context_events is None:
            self.context_events = []
        if self.metadata is None:
            self.metadata = {}


def get_file_history(
    file_path: str,
    limit: int = 10,
    cwd: Optional[Path] = None,
    event_index: Any = None,  # Optional[EventIndex]
    type_filter: Optional[str] = None,  # H1: Added filter
    time_window_days: Optional[int] = None,  # 时间窗口过滤（天数）
    use_causal_chain: bool = True,  # 是否使用因果链追溯
) -> List[GitCommit]:
    """
    获取文件的历史记录，包含时间窗口过滤和因果链追溯。

    Args:
        file_path: 文件相对路径
        limit: 最大返回数量
        cwd: 工作目录
        event_index: EventIndex 实例
        type_filter: 事件类型过滤
        time_window_days: 时间窗口（天数），只返回该范围内的历史
        use_causal_chain: 是否使用 GraphStore 因果链追溯（默认开启）
    """
    commits = []

    # 1. Try EventIndex first (H2 Priority)
    if event_index:
        try:
            # Query mixed events (Git + Decision + ...) - 支持时间窗口过滤
            events = event_index.get_by_file(
                file_path, limit=limit, type_filter=type_filter, time_window_days=time_window_days
            )

            if events:
                # 如果启用因果链，尝试从 GraphStore 获取关联事件
                causal_events = []
                if use_causal_chain:
                    causal_events = _get_causal_related_events(
                        file_path, event_index, time_window_days
                    )

                # 合并事件并按时间排序
                event_map = {evt["id"]: evt for evt in events}

                # 添加因果链中的事件
                for causal_evt in causal_events:
                    if causal_evt["id"] not in event_map:
                        event_map[causal_evt["id"]] = causal_evt

                # 转换为 GitCommit 并按时间排序
                for evt in event_map.values():
                    # Map Event -> GitCommit (Adapter Pattern)
                    # Metadata is stored in json_cache, not as a column
                    meta: Dict[str, Any] = {}
                    if evt.get("json_cache"):
                        import json

                        try:
                            cached_obj = json.loads(evt["json_cache"])
                            meta = cached_obj.get("metadata", {})
                        except Exception:
                            pass
                    meta = dict(meta)

                    # Determine author
                    author = meta.get("author", "Dimcause Agent")
                    if evt["source"] == "manual":
                        author = "User"

                    from_causal_chain = bool(evt.get("_from_causal_chain"))
                    if from_causal_chain:
                        meta["_from_causal_chain"] = True

                    # Create object
                    commit = GitCommit(
                        hash=evt["id"],
                        date=evt["date"],  # YYYY-MM-DD
                        message=evt["summary"],
                        author=author,
                        type=evt["type"],
                        files_changed=meta.get("files_count", 0),
                        metadata=meta,  # Store full metadata
                        from_causal_chain=from_causal_chain,
                    )
                    commits.append(commit)

                # 按时间倒序排列
                commits.sort(key=lambda c: c.date, reverse=True)
                return commits[:limit]
        except Exception as e:
            # Fallback on error
            print(f"EventIndex history query failed: {e}")
            pass

    # 2. Fallback to Git CLI (Legacy)
    # Use --follow to track file renames
    code, out, err = run_git(
        "log",
        "--follow",
        f"--max-count={limit}",
        "--format=%H|%ad|%an|%s",
        "--date=short",
        "--",
        file_path,
        cwd=cwd,
    )

    if code != 0 or not out:
        return []

    # Need datetime for calculation
    from datetime import datetime, timedelta

    for line in out.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", maxsplit=3)
        if len(parts) != 4:
            continue

        hash_val, date_str, author, message = parts
        commit = GitCommit(hash=hash_val, date=date_str, message=message, author=author)

        # 时间窗口过滤（Git CLI 方式）
        if time_window_days is not None:
            try:
                commit_date = datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d")
                now = datetime.now()
                days_diff = (now - commit_date).days
                if days_diff > time_window_days:
                    continue  # 跳过时间窗口外的事件
            except Exception:
                pass

        # Aggregate Context if EventIndex provided (Logic for Legacy Path)
        if event_index:
            try:
                # Commit date is YYYY-MM-DD
                c_date = datetime.strptime(date_str.split(" ")[0], "%Y-%m-%d")
                start_date = c_date - timedelta(days=1)

                date_to = c_date.strftime("%Y-%m-%d")
                date_from = start_date.strftime("%Y-%m-%d")

                events = event_index.query(
                    type="decision", date_from=date_from, date_to=date_to, limit=5
                )
                commit.context_events = events
            except Exception:
                pass

        commits.append(commit)

    return commits


def _get_causal_related_events(
    file_path: str, event_index: Any, time_window_days: Optional[int] = None, max_depth: int = 2
) -> List[Dict[str, Any]]:
    """
    从 GraphStore 获取与文件相关的因果链事件。

    Args:
        file_path: 文件路径
        event_index: EventIndex 实例
        time_window_days: 时间窗口过滤
        max_depth: 因果链追溯深度

    Returns:
        因果链相关的 Events 列表
    """
    from dimcause.storage.graph_store import create_graph_store

    # 优先复用上层注入实例；不存在时才同库降级创建
    graph_store = getattr(event_index, "_graph_store", None) or getattr(
        event_index, "graph_store", None
    )
    if graph_store is None:
        db_path = getattr(event_index, "db_path", None)
        if db_path is None:
            return []
        try:
            graph_store = create_graph_store(path=str(db_path))
        except Exception:
            return []

    # 先通过关系型访问层提取文件相关种子事件，禁止基于 DiGraph 的 file_history 路径
    seed_ids: List[str] = []
    seen_seeds = set()
    file_name = file_path.split("/")[-1]
    search_terms = [file_path]
    if file_name and file_name != file_path:
        search_terms.append(file_name)

    for term in search_terms:
        try:
            seed_events = event_index.get_by_file(
                term, limit=50, type_filter=None, time_window_days=time_window_days
            )
        except Exception:
            seed_events = []
        seed_events = seed_events or []

        for evt in seed_events:
            evt_id = evt.get("id")
            if evt_id and evt_id not in seen_seeds:
                seen_seeds.add(evt_id)
                seed_ids.append(evt_id)

    if not seed_ids:
        return []

    # 对每个种子事件执行因果链回溯（BFS 结果按返回顺序去重拼接）
    causal_ids: List[str] = []
    seen_causal = set()
    for seed_id in seed_ids:
        try:
            chain_ids = graph_store.get_causal_chain(seed_id, depth=max_depth)
        except Exception:
            continue

        for cid in chain_ids:
            if cid and cid not in seen_causal:
                seen_causal.add(cid)
                causal_ids.append(cid)

    if not causal_ids:
        return []

    # 对因果链结果必须强走主键 IN 精确匹配，禁止 LIKE 扩散
    conn = event_index._get_conn()
    try:
        placeholders = ", ".join(["?"] * len(causal_ids))
        query_sql = f"SELECT * FROM events WHERE id IN ({placeholders})"
        params: List[Any] = list(causal_ids)

        if time_window_days is not None:
            query_sql += " AND timestamp >= datetime('now', ?)"
            params.append(f"-{time_window_days} days")

        cursor = conn.execute(query_sql, params)
        fetched = [dict(row) for row in cursor]
    finally:
        conn.close()

    event_map = {evt["id"]: evt for evt in fetched if evt.get("id")}
    causal_events: List[Dict[str, Any]] = []
    for cid in causal_ids:
        evt = event_map.get(cid)
        if not evt:
            continue
        evt["_from_causal_chain"] = True
        causal_events.append(evt)

    return causal_events


def format_history_timeline(commits: List[GitCommit]) -> str:
    """
    Format commit history as a readable timeline.
    """
    if not commits:
        return "No commit history found."

    lines = []
    for i, commit in enumerate(commits, 1):
        lines.append(f"{i}. [{commit.date}] {commit.message}")
        lines.append(f"   Commit: {commit.hash[:8]} by {commit.author}")
        lines.append("")

    return "\n".join(lines)


def get_file_diff(
    file_path: str, commit1: str, commit2: str = "HEAD", cwd: Optional[Path] = None
) -> Optional[str]:
    """
    Get diff between two commits for a file.
    """
    code, out, err = run_git("diff", commit1, commit2, "--", file_path, cwd=cwd)

    if code != 0:
        return None

    return out


def get_file_at_commit(
    file_path: str, commit_hash: str, cwd: Optional[Path] = None
) -> Optional[str]:
    """
    Get file content at a specific commit.
    """
    code, out, err = run_git("show", f"{commit_hash}:{file_path}", cwd=cwd)

    if code != 0:
        return None

    return out
