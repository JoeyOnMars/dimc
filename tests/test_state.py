"""
状态管理模块测试 (Phase 3)
"""

import tempfile
from pathlib import Path

import pytest


class TestState:
    """状态管理测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        """创建临时项目目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_pending_merge_workflow(self, temp_project):
        """测试待合并分支工作流"""
        from dimcause.utils.state import (
            check_pending_merge,
            clear_pending_merge,
            set_pending_merge,
        )

        root_dir, logs_dir, agent_dir = temp_project

        # 初始状态: 无待合并
        assert check_pending_merge() is None

        # 设置待合并
        set_pending_merge("daily/2026-01-15")
        assert check_pending_merge() == "daily/2026-01-15"

        # 清除
        clear_pending_merge()
        assert check_pending_merge() is None

    def test_orphan_job_detection(self, temp_project):
        """测试未闭合任务检测"""
        from datetime import datetime

        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 初始状态: 无 orphan
        orphans = check_orphan_jobs()
        assert len(orphans) == 0

        # 创建一个 orphan job (只有 job-start.md)，使用今天日期确保在 cutoff 范围内
        today = datetime.now()
        year = today.strftime("%Y")
        day = today.strftime("%m-%d")
        job_dir = logs_dir / year / day / "jobs" / "orphan-task"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("---\ntype: job-start\n---")

        orphans = check_orphan_jobs()
        assert len(orphans) == 1
        assert orphans[0]["id"] == "orphan-task"

        # 添加 job-end.md 后不再是 orphan
        (job_dir / "job-end.md").write_text("---\ntype: job-end\n---")
        orphans = check_orphan_jobs()
        assert len(orphans) == 0

    def test_active_job_tracking(self, temp_project):
        """测试活跃任务追踪 (通过 orphan 机制)"""
        from datetime import datetime

        from dimcause.utils.state import get_active_job

        root_dir, logs_dir, agent_dir = temp_project

        # 初始状态: 无活跃任务
        assert get_active_job() is None

        # 创建一个 orphan job → get_active_job 应该返回它
        today = datetime.now()
        job_dir = logs_dir / today.strftime("%Y") / today.strftime("%m-%d") / "jobs" / "my-task"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("---\ntype: job-start\n---")

        result = get_active_job()
        assert result is not None
        assert result[0] == "my-task"  # (job_id, path) tuple

        # 添加 job-end.md 后不再活跃
        (job_dir / "job-end.md").write_text("---\ntype: job-end\n---")
        assert get_active_job() is None


class TestContext:
    """上下文加载测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        """创建临时项目目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)

            yield root_dir, logs_dir, agent_dir

    def test_extract_todos(self, temp_project):
        """测试 TODO 提取"""
        from dimcause.core.context import extract_todos_from_file

        root_dir, logs_dir, agent_dir = temp_project

        # 创建包含 TODO 的文件
        end_file = logs_dir / "2026" / "01-15" / "end.md"
        end_file.parent.mkdir(parents=True)
        end_file.write_text("""---
type: daily-end
date: "2026-01-15"
---

## ✅ 完成
- 完成了任务A

## [待办]
- 任务B待完成
- 任务C需要跟进

## ⏭️ 明日切入点
- 从任务B开始
""")

        todos = extract_todos_from_file(end_file)
        assert len(todos) >= 2
        assert "任务B待完成" in todos

    def test_load_context_empty(self, temp_project):
        """测试空项目的上下文加载"""
        from dimcause.core.context import load_context

        ctx = load_context()
        assert ctx.pending_merge is None
        assert len(ctx.todos) == 0
        assert len(ctx.orphan_jobs) == 0


class TestGetTodayDir:
    """get_today_dir 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)

            yield root_dir, logs_dir

    def test_get_today_dir(self, temp_project):
        """获取今日目录"""
        from dimcause.utils.state import get_today_dir

        today_dir = get_today_dir()
        assert isinstance(today_dir, Path)
        # 应该包含年份和日期
        assert today_dir.parent.name.isdigit()  # 年份目录

    def test_ensure_today_dir(self, temp_project):
        """确保今日目录（通过 get_today_dir + mkdir）"""
        from dimcause.utils.state import get_today_dir

        today_dir = get_today_dir()
        today_dir.mkdir(parents=True, exist_ok=True)
        assert today_dir.exists()


class TestOrphanJob:
    """OrphanJob 测试 (check_orphan_jobs 返回 List[dict])"""

    def test_orphan_job_creation(self):
        """创建 orphan dict 格式"""
        from datetime import datetime

        # state.py 的 check_orphan_jobs 返回 List[dict]，不是 dataclass
        orphan = {
            "id": "test-job",
            "path": "2026/01-17/jobs/test-job",
            "date": "2026-01-17",
            "start_time": datetime.now(),
        }

        assert orphan["id"] == "test-job"
        assert orphan["path"] == "2026/01-17/jobs/test-job"
        assert orphan["date"] == "2026-01-17"


class TestGetRootDir:
    """get_root_dir 测试"""

    def test_get_root_dir(self):
        """获取根目录"""
        from dimcause.utils.state import get_root_dir

        root = get_root_dir()
        assert isinstance(root, Path)


class TestCheckOrphanJobs:
    """check_orphan_jobs 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_empty_logs(self, temp_project):
        """空日志目录"""
        from dimcause.utils.state import check_orphan_jobs

        orphans = check_orphan_jobs()
        assert orphans == []

    def test_find_orphan(self, temp_project):
        """找到未闭合任务"""
        from datetime import datetime

        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 创建今天的未闭合 job
        today = datetime.now()
        year = today.strftime("%Y")
        day = today.strftime("%m-%d")

        job_dir = logs_dir / year / day / "jobs" / "orphan-test"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("---\ntype: job-start\n---")
        # 不创建 job-end.md

        orphans = check_orphan_jobs(days=1)
        assert len(orphans) >= 1
        assert any(o["id"] == "orphan-test" for o in orphans)

    def test_closed_job_not_orphan(self, temp_project):
        """已闭合任务不是孤儿"""
        from datetime import datetime

        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 创建已闭合 job
        today = datetime.now()
        year = today.strftime("%Y")
        day = today.strftime("%m-%d")

        job_dir = logs_dir / year / day / "jobs" / "closed-job"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("---\ntype: job-start\n---")
        (job_dir / "job-end.md").write_text("---\ntype: job-end\n---")

        orphans = check_orphan_jobs(days=1)
        assert not any(o["id"] == "closed-job" for o in orphans)


