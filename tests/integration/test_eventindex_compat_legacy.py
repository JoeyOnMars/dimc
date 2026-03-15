# Covers: EventIndex vs legacy indexer behavior (scope guard)

"""
对比测试：确保 EventIndex 不会比旧 indexer 少扫描事件

这个测试强制要求新的 EventIndex 实现必须扫描至少和旧 indexer 一样多的事件。
如果新实现只扫描 .dimcause/events/ 而忽略 docs/logs/，这个测试会失败。
"""

from pathlib import Path

import pytest


def _collect_legacy_events():
    """
    使用旧 indexer 收集所有事件路径
    """
    from dimcause.core.indexer import scan_log_files, scan_task_files

    # 旧 indexer 扫描两个来源
    log_files = scan_log_files()
    task_files = scan_task_files()

    all_files = list(log_files) + list(task_files)

    # 返回路径集合（去重）
    return sorted({str(f.resolve()) for f in all_files})


def _collect_eventindex_events():
    """
    使用新的 EventIndex 收集所有事件路径
    """
    from dimcause.core.event_index import EventIndex

    # 创建 EventIndex 实例
    index = EventIndex()

    # 准备扫描目录（与 CLI 中的逻辑一致）
    scan_paths = []

    # 1. ~/.dimcause/events/
    events_dir = Path.home() / ".dimcause" / "events"
    if events_dir.exists():
        scan_paths.append(str(events_dir))

    # 2. docs/logs/
    logs_dir = Path.cwd() / "docs" / "logs"
    if logs_dir.exists():
        scan_paths.append(str(logs_dir))

    # 扫描并收集结果
    if not scan_paths:
        return []

    # 查询所有已索引的事件
    results = index.query(limit=100000)  # 大上限确保获取所有

    # 返回 markdown_path 集合
    return sorted({row.get("markdown_path", "") for row in results if row.get("markdown_path")})


@pytest.mark.skip(reason="触碰实际用户量产数据引起缓慢并发超时的自动化阻断")
@pytest.mark.integration
def test_eventindex_does_not_drop_events():
    """
    核心约束：EventIndex 扫描的事件不得少于旧 indexer

    如果这个测试失败，说明新实现丢失了部分数据源。
    """

    # 1. 收集旧 indexer 会扫描的文件
    legacy_paths = _collect_legacy_events()

    # 2. 收集 EventIndex 已索引的文件
    eventindex_paths = _collect_eventindex_events()

    # 3. 检查：EventIndex 索引的文件应该至少包含旧 indexer 扫描的文件
    # 注意：由于索引是增量的，EventIndex 可能包含历史文件，所以用 >=
    legacy_set = set(legacy_paths)
    eventindex_set = set(eventindex_paths)

    # 找出旧 indexer 扫描到但 EventIndex 没有的文件
    missing = legacy_set - eventindex_set

    # 如果有遗漏，说明 EventIndex 扫描范围不足
    if missing:
        # 输出详细信息帮助调试
        print(f"\n旧 indexer 扫描到 {len(legacy_set)} 个文件")
        print(f"EventIndex 索引了 {len(eventindex_set)} 个文件")
        print(f"缺失 {len(missing)} 个文件:")
        for p in sorted(missing)[:10]:  # 只显示前10个
            print(f"  - {p}")

    assert len(missing) == 0, (
        f"EventIndex 缺少 {len(missing)} 个文件。"
        f"可能原因：1) 索引未更新（运行 `dimc index --rebuild`）；"
        f"2) EventIndex.sync() 扫描目录不完整。"
    )


@pytest.mark.skip(reason="触碰实际用户量产数据引起缓慢并发超时的自动化阻断")
@pytest.mark.integration
def test_eventindex_scans_both_directories():
    """
    验证：EventIndex 必须同时扫描 docs/logs/ 和 .dimcause/events/
    """
    from dimcause.core.event_index import EventIndex

    index = EventIndex()
    results = index.query(limit=100000)

    if not results:
        pytest.skip("索引为空，先运行 dimc index --rebuild")

    # 检查索引中的文件路径
    all_paths = [row.get("markdown_path", "") for row in results]

    # 必须有来自 docs/logs/ 的文件
    has_logs = any("docs/logs" in p or "docs\\logs" in p for p in all_paths)

    # 必须有来自 .dimcause/events/ 的文件（如果该目录存在且有文件）
    events_dir = Path.home() / ".dimcause" / "events"
    if events_dir.exists() and any(events_dir.glob("**/*.md")):
        has_events = any(".dimcause/events" in p or ".dimcause\\events" in p for p in all_paths)
    else:
        has_events = True  # 如果目录不存在或为空，跳过检查

    assert has_logs, "EventIndex 没有索引 docs/logs/ 中的文件！"
    assert has_events, "EventIndex 没有索引 .dimcause/events/ 中的文件！"


@pytest.mark.skip(reason="触碰实际用户量产数据引起缓慢并发超时的自动化阻断")
@pytest.mark.integration
def test_cli_index_scans_correct_directories():
    """
    验证：CLI 的 dimc index 命令扫描正确的目录

    这是对 _sync_event_index 和 _rebuild_event_index 函数的集成测试
    """

    # 检查 CLI 中定义的扫描路径
    # 这里我们通过导入函数来验证逻辑
    from dimcause.cli import _sync_event_index
    from dimcause.core.event_index import EventIndex

    # 创建临时索引
    index = EventIndex()

    # 调用同步函数（实际会扫描目录）
    stats = _sync_event_index(index)

    # 验证：stats 应该反映扫描了多个目录
    # 至少应该有一些文件被扫描
    total_scanned = stats.get("scanned", 0) + stats.get("updated", 0) + stats.get("skipped", 0)

    assert total_scanned > 0, "CLI index 命令没有扫描到任何文件"
