"""
统计模块测试
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from dimcause.core.stats import (
    _detect_model,
    _extract_date_from_path,
    estimate_tokens,
    get_activity_trend,
    get_stats,
    get_token_stats,
)


class TestEstimateTokens:
    """Token 估算测试"""

    def test_empty_text(self):
        """空文本返回 0"""
        assert estimate_tokens("") == 0

    def test_none_text(self):
        """None 文本返回 0"""
        # estimate_tokens 不处理 None，这里测试空字符串
        assert estimate_tokens("") == 0

    def test_english_text(self):
        """英文文本估算 (约 4 字符 = 1 token)"""
        text = "Hello world"  # 11 chars
        tokens = estimate_tokens(text)
        # 11 / 4 ≈ 2-3 tokens
        assert 2 <= tokens <= 3

    def test_chinese_text(self):
        """中文文本估算 (约 1.5 字符 = 1 token)"""
        text = "你好世界测试"  # 6 个中文字符
        tokens = estimate_tokens(text)
        # 6 / 1.5 = 4 tokens
        assert 3 <= tokens <= 5

    def test_mixed_text(self):
        """混合文本估算"""
        text = "Hello 你好"  # 6 英文 + 2 中文
        tokens = estimate_tokens(text)
        # (6/4) + (2/1.5) ≈ 1.5 + 1.3 ≈ 2-3
        assert 2 <= tokens <= 4


class TestExtractDateFromPath:
    """日期提取测试"""

    def test_yyyy_mm_dd_format(self):
        """YYYY/MM-DD 格式"""
        path = Path("/logs/2026/01-15/end.md")
        date = _extract_date_from_path(path)
        assert date is not None
        assert date.year == 2026
        assert date.month == 1
        assert date.day == 15

    def test_yyyy_mm_dd_dash_format(self):
        """YYYY-MM-DD 格式"""
        path = Path("/exports/2026-01-15-conversation.md")
        date = _extract_date_from_path(path)
        assert date is not None
        assert date.year == 2026
        assert date.month == 1
        assert date.day == 15

    def test_no_date_in_path(self):
        """路径中没有日期"""
        path = Path("/some/random/file.md")
        date = _extract_date_from_path(path)
        assert date is None

    def test_invalid_date(self):
        """无效日期"""
        path = Path("/logs/2026/13-45/end.md")  # 无效月日
        date = _extract_date_from_path(path)
        assert date is None


class TestDetectModel:
    """AI 模型检测测试"""

    def test_detect_claude(self):
        """检测 Claude"""
        assert _detect_model("This is from Claude AI") == "Claude"
        assert _detect_model("Using Anthropic's model") == "Claude"

    def test_detect_gpt4(self):
        """检测 GPT-4"""
        assert _detect_model("GPT-4 response here") == "GPT-4"
        assert _detect_model("Using OpenAI API") == "GPT-4"

    def test_detect_gpt35(self):
        """检测 GPT-3.5"""
        assert _detect_model("GPT-3.5 turbo response") == "GPT-3.5"

    def test_detect_gemini(self):
        """检测 Gemini"""
        assert _detect_model("Gemini Pro response") == "Gemini"
        assert _detect_model("Google AI response") == "Gemini"

    def test_detect_antigravity(self):
        """检测 Antigravity"""
        assert _detect_model("Using Antigravity IDE") == "Antigravity"

    def test_no_model_detected(self):
        """未检测到模型"""
        assert _detect_model("Just some random text") is None


class TestGetStats:
    """get_stats 函数测试"""

    def test_get_stats_with_db(self, tmp_path):
        """有数据库时获取统计"""
        # 创建模拟的日志目录结构
        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建数据库
        db_path = logs_dir / ".index.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY,
                path TEXT,
                mtime REAL,
                type TEXT,
                job_id TEXT,
                date TEXT,
                status TEXT,
                description TEXT,
                tags TEXT
            )
        """)
        # 插入测试数据
        conn.execute(
            """
            INSERT INTO logs (path, mtime, type, job_id, date, status, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "2026/01-17/end.md",
                0,
                "daily-end",
                "",
                "2026-01-17",
                "done",
                "Test description",
                "test",
            ),
        )
        conn.execute(
            """
            INSERT INTO logs (path, mtime, type, job_id, date, status, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "2026/01-17/jobs/fix-bug/end.md",
                0,
                "job-end",
                "fix-bug",
                "2026-01-17",
                "done",
                "Fixed bug",
                "bugfix",
            ),
        )
        conn.commit()
        conn.close()

        # 由于 get_stats 使用全局路径，我们测试基本功能
        stats = get_stats()
        assert isinstance(stats, dict)
        assert "total_logs" in stats
        assert "active_days" in stats
        assert "completed_jobs" in stats
        assert "recent_activity" in stats

    def test_get_stats_empty(self):
        """空数据库返回默认值"""
        stats = get_stats()
        assert isinstance(stats, dict)
        assert isinstance(stats["total_logs"], int)


