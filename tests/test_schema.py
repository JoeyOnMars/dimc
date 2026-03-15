"""
Schema 模块测试 (Phase 1)
"""

from datetime import date

from dimcause.core.schema import (
    JobEndFrontmatter,
    JobStartFrontmatter,
    LogType,
    SessionEndFrontmatter,
    SessionStartFrontmatter,
    Status,
    parse_frontmatter,
    parse_yaml_frontmatter,
    validate_frontmatter,
)


class TestParseYamlFrontmatter:
    """YAML Frontmatter 解析测试"""

    def test_basic_parsing(self):
        content = """---
type: job-end
job_id: "test-job"
date: "2026-01-15"
status: done
---
Content here
"""
        data = parse_yaml_frontmatter(content)
        assert data["type"] == "job-end"
        assert data["job_id"] == "test-job"
        assert data["date"] == "2026-01-15"
        assert data["status"] == "done"

    def test_no_frontmatter(self):
        content = "Just regular content"
        data = parse_yaml_frontmatter(content)
        assert data == {}

    def test_incomplete_frontmatter(self):
        content = """---
type: job-end
"""
        data = parse_yaml_frontmatter(content)
        assert data == {}  # 没有闭合的 ---

    def test_array_parsing(self):
        content = """---
tags: [ui, frontend, polish]
---
"""
        data = parse_yaml_frontmatter(content)
        assert data["tags"] == ["ui", "frontend", "polish"]

    def test_quoted_values(self):
        content = """---
description: "包含: 冒号的值"
---
"""
        data = parse_yaml_frontmatter(content)
        assert data["description"] == "包含: 冒号的值"

    def test_key_normalization(self):
        content = """---
job-id: test
Job_ID: test2
---
"""
        data = parse_yaml_frontmatter(content)
        assert data["job_id"] == "test2"  # 后者覆盖前者


class TestParseFrontmatter:
    """Frontmatter 解析和验证测试"""

    def test_valid_job_end(self):
        content = """---
type: job-end
job_id: "ui-polish"
date: "2026-01-15"
status: done
description: "完成按钮样式"
tags: [ui, frontend]
---
正文内容
"""
        result = parse_frontmatter(content)
        assert result is not None
        assert isinstance(result, JobEndFrontmatter)
        assert result.job_id == "ui-polish"
        assert result.status == Status.DONE
        assert result.tags == ["ui", "frontend"]

    def test_valid_session_end(self):
        content = """---
type: session-end
date: "2026-01-15"
status: done
---
"""
        result = parse_frontmatter(content)
        assert result is not None
        assert isinstance(result, SessionEndFrontmatter)

    def test_legacy_daily_end_conversion(self):
        """测试 daily-end 自动转换为 session-end"""
        content = """---
type: daily-end
date: "2026-01-15"
status: done
---
"""
        result = parse_frontmatter(content)
        assert result is not None
        assert isinstance(result, SessionEndFrontmatter)
        assert result.type == LogType.SESSION_END

    def test_invalid_job_id_returns_none(self):
        content = """---
type: job-end
job_id: "Invalid ID!"
date: "2026-01-15"
---"""
        result = parse_frontmatter(content)
        # job_id 包含非法字符，应该返回 None
        assert result is None

    def test_missing_frontmatter(self):
        result = parse_frontmatter("no frontmatter here")
        assert result is None

    def test_flexible_tags_string(self):
        content = """---
type: session-end
date: "2026-01-15"
tags: ui, frontend, polish
---"""
        result = parse_frontmatter(content)
        assert result is not None
        assert result.tags == ["ui", "frontend", "polish"]

    def test_flexible_date_formats(self):
        # YYYY-MM-DD
        content1 = """---
type: session-end
date: "2026-01-15"
---"""
        r1 = parse_frontmatter(content1)
        assert r1 is not None
        assert r1.date == date(2026, 1, 15)


class TestValidateFrontmatter:
    """Frontmatter 验证测试"""

    def test_valid_returns_true(self):
        content = """---
type: job-end
job_id: "test"
date: "2026-01-15"
---"""
        is_valid, error = validate_frontmatter(content)
        assert is_valid is True
        assert error is None

    def test_invalid_returns_error(self):
        content = """---
type: job-end
date: "invalid-date"
---"""
        is_valid, error = validate_frontmatter(content)
        assert is_valid is False
        assert error is not None


