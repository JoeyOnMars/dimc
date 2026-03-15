"""
Tests for migration IO operations (file read/write/backup).
"""

import frontmatter
import pytest

from dimcause.core.migrate import migrate_directory, migrate_file


class TestMigrateIO:
    @pytest.fixture
    def v1_file(self, tmp_path):
        """创建一个 v1 格式的文件"""
        content = """---
type: daily-end
date: 2026-01-23
description: "Test Sync"
tags: [test]
---

# Content
"""
        f = tmp_path / "v1_test.md"
        f.write_text(content, encoding="utf-8")
        return f

    @pytest.fixture
    def v2_file(self, tmp_path):
        """创建一个 v2 格式的文件"""
        content = """---
id: evt_migrated_xxx
type: daily_end
timestamp: 2026-01-23T00:00:00
source: manual
schema_version: 2
tags: [test]
---

# Content
"""
        f = tmp_path / "v2_test.md"
        f.write_text(content, encoding="utf-8")
        return f

    def test_migrate_file_dry_run(self, v1_file):
        """测试 Dry Run 不修改文件"""
        orig_content = v1_file.read_text()

        result = migrate_file(v1_file, dry_run=True, backup=True)

        assert result is True
        assert v1_file.read_text() == orig_content
        # 确认没有备份文件生成
        assert not list(v1_file.parent.glob("*.backup"))

    def test_migrate_file_real_run(self, v1_file):
        """测试实际迁移与备份"""
        result = migrate_file(v1_file, dry_run=False, backup=True)

        assert result is True

        # 验证新内容
        post = frontmatter.load(v1_file)
        assert post.metadata["schema_version"] == 2
        assert post.metadata["id"].startswith("evt_migrated_")
        assert "> **[迁移自 v1]** Test Sync" in post.content

        # 验证备份存在
        backup_file = v1_file.with_name(v1_file.name + ".v1.backup")
        assert backup_file.exists()
        assert "type: daily-end" in backup_file.read_text()

    def test_migrate_file_no_backup(self, v1_file):
        """测试不备份模式"""
        result = migrate_file(v1_file, dry_run=False, backup=False)
        assert result is True
        assert not list(v1_file.parent.glob("*.backup"))

    def test_migrate_file_skip_v2(self, v2_file):
        """测试跳过已经是 v2 的文件"""
        orig_mtime = v2_file.stat().st_mtime
        result = migrate_file(v2_file, dry_run=False)

        assert result is False
        assert v2_file.stat().st_mtime == orig_mtime

    def test_migrate_directory(self, tmp_path):
        """测试目录批量迁移"""
        # Setup: 1 v1 file, 1 v2 file, 1 non-md file
        d = tmp_path / "logs"
        d.mkdir()

        (d / "old.md").write_text("---\ndate: 2026-01-01\n---\nBody", encoding="utf-8")
        (d / "new.md").write_text(
            "---\nschema_version: 2\nid: 1\ntimestamp: 2026\n---\nBody", encoding="utf-8"
        )
        (d / "other.txt").write_text("text")

        # Dry Run
        stats = migrate_directory(d, dry_run=True)
        assert stats["scanned"] == 2
        assert stats["needs_migration"] == 1
        assert stats["migrated"] == 0
        assert stats["skipped"] == 1
        assert len(stats["errors"]) == 0

        # Real Run
        stats = migrate_directory(d, dry_run=False)
        assert stats["migrated"] == 1

        # Verify
        post = frontmatter.load(d / "old.md")
        assert post.metadata["schema_version"] == 2

        # Re-run should skip all
        stats = migrate_directory(d, dry_run=False)
        assert stats["needs_migration"] == 0
        assert stats["skipped"] == 2