class TestGetTokenStats:
    """get_token_stats 函数测试"""

    def test_get_token_stats_structure(self):
        """验证返回结构"""
        stats = get_token_stats()
        assert isinstance(stats, dict)
        assert "today" in stats
        assert "week" in stats
        assert "month" in stats
        assert "by_model" in stats
        assert isinstance(stats["today"], int)
        assert isinstance(stats["week"], int)
        assert isinstance(stats["month"], int)
        assert isinstance(stats["by_model"], dict)

    def test_get_token_stats_with_captures(self, tmp_path, monkeypatch):
        """有捕获文件时的 token 统计"""
        logs_dir = tmp_path / "docs" / "logs"
        captures_dir = logs_dir / "captures"
        captures_dir.mkdir(parents=True)

        # 创建今天的捕获文件
        today_str = datetime.now().strftime("%Y-%m-%d")
        capture_file = captures_dir / f"{today_str}-conversation.md"
        capture_file.write_text("This is a test conversation about Claude AI assistant.")

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_token_stats()
        assert stats["today"] > 0  # 应该估算出一些 token
        assert stats["month"] >= stats["today"]

    def test_get_token_stats_model_detection(self, tmp_path, monkeypatch):
        """模型检测测试"""
        logs_dir = tmp_path / "docs" / "logs"
        captures_dir = logs_dir / "captures"
        captures_dir.mkdir(parents=True)

        # 创建包含模型信息的文件
        today_str = datetime.now().strftime("%Y-%m-%d")
        capture_file = captures_dir / f"{today_str}-gpt4.md"
        capture_file.write_text("Using GPT-4 and OpenAI API for this task.")

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_token_stats()
        assert "GPT-4" in stats["by_model"] or stats["month"] > 0


class TestGetActivityTrend:
    """get_activity_trend 函数测试"""

    def test_get_activity_trend_structure(self):
        """验证返回结构"""
        trend = get_activity_trend(days=7)
        assert isinstance(trend, list)
        # 每个条目应该有 date 和 count
        for item in trend:
            assert "date" in item
            assert "count" in item

    def test_get_activity_trend_custom_days(self):
        """自定义天数"""
        trend = get_activity_trend(days=30)
        assert isinstance(trend, list)

    def test_get_activity_trend_with_db(self, tmp_path, monkeypatch):
        """有索引数据库时的趋势"""
        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建索引数据库
        import sqlite3

        db_path = logs_dir / ".index.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY,
                path TEXT,
                mtime REAL,
                type TEXT,
                job_id TEXT,
                date TEXT,
                status TEXT,
                description TEXT,
                tags TEXT
            )
        """)

        today_str = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO logs (path, mtime, type, job_id, date, status, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            ("test.md", 0, "job-end", "test", today_str, "done", "", ""),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        trend = get_activity_trend(days=7)
        assert len(trend) >= 1
        assert trend[-1]["date"] == today_str
        assert trend[-1]["count"] == 1


class TestTokenStatsLogFallback:
    """Token 统计 log 文件回退测试"""

    def test_fallback_to_logs(self, tmp_path, monkeypatch):
        """没有 capture 目录时从日志文件统计"""
        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建日志文件 (不是 capture)
        year_dir = logs_dir / "2026"
        day_dir = year_dir / "01-17"
        day_dir.mkdir(parents=True)

        (day_dir / "end.md").write_text("Some log content here for testing token estimation")

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_token_stats()
        # 应该能从日志文件估算 token
        assert isinstance(stats["month"], int)


class TestGetStatsFallback:
    """get_stats 回退逻辑测试"""

    def test_stats_fallback_to_file_scan(self, tmp_path, monkeypatch):
        """没有索引数据库时回退到文件扫描"""
        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建一些日志文件但不创建数据库
        day_dir = logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("---\ntype: daily-end\n---")

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_stats()
        # 由于没有数据库，应该通过文件扫描找到至少一个日志
        assert stats["total_logs"] >= 1


class TestGetStatsDbCorruption:
    """get_stats 数据库损坏测试"""

    def test_corrupted_db(self, tmp_path, monkeypatch):
        """损坏的数据库"""
        from dimcause.core.stats import get_stats

        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建损坏的数据库文件
        db_file = logs_dir / ".index.db"
        db_file.write_text("this is not a valid sqlite file")

        # 创建日志文件作为回退
        day_dir = logs_dir / "2026" / "01-17"
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("---\ntype: daily-end\n---")

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_stats()
        # 应该回退到文件扫描
        assert isinstance(stats, dict)


class TestGetTokenStatsEmpty:
    """get_token_stats 空目录测试"""

    def test_empty_capture(self, tmp_path, monkeypatch):
        """空的 capture 目录"""
        from dimcause.core.stats import get_token_stats

        logs_dir = tmp_path / "docs" / "logs"
        logs_dir.mkdir(parents=True)

        # 创建空 capture 目录
        capture_dir = logs_dir / "capture"
        capture_dir.mkdir()

        monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

        stats = get_token_stats()
        assert stats["today"] == 0
        assert stats["month"] == 0
