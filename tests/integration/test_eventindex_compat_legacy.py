# Covers: EventIndex vs legacy indexer behavior (scope guard)

"""
对比测试：确保 EventIndex 在受控工作区里不比旧 indexer 少扫描事件。

这里不再依赖开发机上现成的 ~/.dimcause 或历史索引，
而是在临时工作区里构造 docs/logs 与 ~/.dimcause/events 两类源材料，
验证新旧两套扫描逻辑在相同输入下保持兼容。
"""

from pathlib import Path

import pytest


def _write_event_file(path: Path, *, event_id: str, event_type: str, summary: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {event_id}
type: {event_type}
timestamp: 2026-03-18T10:00:00
summary: {summary}
tags: []
---

# {summary}

受保护测试数据。
""",
        encoding="utf-8",
    )


@pytest.fixture
def isolated_event_sources(tmp_path, monkeypatch):
    root_dir = tmp_path / "workspace"
    logs_dir = root_dir / "docs" / "logs"
    home_dir = tmp_path / "home"
    events_dir = home_dir / ".dimcause" / "events"
    db_path = home_dir / ".dimcause" / "index.db"

    _write_event_file(
        logs_dir / "2026" / "03-18" / "end.md",
        event_id="daily_end_001",
        event_type="unknown",
        summary="Daily End",
    )
    _write_event_file(
        logs_dir / "2026" / "03-18" / "jobs" / "job-001" / "end.md",
        event_id="job_end_001",
        event_type="unknown",
        summary="Job End",
    )
    _write_event_file(
        events_dir / "2026" / "03" / "18" / "task_001.md",
        event_id="task_001",
        event_type="task",
        summary="Task Event",
    )

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("DIMCAUSE_ROOT", str(root_dir))
    monkeypatch.chdir(root_dir)

    from dimcause.utils.config import reset_config

    reset_config()
    monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
    yield {
        "root_dir": root_dir,
        "logs_dir": logs_dir,
        "events_dir": events_dir,
        "db_path": db_path,
    }
    reset_config()


def _collect_legacy_events():
    """使用旧 indexer 收集当前受控工作区里的所有事件路径。"""
    from dimcause.core.indexer import scan_log_files, scan_task_files

    log_files = scan_log_files()
    task_files = scan_task_files()
    all_files = list(log_files) + list(task_files)
    return sorted({str(f.resolve()) for f in all_files})


def _collect_eventindex_events(db_path: Path, logs_dir: Path, events_dir: Path):
    """使用新的 EventIndex 在受控工作区里完成一次完整同步。"""
    from dimcause.core.event_index import EventIndex

    index = EventIndex(db_path=str(db_path))
    index.sync(
        [str(events_dir), str(logs_dir)],
        base_docs_dir=str(logs_dir),
        base_data_dir=str(events_dir),
    )
    results = index.query(limit=100000)  # 大上限确保获取所有
    return sorted({row.get("markdown_path", "") for row in results if row.get("markdown_path")})


@pytest.mark.protected
@pytest.mark.integration
def test_eventindex_does_not_drop_events(isolated_event_sources):
    """
    核心约束：EventIndex 扫描的事件不得少于旧 indexer

    如果这个测试失败，说明新实现丢失了部分数据源。
    """
    legacy_paths = _collect_legacy_events()
    eventindex_paths = _collect_eventindex_events(
        isolated_event_sources["db_path"],
        isolated_event_sources["logs_dir"],
        isolated_event_sources["events_dir"],
    )

    legacy_set = set(legacy_paths)
    eventindex_set = set(eventindex_paths)
    missing = legacy_set - eventindex_set

    if missing:
        print(f"\n旧 indexer 扫描到 {len(legacy_set)} 个文件")
        print(f"EventIndex 索引了 {len(eventindex_set)} 个文件")
        print(f"缺失 {len(missing)} 个文件:")
        for p in sorted(missing)[:10]:
            print(f"  - {p}")

    assert len(missing) == 0, (
        f"EventIndex 缺少 {len(missing)} 个文件。"
        f"可能原因：1) 索引未更新（运行 `dimc index --rebuild`）；"
        f"2) EventIndex.sync() 扫描目录不完整。"
    )


@pytest.mark.protected
@pytest.mark.integration
def test_eventindex_scans_both_directories(isolated_event_sources):
    """
    验证：EventIndex 必须同时扫描 docs/logs/ 和 .dimcause/events/
    """
    from dimcause.core.event_index import EventIndex

    index = EventIndex(db_path=str(isolated_event_sources["db_path"]))
    index.sync(
        [str(isolated_event_sources["events_dir"]), str(isolated_event_sources["logs_dir"])],
        base_docs_dir=str(isolated_event_sources["logs_dir"]),
        base_data_dir=str(isolated_event_sources["events_dir"]),
    )
    results = index.query(limit=100000)

    all_paths = [row.get("markdown_path", "") for row in results]

    has_logs = any("docs/logs" in p or "docs\\logs" in p for p in all_paths)
    has_events = any(".dimcause/events" in p or ".dimcause\\events" in p for p in all_paths)

    assert has_logs, "EventIndex 没有索引 docs/logs/ 中的文件！"
    assert has_events, "EventIndex 没有索引 .dimcause/events/ 中的文件！"


@pytest.mark.protected
@pytest.mark.integration
def test_cli_index_scans_correct_directories(isolated_event_sources):
    """
    验证：CLI 的 dimc index 命令扫描正确的目录

    这是对 _sync_event_index 和 _rebuild_event_index 函数的集成测试
    """
    from dimcause.cli import _sync_event_index
    from dimcause.core.event_index import EventIndex

    index = EventIndex(db_path=str(isolated_event_sources["db_path"]))
    stats = _sync_event_index(index)
    total_scanned = stats.get("added", 0) + stats.get("updated", 0) + stats.get("skipped", 0)
    results = index.query(limit=100000)
    all_paths = [row.get("markdown_path", "") for row in results]

    has_logs = any("docs/logs" in p or "docs\\logs" in p for p in all_paths)
    has_events = any(".dimcause/events" in p or ".dimcause\\events" in p for p in all_paths)

    assert total_scanned > 0, "CLI index 命令没有扫描到任何文件"
    assert has_logs, "CLI index 没有索引 docs/logs/ 中的文件！"
    assert has_events, "CLI index 没有索引 .dimcause/events/ 中的文件！"
