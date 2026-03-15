"""
Workflow 模块测试

测试从 CLI 抽取的业务逻辑
"""

import tempfile
from pathlib import Path

import pytest


class TestWorkflowResult:
    """WorkflowResult 数据类测试"""

    def test_success_result(self):
        """成功结果"""
        from dimcause.services.workflow import WorkflowResult

        result = WorkflowResult(success=True, message="操作成功", data={"path": "/test/path"})

        assert result.success is True
        assert result.message == "操作成功"
        assert result.data["path"] == "/test/path"

    def test_failure_result(self):
        """失败结果"""
        from dimcause.services.workflow import WorkflowResult

        result = WorkflowResult(success=False, message="操作失败")

        assert result.success is False
        assert result.data is None


class TestCreateDailyLog:
    """create_daily_log 函数测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir

    def test_create_start_log(self, temp_project):
        """创建 daily start 日志"""
        from dimcause.services.workflow import create_daily_log

        root_dir, logs_dir, today_dir = temp_project

        result = create_daily_log("start")

        assert result.success is True
        assert today_dir.exists()
        start_files = list(today_dir.glob("*-start.md"))
        assert start_files, "应有 {hex}-start.md 文件"

        content = start_files[0].read_text()
        assert "session-start" in content
        assert "2026-01-17" in content

    def test_create_end_log(self, temp_project):
        """创建 daily end 日志"""
        from dimcause.services.workflow import create_daily_log

        root_dir, logs_dir, today_dir = temp_project

        result = create_daily_log("end")

        assert result.success is True
        end_files = list(today_dir.glob("*-end.md"))
        assert end_files, "应有 {hex}-end.md 文件"

        content = end_files[0].read_text()
        assert "session-end" in content
        assert "status: done" in content

    def test_duplicate_log(self, temp_project):
        """V6.0 多会话：两次 create_daily_log 都成功，各分配不同序列"""
        from dimcause.services.workflow import create_daily_log

        root_dir, logs_dir, today_dir = temp_project

        # 第一次创建（01-start.md）
        result1 = create_daily_log("start")
        assert result1.success is True

        # 第二次创建应该也成功（02-start.md），V6.0 支持每天多会话
        result2 = create_daily_log("start")
        assert result2.success is True

        # 两次各分配不同文件
        start_files = list(today_dir.glob("*-start.md"))
        assert len(start_files) == 2


class TestCreateJobLog:
    """create_job_log 函数测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir

    def test_create_job_start(self, temp_project):
        """创建 job start 日志"""
        from dimcause.services.workflow import create_job_log

        root_dir, logs_dir, today_dir = temp_project

        result = create_job_log("my-feature", "start")

        assert result.success is True
        assert result.data["job_id"] == "my-feature"

        job_dir = today_dir / "jobs" / "my-feature"
        assert job_dir.exists()
        assert (job_dir / "job-start.md").exists()

        content = (job_dir / "job-start.md").read_text()
        assert "job-start" in content
        assert "my-feature" in content

    def test_create_job_end(self, temp_project):
        """创建 job end 日志"""
        from dimcause.services.workflow import create_job_log

        root_dir, logs_dir, today_dir = temp_project

        # 先创建 start
        create_job_log("my-feature", "start")

        # 再创建 end
        result = create_job_log("my-feature", "end")

        assert result.success is True

        job_dir = today_dir / "jobs" / "my-feature"
        assert (job_dir / "job-end.md").exists()

        content = (job_dir / "job-end.md").read_text()
        assert "job-end" in content
        assert "status: done" in content

    def test_job_id_normalization(self, temp_project):
        """Job ID 标准化"""
        from dimcause.services.workflow import create_job_log

        root_dir, logs_dir, today_dir = temp_project

        # 使用大写和空格
        result = create_job_log("My Feature Task", "start")

        assert result.success is True
        assert result.data["job_id"] == "my-feature-task"

        # 验证目录名是小写连字符
        job_dir = today_dir / "jobs" / "my-feature-task"
        assert job_dir.exists()

    def test_duplicate_job_start(self, temp_project):
        """重复开始任务"""
        from dimcause.services.workflow import create_job_log

        root_dir, logs_dir, today_dir = temp_project

        # 第一次开始
        result1 = create_job_log("my-job", "start")
        assert result1.success is True

        # 第二次开始应该失败
        result2 = create_job_log("my-job", "start")
        assert result2.success is False
        assert "已存在" in result2.message

    def test_multiple_job_end(self, temp_project):
        """多次结束任务（覆盖）"""
        from dimcause.services.workflow import create_job_log

        root_dir, logs_dir, today_dir = temp_project

        # 开始任务
        create_job_log("my-job", "start")

        # 第一次结束
        result1 = create_job_log("my-job", "end")
        assert result1.success is True

        # 第二次结束（覆盖，也应该成功）
        result2 = create_job_log("my-job", "end")
        assert result2.success is True


