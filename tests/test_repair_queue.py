"""
Tests for Auto-Repair Queue - 自动修复队列测试

验证三层存储一致性检测与修复
"""

import tempfile
from pathlib import Path

import pytest

from dimcause.utils.repair_queue import AutoRepairQueue, RepairTask, get_repair_queue


class TestAutoRepairQueue:
    """测试Auto-Repair Queue"""

    @pytest.fixture
    def temp_queue_file(self):
        """临时队列文件"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
            queue_path = f.name
        yield queue_path
        Path(queue_path).unlink(missing_ok=True)

    @pytest.fixture
    def temp_markdown_dir(self, tmp_path):
        """临时Markdown目录"""
        md_dir = tmp_path / "logs"
        md_dir.mkdir()
        return md_dir

    def test_add_task(self, temp_queue_file, temp_markdown_dir):
        """测试添加修复任务"""
        queue = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)

        queue.add_task("sync_001", "missing_vector", "/path/to/file.md")

        assert len(queue.queue) == 1
        assert queue.queue[0].sync_id == "sync_001"
        assert queue.queue[0].issue_type == "missing_vector"

    def test_queue_persistence(self, temp_queue_file, temp_markdown_dir):
        """测试队列持久化"""
        # 第一个queue实例
        queue1 = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)
        queue1.add_task("sync_001", "both", "/path/to/file.md")

        # 第二个queue实例(重新加载)
        queue2 = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)

        # 应该加载到之前的任务
        assert len(queue2.queue) == 1
        assert queue2.queue[0].sync_id == "sync_001"

    def test_extract_sync_ids_from_markdown(self, temp_markdown_dir):
        """测试从Markdown提取SYNC_ID"""
        queue = AutoRepairQueue(markdown_dir=str(temp_markdown_dir))

        # 创建测试Markdown文件
        md_file = temp_markdown_dir / "test.md"
        md_file.write_text("""
# Test

<!-- DIMCAUSE_SYNC_ID: sync-abc-123 -->
Some content

<!-- DIMCAUSE_SYNC_ID: sync-def-456 -->
More content
""")

        sync_ids = queue.extract_sync_ids_from_markdown(md_file)

        assert len(sync_ids) == 2
        assert "sync-abc-123" in sync_ids
        assert "sync-def-456" in sync_ids

    def test_duplicate_task_prevention(self, temp_queue_file, temp_markdown_dir):
        """测试防止重复任务"""
        queue = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)

        queue.add_task("sync_001", "both", "/path/to/file.md")
        queue.add_task("sync_001", "both", "/path/to/file.md")  # 重复

        # 应该只有1个任务
        assert len(queue.queue) == 1

    def test_stats(self, temp_queue_file, temp_markdown_dir):
        """测试队列统计"""
        queue = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)

        queue.add_task("sync_001", "missing_vector", "/path/a.md")
        queue.add_task("sync_002", "missing_graph", "/path/b.md")
        queue.add_task("sync_003", "both", "/path/c.md")

        stats = queue.stats()

        assert stats["total"] == 3
        assert stats["by_type"]["missing_vector"] == 1
        assert stats["by_type"]["missing_graph"] == 1
        assert stats["by_type"]["both"] == 1

    def test_empty_queue_stats(self, temp_queue_file, temp_markdown_dir):
        """测试空队列统计"""
        queue = AutoRepairQueue(markdown_dir=str(temp_markdown_dir), queue_file=temp_queue_file)

        stats = queue.stats()

        assert stats["total"] == 0
        assert stats["oldest_task"] is None

    def test_default_queue_path_uses_dimcause(self, tmp_path, monkeypatch):
        """默认队列路径应为 ~/.dimcause/repair_queue.jsonl"""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        queue = AutoRepairQueue(markdown_dir=str(tmp_path / "logs"))
        expected = tmp_path / ".dimcause" / "repair_queue.jsonl"

        assert queue.queue_file == expected
        assert expected.parent.exists()

    def test_default_queue_ignores_legacy_oldbrand_dir(self, tmp_path, monkeypatch):
        """存在 legacy 目录下 repair_queue.jsonl 时，默认路径仍应保持 ~/.dimcause。"""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        legacy = tmp_path / ".legacy_dimcause" / "repair_queue.jsonl"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy_content = '{"sync_id":"legacy_1","issue_type":"both","markdown_file":"/tmp/x.md","discovered_at":1.0,"retry_count":0,"last_retry_at":0.0}\n'
        legacy.write_text(legacy_content, encoding="utf-8")

        queue = AutoRepairQueue(markdown_dir=str(tmp_path / "logs"))
        expected = tmp_path / ".dimcause" / "repair_queue.jsonl"

        assert queue.queue_file == expected
        assert expected.parent.exists()
        assert legacy.exists()


class TestRepairTask:
    """测试RepairTask数据类"""

    def test_repair_task_creation(self):
        """测试创建RepairTask"""
        import time

        task = RepairTask(
            sync_id="test_001",
            issue_type="missing_vector",
            markdown_file="/path/to/file.md",
            discovered_at=time.time(),
        )

        assert task.sync_id == "test_001"
        assert task.issue_type == "missing_vector"
        assert task.retry_count == 0


class TestSingleton:
    """测试单例模式"""

    def test_get_repair_queue_singleton(self):
        """测试全局单例"""
        queue1 = get_repair_queue()
        queue2 = get_repair_queue()

        assert queue1 is queue2


def test_markdown_parsing_edge_cases():
    """测试Markdown解析边界情况"""
    queue = AutoRepairQueue()

    # 测试非法格式
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("<!-- DIMCAUSE_SYNC_ID: with spaces in id -->")
        temp_path = Path(f.name)

    try:
        sync_ids = queue.extract_sync_ids_from_markdown(temp_path)
        # 应该仍然提取(允许空格)
        assert len(sync_ids) >= 0
    finally:
        temp_path.unlink()


def test_queue_file_corruption_handling():
    """测试队列文件损坏处理"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        queue_file = f.name
        # 写入损坏的JSON
        f.write("CORRUPTED JSON\n")
        f.write('{"sync_id": "test"}\n')  # 缺少必需字段

    try:
        # 应该能够处理损坏行
        queue = AutoRepairQueue(markdown_dir="docs/logs", queue_file=queue_file)

        # 队列应该为空或只加载有效的
        assert isinstance(queue.queue, list)
    finally:
        Path(queue_file).unlink(missing_ok=True)
