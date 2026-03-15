"""
测试 Event 模型的序列化与反序列化
"""

from datetime import datetime

import pytest

from dimcause.core.models import CodeEntity, CodeEntityType, Entity, Event, EventType, SourceType


class TestEventMarkdownSerialization:
    """测试 Event 的 Markdown 序列化/反序列化"""

    def test_basic_roundtrip(self):
        """测试基础的往返转换"""
        event = Event(
            id="test_123",
            type=EventType.DECISION,
            timestamp=datetime(2026, 1, 21, 10, 30, 0),
            summary="Test Decision",
            content="This is a test decision",
            tags=["test", "decision"],
        )

        # Serialize
        markdown = event.to_markdown()
        assert "test_123" in markdown
        assert "Test Decision" in markdown

        # Deserialize
        restored = Event.from_markdown(markdown)
        assert restored.id == "test_123"
        assert restored.type == EventType.DECISION
        assert restored.summary == "Test Decision"
        assert "test" in restored.tags

    def test_metadata_preservation(self):
        """测试 metadata 字段的持久化"""
        event = Event(
            id="task_456",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Task with status",
            content="Task content",
            metadata={"status": "pending", "priority": "high", "count": 42},
        )

        # Serialize
        markdown = event.to_markdown()
        assert "status: pending" in markdown
        assert "priority: high" in markdown
        assert "count: 42" in markdown

        # Deserialize
        restored = Event.from_markdown(markdown)
        assert restored.metadata.get("status") == "pending"
        assert restored.metadata.get("priority") == "high"
        # Note: numeric values might be string after YAML parsing
        assert str(restored.metadata.get("count")) == "42" or restored.metadata.get("count") == 42

    def test_fallback_parser(self):
        """测试降级解析器（无 frontmatter 库时）"""
        # Manually craft a markdown string
        markdown_content = """---
id: fallback_test
type: code_change
timestamp: 2026-01-21T12:00:00
tags: [git, test]
status: done
---

# Fallback Test

This is testing the fallback parser.
"""
        # Temporarily unload frontmatter to test fallback
        import sys

        frontmatter_backup = sys.modules.get("frontmatter")
        if "frontmatter" in sys.modules:
            del sys.modules["frontmatter"]

        try:
            restored = Event.from_markdown(markdown_content)
            assert restored.id == "fallback_test"
            assert restored.type == EventType.CODE_CHANGE
            assert restored.summary == "Fallback Test"
            # Metadata from fallback parser
            assert restored.metadata.get("status") == "done"
        finally:
            # Restore module
            if frontmatter_backup:
                sys.modules["frontmatter"] = frontmatter_backup

    def test_missing_fields_handled(self):
        """测试缺失字段的默认处理"""
        markdown_content = """---
type: unknown
---

# No ID Event
"""
        restored = Event.from_markdown(markdown_content, file_path="/tmp/test.md")
        # Should use file stem as ID fallback
        assert restored.id == "test"
        assert restored.type == EventType.UNKNOWN

    def test_complex_metadata_serialization(self):
        """测试复杂类型的 metadata 序列化"""
        # 由于我们添加了 validator，复杂类型应该被拒绝
        with pytest.raises(ValueError, match="non-JSON-serializable"):
            Event(
                id="complex_meta",
                type=EventType.RESEARCH,
                timestamp=datetime.now(),
                summary="Complex Metadata Test",
                content="Content",
                metadata={
                    "simple_string": "value",
                    "simple_int": 123,
                    "complex_dict": {"nested": "data"},  # 这个应该没问题
                    "bad_object": datetime.now(),  # 这个会失败
                },
            )

    def test_from_markdown_malformed_yaml(self):
        """测试畸形 YAML 的处理"""
        malformed = """---
id: test
type: decision
timestamp: 2026-01-21T12:00:00
tags: [unclosed
---

# Test
"""
        # 应该能容错处理，使用 fallback parser
        restored = Event.from_markdown(malformed)
        # Fallback parser 可能无法完美解析，但不应该崩溃
        assert restored.id  # 至少有个 ID

    def test_from_markdown_empty_file(self):
        """测试空文件处理"""
        empty = ""
        restored = Event.from_markdown(empty, file_path="/tmp/empty.md")
        # 应该返回一个默认 Event
        assert restored.id == "empty"
        assert restored.type == EventType.UNKNOWN

    def test_from_markdown_large_content(self):
        """测试大文件处理（性能测试）"""
        large_content = "# Large File\n\n" + ("x" * 100000)
        markdown = f"""---
id: large_test
type: research
timestamp: 2026-01-21T12:00:00
---

{large_content}
"""
        import time

        start = time.time()
        restored = Event.from_markdown(markdown)
        duration = time.time() - start

        assert restored.id == "large_test"
        # 解析应该在 1 秒内完成
        assert duration < 1.0, f"Parsing took {duration}s, too slow!"

    def test_simple_types_only(self):
        """测试 metadata 只允许简单类型"""
        # 这个应该成功
        event = Event(
            id="simple_meta",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Simple Metadata",
            content="Content",
            metadata={
                "string": "value",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "list": [1, 2, 3],
                "dict": {"nested": "ok"},
            },
        )
        assert event.metadata["string"] == "value"

    def test_roundtrip_preserves_structured_fields(self):
        event = Event(
            id="roundtrip_full",
            type=EventType.INCIDENT,
            timestamp=datetime(2026, 3, 7, 12, 0, 0),
            summary="Full Fidelity Event",
            content="Detailed content body",
            raw_data_id="raw-001",
            entities=[Entity(name="AuthService", type="class", context="service")],
            code_entities=[
                CodeEntity(
                    name="AuthService.login",
                    type=CodeEntityType.METHOD,
                    file="src/auth.py",
                    line_start=10,
                    line_end=18,
                    signature="def login(self, user)",
                    docstring="Authenticate user",
                    language="python",
                )
            ],
            tags=["auth", "incident"],
            related_files=["src/auth.py", "docs/runbook.md"],
            related_event_ids=["evt_prev_001"],
            source=SourceType.CONTINUE_DEV,
            confidence=0.82,
            metadata={"status": "active", "nested": {"severity": "high"}},
        )

        markdown = event.to_markdown()
        restored = Event.from_markdown(markdown)

        assert restored.id == event.id
        assert restored.type == EventType.INCIDENT
        assert restored.summary == event.summary
        assert restored.content == event.content
        assert restored.raw_data_id == "raw-001"
        assert restored.source == SourceType.CONTINUE_DEV
        assert restored.confidence == pytest.approx(0.82)
        assert restored.related_files == ["src/auth.py", "docs/runbook.md"]
        assert restored.related_event_ids == ["evt_prev_001"]
        assert restored.entities[0].name == "AuthService"
        assert restored.code_entities[0].name == "AuthService.login"
        assert restored.metadata["status"] == "active"
        assert restored.metadata["nested"]["severity"] == "high"