class TestDailyStartWorkflow:
    """start_daily_workflow 函数测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir, agent_dir

    def test_start_daily_basic(self, temp_project):
        """基本开工流程"""
        from dimcause.services.workflow import start_daily_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        result = start_daily_workflow()

        assert result.success is True
        assert "日志已创建" in result.message
        assert any(today_dir.glob("*-start.md")), "应有 {hex}-start.md 文件"

        # 验证返回的上下文数据
        assert "pending_merge" in result.data
        assert "orphan_jobs" in result.data
        assert "recent_entries" in result.data
        assert "todos" in result.data


class TestEndDailyWorkflow:
    """end_daily_workflow 函数测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir, agent_dir

    def test_end_daily_basic(self, temp_project):
        """基本收工流程"""
        from dimcause.services.workflow import end_daily_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        result = end_daily_workflow(skip_git=True)

        assert result.success is True
        assert any(today_dir.glob("*-end.md")), "应有 {hex}-end.md 文件"
        assert result.data["skip_git"] is True


class TestJobWorkflow:
    """Job 工作流函数测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import datetime as dt
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            # 使用真实今日路径，否则 check_orphan_jobs 7天 cutoff 会过滤掉测试数据
            now = dt.datetime.now()
            today_dir = logs_dir / now.strftime("%Y") / now.strftime("%m-%d")
            today_str = now.strftime("%Y-%m-%d")

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: today_str)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir, agent_dir

    def test_start_job(self, temp_project):
        """开始任务"""
        from dimcause.utils.state import get_active_job
        from dimcause.services.workflow import start_job_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        result = start_job_workflow("test-task")

        assert result.success is True
        assert "开始任务" in result.message

        # 验证活跃任务记录（get_active_job 返回 Tuple[str, Path] 或 None）
        active = get_active_job()
        assert active is not None and active[0] == "test-task"

    def test_end_job_explicit(self, temp_project):
        """显式结束任务"""
        from dimcause.utils.state import get_active_job
        from dimcause.services.workflow import end_job_workflow, start_job_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        start_job_workflow("my-task")
        result = end_job_workflow("my-task")

        assert result.success is True
        assert "结束任务" in result.message

        # 验证活跃任务已清除
        active = get_active_job()
        assert active is None

    def test_end_job_auto_detect(self, temp_project):
        """自动检测结束任务"""
        from dimcause.services.workflow import end_job_workflow, start_job_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        start_job_workflow("auto-task")

        # 不指定 job_id
        result = end_job_workflow()

        assert result.success is True

    def test_end_job_no_active(self, temp_project):
        """无活跃任务时结束"""
        from dimcause.services.workflow import end_job_workflow

        root_dir, logs_dir, today_dir, agent_dir = temp_project

        result = end_job_workflow()

        assert result.success is False
        assert "未检测到" in result.message


class TestTemplates:
    """日志模板测试"""

    def test_daily_start_template(self):
        """daily start 模板"""
        from dimcause.services.workflow import DAILY_START_TEMPLATE

        content = DAILY_START_TEMPLATE.format(
            session_id="2026-01-17-01", iso_timestamp="2026-01-17T09:00:00+08:00", date="2026-01-17"
        )

        assert "session-start" in content
        assert "2026-01-17" in content
        assert "会话开始" in content

    def test_daily_end_template(self):
        """daily end 模板"""
        from dimcause.services.workflow import DAILY_END_TEMPLATE

        content = DAILY_END_TEMPLATE.format(
            session_id="2026-01-17-01", iso_timestamp="2026-01-17T09:00:00+08:00", date="2026-01-17"
        )

        assert "session-end" in content
        assert "status: done" in content
        assert "遗留问题" in content

    def test_job_start_template(self):
        """job start 模板"""
        from dimcause.services.workflow import JOB_START_TEMPLATE

        content = JOB_START_TEMPLATE.format(job_id="test-job", date="2026-01-17")

        assert "job-start" in content
        assert "test-job" in content
        assert "任务目标" in content

    def test_job_end_template(self):
        """job end 模板"""
        from dimcause.services.workflow import JOB_END_TEMPLATE

        content = JOB_END_TEMPLATE.format(job_id="test-job", date="2026-01-17")

        assert "job-end" in content
        assert "status: done" in content
        assert "遗留问题" in content


class TestWorkflowHelpers:
    """工作流辅助函数测试"""

    def test_get_root_dir(self):
        """获取根目录"""
        from dimcause.services.workflow import get_root_dir

        root = get_root_dir()
        assert isinstance(root, Path)

    def test_get_logs_dir(self):
        """获取日志目录"""
        from dimcause.services.workflow import get_logs_dir

        logs = get_logs_dir()
        assert isinstance(logs, Path)
        assert "logs" in str(logs)

    def test_get_today_str(self):
        """获取今日日期字符串"""
        from dimcause.services.workflow import get_today_str

        date_str = get_today_str()
        assert isinstance(date_str, str)
        # 格式应该是 YYYY-MM-DD
        assert len(date_str) == 10
        assert date_str.count("-") == 2

    def test_get_today_dir(self, monkeypatch):
        """获取今日目录"""
        import tempfile

        from dimcause.services.workflow import get_today_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)

            today = get_today_dir()
            assert isinstance(today, Path)
            # 应该包含年份目录
            parts = today.parts
            assert any(p.isdigit() and len(p) == 4 for p in parts)

    def test_get_today_str_without_pytz(self, monkeypatch):
        """没有 pytz 时的回退"""
        import sys

        # 模拟 pytz 不存在
        original_modules = sys.modules.copy()
        if "pytz" in sys.modules:
            del sys.modules["pytz"]

        # 确保 import pytz 会失败
        def raise_import_error(*args):
            raise ImportError("No module named 'pytz'")

        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pytz":
                raise ImportError("No module named 'pytz'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # 重新导入以测试
        import importlib

        from dimcause.services import workflow

        importlib.reload(workflow)

        # 应该能正常工作（使用本地时间）
        date_str = workflow.get_today_str()
        assert len(date_str) == 10

        # 恢复
        sys.modules.update(original_modules)


class TestStartDailyWithContext:
    """start_daily_workflow 上下文测试"""

    @pytest.fixture
    def temp_project_with_context(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            # 创建待合并文件
            (agent_dir / "pending_merge.txt").write_text("daily/2026-01-16")

            # 创建未闭合任务
            job_dir = logs_dir / "2026" / "01-16" / "jobs" / "orphan-job"
            job_dir.mkdir(parents=True)
            (job_dir / "start.md").write_text("---\ntype: job-start\njob_id: orphan-job\n---")

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)

            yield root_dir, logs_dir, today_dir, agent_dir

    def test_start_with_pending_merge(self, temp_project_with_context):
        """开工时检测到待合并分支"""
        from dimcause.services.workflow import start_daily_workflow

        result = start_daily_workflow()

        assert result.success is True
        assert result.data["pending_merge"] == "daily/2026-01-16"


class TestEndDailyWithErrors:
    """end_daily_workflow 错误处理测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            today_dir = logs_dir / "2026" / "01-17"

            monkeypatch.setattr("dimcause.services.workflow.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_dir", lambda: today_dir)
            monkeypatch.setattr("dimcause.services.workflow.get_today_str", lambda: "2026-01-17")
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_today_dir", lambda: today_dir)

            yield root_dir, logs_dir, today_dir

    def test_end_with_index_error(self, temp_project, monkeypatch):
        """收工时索引更新失败"""
        from dimcause.services.workflow import end_daily_workflow

        # 模拟索引失败
        def mock_update_index():
            raise Exception("Database error")

        monkeypatch.setattr("dimcause.core.indexer.update_index", mock_update_index)

        result = end_daily_workflow(skip_git=True)

        # 应该仍然成功（只是索引有错误）
        assert result.success is True
        assert "error" in result.data["index"]


