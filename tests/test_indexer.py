"""
索引器模块测试 (Phase 4)
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestIndexer:
    """索引器测试"""

    @pytest.fixture
    def temp_logs_dir(self, monkeypatch):
        """创建临时日志目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            # Mock get_logs_dir
            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            # Mock scan_task_files 避免扫描真实 ~/.dimcause/events/
            monkeypatch.setattr("dimcause.core.indexer.scan_task_files", lambda: [])

            yield logs_dir

    def test_init_db(self, temp_logs_dir):
        """测试数据库初始化"""
        from dimcause.core.indexer import init_db

        # Mock index db path
        db_path = temp_logs_dir / ".index.db"

        conn = sqlite3.connect(db_path)
        conn = init_db(conn)

        # 检查表是否存在
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_empty_index(self, temp_logs_dir, monkeypatch):
        """测试空索引"""
        from dimcause.core.indexer import update_index

        # Mock index db path
        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        stats = update_index()
        assert stats["processed"] == 0
        assert stats["hot"] == 0

    def test_index_single_file(self, temp_logs_dir, monkeypatch):
        """测试索引单个文件"""
        from dimcause.core.indexer import update_index

        # Mock index db path
        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        # 创建测试文件（用今天日期确保进入 hot index）
        from datetime import date as date_cls
        today = date_cls.today()
        year_str = today.strftime("%Y")
        month_day_str = today.strftime("%m-%d")
        date_str = today.strftime("%Y-%m-%d")

        job_dir = temp_logs_dir / year_str / month_day_str / "jobs" / "test-job"
        job_dir.mkdir(parents=True)
        (job_dir / "end.md").write_text(f"""---
type: job-end
job_id: "test-job"
date: "{date_str}"
status: done
description: "测试任务完成"
tags: [test]
---
任务内容
""")

        # 第一次索引
        stats1 = update_index()
        assert stats1["processed"] == 1
        assert stats1["hot"] >= 1

        # 第二次索引 (无变化)
        stats2 = update_index()
        assert stats2["processed"] == 0
        assert stats2["skipped"] == 1

    def test_index_generates_markdown(self, temp_logs_dir, monkeypatch):
        """测试生成 Markdown 视图"""
        from dimcause.core.indexer import update_index

        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        # 创建测试文件（用今天日期确保进入 hot index / INDEX.md）
        from datetime import date as date_cls
        today = date_cls.today()
        year_str = today.strftime("%Y")
        month_day_str = today.strftime("%m-%d")
        date_str = today.strftime("%Y-%m-%d")

        job_dir = temp_logs_dir / year_str / month_day_str / "jobs" / "test"
        job_dir.mkdir(parents=True)
        (job_dir / "end.md").write_text(f"""---
type: job-end
job_id: "test"
date: "{date_str}"
status: done
---
""")

        update_index()

        # 检查 INDEX.md 是否生成
        index_file = temp_logs_dir / "INDEX.md"
        assert index_file.exists()

        content = index_file.read_text()
        assert "Active Context" in content
        assert "test" in content

    def test_rebuild_index(self, temp_logs_dir, monkeypatch):
        """测试重建索引"""
        import time

        from dimcause.core.indexer import rebuild_index, update_index

        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        # 创建测试文件
        job_dir = temp_logs_dir / "2026" / "01-16" / "jobs" / "rebuild-test"
        job_dir.mkdir(parents=True)
        end_file = job_dir / "end.md"
        end_file.write_text("""---
type: job-end
job_id: "rebuild-test"
date: "2026-01-16"
status: done
---
""")

        # 首次索引
        stats1 = update_index()
        assert stats1["processed"] == 1

        # 重建索引 (验证不抛出异常)
        rebuild_index()

        # 修改文件内容触发重新处理
        time.sleep(0.1)  # 确保 mtime 变化
        end_file.write_text("""---
type: job-end
job_id: "rebuild-test"
date: "2026-01-16"
status: done
description: "updated"
---
""")

        stats2 = update_index()
        assert stats2["processed"] == 1

    def test_query_index_hot(self, temp_logs_dir, monkeypatch):
        """测试热索引查询"""
        from dimcause.core.indexer import query_index, update_index

        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        # 创建测试文件
        job_dir = temp_logs_dir / "2026" / "01-17" / "jobs" / "hot-test"
        job_dir.mkdir(parents=True)
        (job_dir / "end.md").write_text("""---
type: job-end
job_id: "hot-test"
date: "2026-01-17"
status: done
---
""")

        update_index()

        # 查询近 7 天
        entries = query_index(days=7)
        assert isinstance(entries, list)

    def test_query_index_filter(self, temp_logs_dir, monkeypatch):
        """测试带过滤的查询"""
        from dimcause.core.indexer import query_index, update_index

        monkeypatch.setattr(
            "dimcause.core.indexer.get_index_db", lambda: temp_logs_dir / ".index.db"
        )

        update_index()

        # 按状态查询
        entries = query_index(status="done")
        assert isinstance(entries, list)

        # 按 job_id 查询
        entries = query_index(job_id="test")
        assert isinstance(entries, list)