class TestLogType:
    """LogType 枚举测试"""

    def test_log_type_values(self):
        """验证 LogType 枚举值"""
        assert LogType.SESSION_START.value == "session-start"
        assert LogType.SESSION_END.value == "session-end"
        assert LogType.JOB_START.value == "job-start"
        assert LogType.JOB_END.value == "job-end"


class TestStatus:
    """Status 枚举测试"""

    def test_status_values(self):
        """验证 Status 枚举值"""
        assert Status.ACTIVE.value == "active"
        assert Status.DONE.value == "done"
        assert Status.BLOCKED.value == "blocked"
        assert Status.PLANNING.value == "planning"
        assert Status.ABANDONED.value == "abandoned"


class TestJobEndFrontmatter:
    """JobEndFrontmatter 测试"""

    def test_create_frontmatter(self):
        """创建 Frontmatter"""
        fm = JobEndFrontmatter(
            type=LogType.JOB_END,
            job_id="test-job",
            date=date(2026, 1, 15),
            status=Status.DONE,
            description="Test description",
            tags=["test", "unit"],
        )
        assert fm.job_id == "test-job"
        assert fm.status == Status.DONE
        assert fm.tags == ["test", "unit"]

    def test_job_id_normalization(self):
        """job_id 标准化测试"""
        # 大写 -> 小写
        fm = JobStartFrontmatter(
            job_id="Test-Job",
            date=date(2026, 1, 15),
        )
        assert fm.job_id == "test-job"

    def test_job_id_space_to_dash(self):
        """job_id 空格转横杠"""
        fm = JobStartFrontmatter(
            job_id="my job",
            date=date(2026, 1, 15),
        )
        assert fm.job_id == "my-job"


class TestSessionEndFrontmatter:
    """SessionEndFrontmatter 测试"""

    def test_create_session_end(self):
        """创建 SessionEndFrontmatter"""
        fm = SessionEndFrontmatter(
            type=LogType.SESSION_END,
            date=date(2026, 1, 15),
            status=Status.DONE,
        )
        assert fm.type == LogType.SESSION_END
        assert fm.date == date(2026, 1, 15)


class TestSessionStartFrontmatter:
    """SessionStartFrontmatter 测试"""

    def test_create_session_start(self):
        """创建 SessionStartFrontmatter"""
        fm = SessionStartFrontmatter(
            date=date(2026, 1, 15),
        )
        assert fm.type == LogType.SESSION_START


class TestParseYamlEdgeCases:
    """YAML 解析边缘情况测试"""

    def test_quoted_colons(self):
        """处理引号中的冒号"""
        content = """---
description: "包含: 冒号的值"
type: session-end
date: "2026-01-15"
---"""
        result = parse_frontmatter(content)
        assert result is not None
        assert "冒号" in result.description

    def test_tags_as_string(self):
        """tags 作为逗号分隔字符串"""
        content = """---
type: session-end
date: "2026-01-15"
tags: "ui, frontend, polish"
---"""
        result = parse_frontmatter(content)
        assert result is not None
        assert "ui" in result.tags


class TestValidateFrontmatterTypes:
    """不同类型的 validate_frontmatter 测试"""

    def test_validate_job_start(self):
        """验证 job-start"""
        content = """---
type: job-start
job_id: "test-job"
date: "2026-01-15"
---"""
        is_valid, error = validate_frontmatter(content)
        assert is_valid is True

    def test_validate_session_start(self):
        """验证 session-start (legacy daily-start)"""
        content = """---
type: session-start
date: "2026-01-15"
---"""
        is_valid, error = validate_frontmatter(content)
        assert is_valid is True

    def test_validate_unknown_type(self):
        """未知类型验证失败"""
        content = """---
type: custom-type
date: "2026-01-15"
---"""
        is_valid, error = validate_frontmatter(content)
        # 未知类型验证失败
        assert is_valid is False


class TestParseFrontmatterUnknownType:
    """未知类型解析测试"""

    def test_parse_unknown_type(self):
        """解析未知类型返回 None"""
        content = """---
type: custom-type
date: "2026-01-15"
---"""
        result = parse_frontmatter(content)
        # 未知类型返回 None
        assert result is None