class TestGetContextSummary:
    """get_context_summary 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            # 创建测试日志
            day_dir = logs_dir / "2026" / "01-16"
            day_dir.mkdir(parents=True)
            (day_dir / "end.md").write_text("""---
type: daily-end
date: 2026-01-16
status: done
---

## [待办]
- 测试任务
""")

            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_get_context_summary(self, temp_project):
        """获取上下文摘要"""
        from dimcause.services.workflow import get_context_summary

        summary = get_context_summary()

        assert "pending_merge" in summary
        assert "orphan_jobs" in summary
        assert "recent_entries" in summary
        assert "todos" in summary
        assert "has_todos" in summary


class TestRunIndex:
    """run_index 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            day_dir = logs_dir / "2026" / "01-17"
            day_dir.mkdir(parents=True)
            (day_dir / "end.md").write_text("""---
type: daily-end
date: 2026-01-17
status: done
---""")

            monkeypatch.setattr("dimcause.core.indexer.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr(
                "dimcause.core.indexer.get_index_db", lambda: logs_dir / ".index.db"
            )

            yield root_dir, logs_dir

    def test_run_index_normal(self, temp_project):
        """正常运行索引"""
        from dimcause.services.workflow import run_index

        stats = run_index()

        assert "processed" in stats
        assert "skipped" in stats
        assert "errors" in stats
        assert "hot" in stats
        assert "archive" in stats

    def test_run_index_rebuild(self, temp_project):
        """重建索引"""
        from dimcause.services.workflow import run_index

        stats = run_index(rebuild=True)

        assert stats["processed"] >= 0


class TestGetStatsSummary:
    """get_stats_summary 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.stats.get_logs_dir", lambda: logs_dir)

            yield root_dir, logs_dir

    def test_get_stats_summary(self, temp_project):
        """获取统计摘要"""
        from dimcause.services.workflow import get_stats_summary

        summary = get_stats_summary()

        assert "total_logs" in summary
        assert "tokens_today" in summary
        assert "tokens_month" in summary