class TestIndexerHelpers:
    """索引器辅助函数测试"""

    @pytest.fixture
    def temp_logs_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)

            yield logs_dir

    def test_scan_log_files(self, temp_logs_dir):
        """扫描日志文件"""
        from dimcause.core.indexer import scan_log_files

        # 创建测试文件
        (temp_logs_dir / "2026" / "01-17").mkdir(parents=True)
        (temp_logs_dir / "2026" / "01-17" / "end.md").write_text("test")
        (temp_logs_dir / "2026" / "01-17" / "jobs" / "test").mkdir(parents=True)
        (temp_logs_dir / "2026" / "01-17" / "jobs" / "test" / "end.md").write_text("test")

        files = scan_log_files()
        assert len(files) >= 2

    def test_extract_date_from_path(self):
        """从路径提取日期"""
        from dimcause.core.indexer import _extract_date_from_path

        assert _extract_date_from_path("2026/01-17/end.md") == "2026-01-17"
        assert _extract_date_from_path("2026/01-17/jobs/test/end.md") == "2026-01-17"
        assert _extract_date_from_path("invalid/path") == ""

    def test_generate_table(self):
        """生成 Markdown 表格"""
        from dimcause.core.indexer import _generate_table

        rows = [
            (
                "2026-01-17",
                "test-job",
                "done",
                "Test description",
                "test,unit",
                "2026/01-17/jobs/test/end.md",
            ),
        ]

        content = _generate_table("Test Title", "> Subtitle", rows, detailed=True)
        assert "Test Title" in content
        assert "test-job" in content
        assert "| Date | Job | Status | Summary | Tags |" in content


class TestIndexStats:
    """IndexStats 测试"""

    def test_index_stats_defaults(self):
        """IndexStats 默认值"""
        from dimcause.core.indexer import IndexStats

        stats = IndexStats()
        assert stats.processed == 0
        assert stats.skipped == 0
        assert stats.errors == 0
        assert stats.hot == 0
        assert stats.archive == 0


class TestGenerateMarkdownViews:
    """generate_markdown_views 测试"""

    @pytest.fixture
    def temp_logs_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )

            yield logs_dir

    def test_generate_views_empty(self, temp_logs_dir):
        """空数据库生成视图"""
        import sqlite3

        from dimcause.core.indexer import generate_markdown_views, init_db

        db_path = temp_logs_dir / ".index.db"
        conn = sqlite3.connect(db_path)
        init_db(conn)

        stats = generate_markdown_views(conn)

        assert stats["hot"] == 0
        assert stats["archive"] == 0
        assert (temp_logs_dir / "INDEX.md").exists()

        conn.close()


class TestUpdateIndexWithBadFile:
    """索引更新错误处理测试"""

    @pytest.fixture
    def temp_logs_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )

            yield logs_dir

    def test_index_file_without_frontmatter(self, temp_logs_dir):
        """索引没有 frontmatter 的文件"""
        from dimcause.core.indexer import update_index

        # 创建没有 frontmatter 的 end.md
        day_dir = temp_logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("No frontmatter here, just content")

        stats = update_index()
        # 应该能处理（使用"unknown"类型）
        assert stats["processed"] >= 1