class TestGetActiveJob:
    """get_active_job 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_get_active_from_file(self, temp_project):
        """从 orphan job 获取活跃任务"""
        from datetime import datetime

        from dimcause.utils.state import get_active_job

        root_dir, logs_dir, agent_dir = temp_project

        # get_active_job 现在通过 check_orphan_jobs 查找，返回 (id, path) tuple
        today = datetime.now()
        job_dir = logs_dir / today.strftime("%Y") / today.strftime("%m-%d") / "jobs" / "my-active-job"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("---\ntype: job-start\n---")

        result = get_active_job()
        assert result is not None
        assert result[0] == "my-active-job"

    def test_get_active_none(self, temp_project):
        """没有活跃任务"""
        from dimcause.utils.state import get_active_job

        result = get_active_job()
        assert result is None


class TestRecordJob:
    """record_job_end 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)

            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield agent_dir

    def test_record_job_end_exists(self, temp_project):
        """record_job_end 函数存在且可调用"""
        from dimcause.utils.state import record_job_end

        # 这里只做最小 smoke test；显式 marker 行为由专门测试覆盖
        record_job_end()

class TestCheckOrphanJobsEdgeCases:
    """check_orphan_jobs 边缘情况测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_file_instead_of_dir(self, temp_project):
        """文件而非目录"""
        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 创建一个文件而非目录
        (logs_dir / "2026").mkdir()
        (logs_dir / "2026" / "not-a-date").write_text("file content")

        # 不应该崩溃
        orphans = check_orphan_jobs(days=30)
        assert isinstance(orphans, list)

    def test_invalid_date_format(self, temp_project):
        """无效日期格式"""
        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 创建无效日期目录
        invalid_dir = logs_dir / "2026" / "invalid-date"
        invalid_dir.mkdir(parents=True)

        # 不应该崩溃
        orphans = check_orphan_jobs(days=30)
        assert isinstance(orphans, list)

    def test_job_dir_is_file(self, temp_project):
        """job 是文件而非目录"""
        from datetime import datetime

        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        today = datetime.now()
        year = today.strftime("%Y")
        day = today.strftime("%m-%d")

        jobs_dir = logs_dir / year / day / "jobs"
        jobs_dir.mkdir(parents=True)

        # 创建一个文件而非 job 目录
        (jobs_dir / "not-a-dir").write_text("file")

        orphans = check_orphan_jobs(days=1)
        assert isinstance(orphans, list)


class TestGetActiveJobOrphan:
    """get_active_job 使用 orphan 回退"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_get_active_from_orphan(self, temp_project):
        """从 orphan job 获取活跃任务"""
        from datetime import datetime

        from dimcause.utils.state import get_active_job

        root_dir, logs_dir, agent_dir = temp_project

        # 创建一个 orphan job (今天有 job-start.md 没有 job-end.md)
        today = datetime.now()
        year = today.strftime("%Y")
        day = today.strftime("%m-%d")

        job_dir = logs_dir / year / day / "jobs" / "orphan-task"
        job_dir.mkdir(parents=True)
        (job_dir / "job-start.md").write_text("""---
type: job-start
job_id: orphan-task
---""")

        # get_active_job 返回 (job_id, path) tuple
        active = get_active_job()
        assert active is not None
        assert active[0] == "orphan-task"


class TestYearAsFile:
    """年份目录是文件的情况"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield root_dir, logs_dir, agent_dir

    def test_year_is_file(self, temp_project):
        """年份是文件而非目录"""
        from dimcause.utils.state import check_orphan_jobs

        root_dir, logs_dir, agent_dir = temp_project

        # 创建 2026 文件而非目录
        (logs_dir / "2026").write_text("not a directory")

        orphans = check_orphan_jobs(days=30)
        assert isinstance(orphans, list)
