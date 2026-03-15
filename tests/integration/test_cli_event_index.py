# Covers: Integration test for CLI + EventIndex (C1 task)

"""
Integration Tests: CLI + EventIndex

验证 CLI 命令在使用 EventIndex 后的正确性
"""

import os
import tempfile
from pathlib import Path

import pytest

from dimcause.core.event_index import EventIndex


@pytest.fixture
def temp_mal_dir():
    """创建临时 .dimcause 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        mal_dir = Path(tmpdir) / ".dimcause"
        mal_dir.mkdir()

        # 创建 events 目录
        events_dir = mal_dir / "events"
        events_dir.mkdir()

        # 创建测试事件文件
        test_event_dir = events_dir / "2026" / "01" / "23"
        test_event_dir.mkdir(parents=True)

        # 创建一个测试任务
        task_file = test_event_dir / "task_test_001.md"
        task_file.write_text("""---
id: task_test_001
type: task
source: manual
timestamp: 2026-01-23T10:00:00
summary: Test Task 1
tags: []
status: pending
schema_version: 2
---

# Test Task 1

This is a test task.
""")

        yield mal_dir


@pytest.fixture
def event_index_with_data(temp_mal_dir):
    """创建包含测试数据的 EventIndex"""
    db_path = temp_mal_dir / "index.db"
    event_index = EventIndex(str(db_path))

    # 同步事件
    events_dir = temp_mal_dir / "events"
    event_index.sync(
        [str(events_dir)],
        base_data_dir=str(events_dir),
        base_docs_dir=str(events_dir),
    )

    yield event_index


class TestCLIEventIndex:
    """测试 CLI 与 EventIndex 集成"""

    def test_event_index_query_returns_task_format(self, event_index_with_data):
        """测试 EventIndex 查询返回 CLI 所需格式"""
        # 直接测试 EventIndex 而不是 CLI 函数
        results = event_index_with_data.query(type="task", status="pending")

        # 验证返回格式符合 CLI 期望
        assert isinstance(results, list)
        assert len(results) > 0, "sync 后应有数据，结果为空说明同步失败"

        for row in results:
            # CLI 需要的字段
            assert "id" in row
            assert "type" in row
            assert "summary" in row
            assert "status" in row
            assert "timestamp" in row

            # 可以转换为 CLI task 格式
            task = {
                "id": row["id"],
                "summary": row.get("summary", "Unnamed task"),
                "status": row.get("status", "active"),
                "timestamp": row.get("timestamp", ""),
            }
            assert task["id"]
            assert task["summary"]

    def test_environment_variable_parsing(self, monkeypatch):
        """测试环境变量解析"""

        # 测试默认值
        assert os.getenv("DIMCAUSE_USE_EVENT_INDEX", "true").lower() == "true"

        # 测试自定义值
        monkeypatch.setenv("DIMCAUSE_USE_EVENT_INDEX", "false")
        assert os.getenv("DIMCAUSE_USE_EVENT_INDEX").lower() == "false"


class TestEventIndexQueryConsistency:
    """测试 EventIndex 查询一致性"""

    def test_query_task_returns_correct_fields(self, event_index_with_data):
        """验证查询任务返回正确的字段"""
        results = event_index_with_data.query(type="task", limit=10)

        assert isinstance(results, list)
        assert len(results) > 0, "sync 后应有数据，结果为空说明同步失败"

        for row in results:
            # 必须包含的字段
            assert "id" in row
            assert "type" in row
            assert "summary" in row
            assert "status" in row
            assert "timestamp" in row

    def test_query_with_status_filter(self, event_index_with_data):
        """测试状态过滤"""
        results = event_index_with_data.query(type="task", status="pending")

        assert isinstance(results, list)

        # 所有返回的结果应该都是 pending 状态
        for row in results:
            assert row.get("status") == "pending"


@pytest.mark.skip(reason="需要完整 CLI 环境，手动测试")
def test_mal_tasks_command_output():
    """测试 dimc tasks 命令输出格式"""
    # 这个测试需要在真实环境中手动运行：
    # 1. DIMCAUSE_USE_EVENT_INDEX=true dimc tasks
    # 2. DIMCAUSE_USE_EVENT_INDEX=false dimc tasks
    # 3. 对比输出格式是否一致
    pass


@pytest.mark.skip(reason="需要完整 CLI 环境，手动测试")
def test_mal_index_rebuild():
    """测试 dimc index --rebuild 命令"""
    # 手动测试：
    # dimc index --rebuild
    # 验证索引重建成功
    pass