class TestIndexerErrors:
    """Indexer 错误处理测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )

            # 初始化 DB
            conn = sqlite3.connect(logs_dir / ".index.db")
            from dimcause.core.indexer import init_db

            init_db(conn)
            conn.close()

            yield root_dir, logs_dir

    def test_update_index_stat_error(self, temp_project):
        """文件 stat 错误"""
        from unittest.mock import patch

        from dimcause.core.indexer import update_index

        root_dir, logs_dir = temp_project
        day_dir = logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("content")

        original_stat = Path.stat

        class MockStatResult:
            def __init__(self, original):
                self._original = original

            @property
            def st_mtime(self):
                raise OSError("Permission denied")

            def __getattr__(self, name):
                return getattr(self._original, name)

        def mock_stat_v2(self, **kwargs):
            st = original_stat(self)
            if "end.md" in self.name:
                return MockStatResult(st)
            return st

        with patch.object(Path, "stat", mock_stat_v2):
            stats = update_index()
            # If glob calls stat(), it usually checks st_mode or similar.
            # Our MockStatResult proxies everything except st_mtime.
            assert stats["errors"] >= 1

    def test_update_index_unicode_error(self, temp_project):
        """Unicode 解码错误"""
        from dimcause.core.indexer import update_index

        root_dir, logs_dir = temp_project
        day_dir = logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)

        # 写入类似 GBK 或二进制乱码的内容
        with open(day_dir / "end.md", "wb") as f:
            f.write(b"\x80\x81\xff")

        stats = update_index()
        assert stats["errors"] >= 1

    def test_update_index_generic_exception(self, temp_project, monkeypatch):
        """通用异常"""
        from dimcause.core.indexer import update_index

        root_dir, logs_dir = temp_project
        day_dir = logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("some content")

        # Mock parse_frontmatter to raise Exception
        def mock_parse(*args):
            raise ValueError("Something unexpected")

        monkeypatch.setattr("dimcause.core.indexer.parse_frontmatter", mock_parse)

        stats = update_index()
        assert stats["errors"] >= 1


class TestIndexerJobInference:
    """无 Frontmatter 时推断 Job ID"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )
            monkeypatch.setattr("dimcause.core.indexer.scan_task_files", lambda: [])

            # 初始化 DB
            conn = sqlite3.connect(logs_dir / ".index.db")
            from dimcause.core.indexer import init_db

            init_db(conn)
            conn.close()

            yield root_dir, logs_dir

    def test_infer_job_id_from_path(self, temp_project):
        """从路径推断 Job ID"""
        import sqlite3

        from dimcause.core.indexer import update_index

        root_dir, logs_dir = temp_project

        # 创建 jobs 目录下的文件
        job_dir = logs_dir / "2026" / "01-17" / "jobs" / "inferred-job"
        job_dir.mkdir(parents=True)
        # 没有 frontmatter, 必须是 end.md
        (job_dir / "end.md").write_text("Just content without meta")

        update_index()

        # 检查是否正确推断了 job_id
        conn = sqlite3.connect(logs_dir / ".index.db")
        cur = conn.cursor()
        cur.execute("SELECT job_id FROM logs WHERE path LIKE '%inferred-job%'")
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "inferred-job"

    def test_non_standard_path_without_frontmatter_still_skips(self, temp_project):
        """只对标准 logs 路径做保守推断，非标准路径仍跳过。"""
        import sqlite3

        from dimcause.core.indexer import update_index

        root_dir, logs_dir = temp_project

        odd_dir = logs_dir / "misc" / "notes"
        odd_dir.mkdir(parents=True)
        (odd_dir / "end.md").write_text("Just content without meta")

        stats = update_index()

        conn = sqlite3.connect(logs_dir / ".index.db")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM logs WHERE path LIKE '%misc/notes/end.md'")
        row_count = cur.fetchone()[0]
        conn.close()

        assert stats["errors"] >= 1
        assert row_count == 0

    def test_get_logs_dir(self):
        """get_logs_dir 函数"""
        from dimcause.core.indexer import get_logs_dir

        logs = get_logs_dir()
        assert isinstance(logs, Path)

    def test_get_index_db(self):
        """get_index_db 函数"""
        from dimcause.core.indexer import get_index_db

        db = get_index_db()
        assert isinstance(db, Path)
        assert db.suffix == ".db"  # code.db（已从 .index.db 重命名，见 config.py Architecture Fix）


class TestIncrementalUpdate:
    """增量更新测试"""

    @pytest.fixture
    def temp_logs_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )

            yield logs_dir

    def test_skip_unchanged_files(self, temp_logs_dir):
        """跳过未更改的文件"""
        from dimcause.core.indexer import update_index

        # 创建日志
        day_dir = temp_logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("""---
type: daily-end
date: 2026-01-17
status: done
---""")

        # 第一次索引
        stats1 = update_index()
        assert stats1["processed"] >= 1

        # 第二次索引（应该跳过）
        stats2 = update_index()
        assert stats2["skipped"] >= 1
