# Covers: EventIndex source directory invariants (scope guard)

"""
单元测试：EventIndex.sync() 必须扫描必需的数据源目录

这个测试确保 EventIndex.sync() 的运行时断言正常工作，
防止误传参数导致丢失数据源。
"""

from pathlib import Path

import pytest

from dimcause.core.event_index import EventIndex


def test_sync_requires_both_directories(tmp_path):
    """
    验证：EventIndex.sync() 必须同时接收 docs/logs/ 和 .dimcause/events/

    如果缺少任何一个，应该抛出 ValueError
    """
    index = EventIndex(str(tmp_path / "index.db"))

    # 准备测试目录
    docs_logs = tmp_path / "docs" / "logs"
    mal_events = tmp_path / ".dimcause" / "events"
    docs_logs.mkdir(parents=True, exist_ok=True)
    mal_events.mkdir(parents=True, exist_ok=True)

    kwargs = {"base_docs_dir": docs_logs, "base_data_dir": mal_events}

    # 测试1：只传 docs/logs/ -> 应该失败
    with pytest.raises(ValueError, match="缺少必需的数据源目录"):
        index.sync([str(docs_logs)], **kwargs)

    # 测试2：只传 .dimcause/events/ -> 应该失败
    with pytest.raises(ValueError, match="缺少必需的数据源目录"):
        index.sync([str(mal_events)], **kwargs)

    # 测试3：传空列表 -> 应该失败
    with pytest.raises(ValueError, match="缺少必需的数据源目录"):
        index.sync([], **kwargs)

    # 测试4：同时传两个 -> 应该成功
    result = index.sync([str(docs_logs), str(mal_events)], **kwargs)
    assert isinstance(result, dict)
    assert "added" in result
    assert "updated" in result


def test_sync_accepts_parent_directories(tmp_path):
    """
    验证：如果传入的是父目录，也应该被接受

    例如传 docs/ 或 ~/.dimcause/ 应该也能通过检查
    """
    index = EventIndex(str(tmp_path / "index.db"))

    docs_dir = tmp_path / "docs"
    mal_dir = tmp_path / ".dimcause"
    docs_logs = docs_dir / "logs"
    mal_events = mal_dir / "events"
    docs_logs.mkdir(parents=True, exist_ok=True)
    mal_events.mkdir(parents=True, exist_ok=True)

    kwargs = {"base_docs_dir": docs_logs, "base_data_dir": mal_events}

    # 这应该成功，因为扫描会深入子目录
    result = index.sync([str(docs_dir), str(mal_dir)], **kwargs)
    assert isinstance(result, dict)


def test_sync_with_nonexistent_directories(tmp_path):
    """
    验证：如果必需目录不存在，可以跳过检查

    这是为了兼容：用户可能还没有创建 .dimcause/events/ 目录

    但如果目录存在，就必须扫描它
    """
    index = EventIndex(str(tmp_path / "index.db"))

    docs_logs = tmp_path / "docs" / "logs"
    mal_events = tmp_path / ".dimcause" / "events"
    kwargs = {"base_docs_dir": docs_logs, "base_data_dir": mal_events}

    # 场景1：都不存在时传空列表 (内部检查发现目录不存在不会报错缺少)
    index.sync([], **kwargs)

    # 场景2：如果两个目录都存在，必须都传入
    docs_logs.mkdir(parents=True, exist_ok=True)
    mal_events.mkdir(parents=True, exist_ok=True)

    # 这是真实的强制约束：不能只扫描一个
    with pytest.raises(ValueError, match="缺少必需的数据源目录"):
        index.sync([str(docs_logs)], **kwargs)  # 缺少 .dimcause/events/

    with pytest.raises(ValueError, match="缺少必需的数据源目录"):
        index.sync([str(mal_events)], **kwargs)  # 缺少 docs/logs/


def test_sync_error_message_is_helpful(tmp_path):
    """
    验证：错误消息应该明确指出缺少哪个目录
    """
    index = EventIndex(str(tmp_path / "index.db"))

    docs_logs = tmp_path / "docs" / "logs"
    mal_events = tmp_path / ".dimcause" / "events"
    docs_logs.mkdir(parents=True, exist_ok=True)
    mal_events.mkdir(parents=True, exist_ok=True)
    
    kwargs = {"base_docs_dir": docs_logs, "base_data_dir": mal_events}

    try:
        index.sync([str(docs_logs)], **kwargs)  # 故意只传一个
        pytest.fail("应该抛出 ValueError")
    except ValueError as e:
        error_msg = str(e)
        # 错误消息应该提到缺失的目录
        assert "events" in error_msg or mal_events.name in error_msg
        # 错误消息应该说明原因
        assert "兼容" in error_msg or "必需" in error_msg
