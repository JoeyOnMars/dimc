"""
Tests for core migration logic (v1 -> v2).
"""

import pytest

from dimcause.core.migrate import (
    detect_schema_version,
    generate_migration_id,
    merge_description_to_content,
    migrate_event,
)


class TestMigrateCore:
    def test_generate_migration_id(self):
        """测试 ID 生成格式和唯一性"""
        date_str = "2026-01-23"
        id1 = generate_migration_id(date_str)
        id2 = generate_migration_id(date_str)

        # Check format
        assert id1.startswith("evt_migrated_20260123_")
        assert len(id1) == len("evt_migrated_20260123_") + 8

        # Check uniqueness
        assert id1 != id2

    def test_detect_schema_version(self):
        """测试版本检测逻辑"""
        # v1: has date
        assert detect_schema_version({"date": "2026-01-01"}) == 1

        # v2: has schema_version
        assert detect_schema_version({"schema_version": 2}) == 2

        # v2 implicit: has id and timestamp
        assert detect_schema_version({"id": "1", "timestamp": "..."}) == 2

        # unknown
        assert detect_schema_version({"foo": "bar"}) == 0

        # Priority: schema_version > implicit v2 > v1
        assert detect_schema_version({"schema_version": 2, "date": "..."}) == 2

    def test_merge_description_to_content_with_header(self):
        """测试合并 description 到带有标题的内容"""
        content = "# H1 Title\n\nSome text."
        desc = "This is a description."

        merged = merge_description_to_content(desc, content)

        expected = "# H1 Title\n\n> **[迁移自 v1]** This is a description.\n\nSome text."
        assert merged == expected

    def test_merge_description_to_content_without_header(self):
        """测试合并 description 到无标题内容"""
        content = "Just text."
        desc = "Desc."

        merged = merge_description_to_content(desc, content)

        expected = "> **[迁移自 v1]** Desc.\n\nJust text."
        assert merged == expected

    def test_merge_description_empty(self):
        """测试空 description 不合并"""
        content = "# Title"
        assert merge_description_to_content(None, content) == content
        assert merge_description_to_content("", content) == content
        assert merge_description_to_content("   ", content) == content

    def test_migrate_event_v1_to_v2(self):
        """测试完整的 v1 到 v2 转换"""
        v1_data = {
            "type": "daily-end",
            "date": "2026-01-23",
            "description": "My Report",
            "tags": ["work", "test"],
        }
        v1_content = "# Daily Report\n\nBody text."

        new_data, new_content = migrate_event(v1_data, v1_content)

        # Verify Data
        assert new_data["id"].startswith("evt_migrated_20260123_")
        assert new_data["type"] == "daily_end"  # normalized
        assert new_data["timestamp"] == "2026-01-23T00:00:00"
        assert new_data["source"] == "manual"
        assert new_data["schema_version"] == 2
        assert new_data["tags"] == ["work", "test"]
        assert "description" not in new_data

        # Verify Content
        assert "> **[迁移自 v1]** My Report" in new_content
        assert "# Daily Report" in new_content

    def test_migrate_event_string_tags(self):
        """测试 tags 为字符串时的转换"""
        v1_data = {"tags": "work, hard"}
        new_data, _ = migrate_event(v1_data, "")
        assert new_data["tags"] == ["work", "hard"]

    def test_migrate_event_unsupported_version(self):
        """测试不支持的版本转换报错"""
        with pytest.raises(ValueError):
            migrate_event({}, "", from_version=2, to_version=3)
