"""
DIMCAUSE v0.1 State 和 Graph 测试

目标: 提升覆盖率到 90%
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestStateManagement:
    """状态管理测试"""

    @patch("dimcause.utils.state.get_config")
    def test_get_root_dir(self, mock_config):
        """测试获取根目录"""
        from dimcause.utils.state import get_root_dir

        mock_cfg = MagicMock()
        mock_cfg.root_dir = Path("/test/root")
        mock_config.return_value = mock_cfg

        result = get_root_dir()

        assert result == Path("/test/root")

    @patch("dimcause.utils.state.get_config")
    def test_get_logs_dir(self, mock_config):
        """测试获取日志目录"""
        from dimcause.utils.state import get_logs_dir

        mock_cfg = MagicMock()
        mock_cfg.logs_dir = Path("/test/logs")
        mock_config.return_value = mock_cfg

        result = get_logs_dir()

        assert result == Path("/test/logs")

    @patch("dimcause.utils.state.get_config")
    def test_get_agent_dir(self, mock_config):
        """测试获取 agent 目录"""
        from dimcause.utils.state import get_agent_dir

        mock_cfg = MagicMock()
        mock_cfg.agent_dir = Path("/test/.agent")
        mock_config.return_value = mock_cfg

        result = get_agent_dir()

        assert result == Path("/test/.agent")


class TestPendingMerge:
    """待合并分支测试"""

    @patch("dimcause.utils.state.get_agent_dir")
    def test_check_pending_merge_exists(self, mock_agent_dir):
        """测试检查存在的待合并"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            mock_agent_dir.return_value = agent_dir

            # 创建文件
            pending_file = agent_dir / "pending_merge.txt"
            pending_file.write_text("feature/test-branch")

            from dimcause.utils.state import check_pending_merge

            result = check_pending_merge()

            assert result == "feature/test-branch"

    @patch("dimcause.utils.state.get_agent_dir")
    def test_check_pending_merge_not_exists(self, mock_agent_dir):
        """测试检查不存在的待合并"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent_dir.return_value = Path(tmpdir)

            from dimcause.utils.state import check_pending_merge

            result = check_pending_merge()

            assert result is None

    @patch("dimcause.utils.state.get_agent_dir")
    def test_set_pending_merge(self, mock_agent_dir):
        """测试设置待合并"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent_dir.return_value = Path(tmpdir)

            from dimcause.utils.state import set_pending_merge

            set_pending_merge("feature/new-branch")

            pending_file = Path(tmpdir) / "pending_merge.txt"
            assert pending_file.exists()
            assert pending_file.read_text() == "feature/new-branch"

    @patch("dimcause.utils.state.get_agent_dir")
    def test_clear_pending_merge(self, mock_agent_dir):
        """测试清除待合并"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            mock_agent_dir.return_value = agent_dir

            # 创建文件
            pending_file = agent_dir / "pending_merge.txt"
            pending_file.write_text("test")

            from dimcause.utils.state import clear_pending_merge

            clear_pending_merge()

            assert not pending_file.exists()


class TestOrphanJobs:
    """孤儿任务测试"""

    @patch("dimcause.utils.state.get_logs_dir")
    def test_check_orphan_jobs_empty(self, mock_logs_dir):
        """测试检查空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_logs_dir.return_value = Path(tmpdir)

            from dimcause.utils.state import check_orphan_jobs

            result = check_orphan_jobs()

            assert result == []

    @patch("dimcause.utils.state.get_logs_dir")
    def test_check_orphan_jobs_with_orphan(self, mock_logs_dir):
        """测试检查有孤儿任务"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            mock_logs_dir.return_value = logs_dir

            # 创建目录结构
            today = datetime.now()
            year_dir = logs_dir / today.strftime("%Y")
            day_dir = year_dir / today.strftime("%m-%d")
            job_dir = day_dir / "jobs" / "test-job"
            job_dir.mkdir(parents=True)

            # 创建 job-start.md（没有 job-end.md）
            (job_dir / "job-start.md").write_text("# Job Start")

            from dimcause.utils.state import check_orphan_jobs

            result = check_orphan_jobs(days=1)

            assert len(result) >= 1
            assert result[0]["id"] == "test-job"


class TestActiveJob:
    """活跃任务测试"""

    @patch("dimcause.utils.state.get_agent_dir")
    @patch("dimcause.utils.state.check_orphan_jobs")
    def test_get_active_job_from_file(self, mock_orphans, mock_agent_dir):
        """测试 get_active_job 使用 check_orphan_jobs 返回结果"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            mock_agent_dir.return_value = agent_dir
            mock_orphans.return_value = [
                {"id": "current-job", "path": Path(tmpdir), "start_time": 0}
            ]

            from dimcause.utils.state import get_active_job

            result = get_active_job()

            assert result is not None
            assert result[0] == "current-job"

    @patch("dimcause.utils.state.get_agent_dir")
    def test_record_job_start(self, mock_agent_dir):
        """record_job_start 在最小环境下可安全调用"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent_dir.return_value = Path(tmpdir)

            from dimcause.utils.state import record_job_start

            record_job_start("new-job")

    @patch("dimcause.utils.state.get_agent_dir")
    def test_record_job_end(self, mock_agent_dir):
        """record_job_end 在最小环境下可安全调用"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            mock_agent_dir.return_value = agent_dir

            from dimcause.utils.state import record_job_end

            record_job_end()


class TestTodayDir:
    """今日目录测试"""

    @patch("dimcause.utils.state.get_config")
    @patch("dimcause.utils.state.get_logs_dir")
    def test_get_today_dir(self, mock_logs_dir, mock_config):
        """测试获取今日目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_logs_dir.return_value = Path(tmpdir)

            mock_cfg = MagicMock()
            mock_cfg.timezone = "Asia/Shanghai"
            mock_config.return_value = mock_cfg

            from dimcause.utils.state import get_today_dir

            result = get_today_dir()

            assert isinstance(result, Path)

    @patch("dimcause.utils.state.get_today_dir")
    def test_ensure_today_dir(self, mock_today_dir):
        """测试确保今日目录存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            today_path = Path(tmpdir) / "2026" / "01-19"
            mock_today_dir.return_value = today_path

            from dimcause.utils.state import ensure_today_dir

            result = ensure_today_dir()

            assert result.exists()


class TestGraphStoreFull:
    """GraphStore 完整测试"""

    def test_graph_save_load(self):
        """测试图保存和加载"""
        from dimcause.core.models import Entity
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = f"{tmpdir}/graph.pkl"

            store = GraphStore(persist_path=persist_path)

            if store._graph is None:
                pytest.skip("networkx not available")

            # 添加数据
            store.add_entity(Entity(name="test.py", type="file"))

            # 保存
            store.save()

            # 验证文件存在
            assert os.path.exists(persist_path)

    def test_graph_add_multiple_entities(self):
        """测试添加多个实体"""
        from dimcause.core.models import Entity
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            for i in range(5):
                store.add_entity(Entity(name=f"file_{i}.py", type="file"))

            stats = store.stats()
            assert stats["nodes"] >= 5

    def test_graph_find_related_empty(self):
        """测试查找空图的关联"""
        from dimcause.storage.graph_store import GraphStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(persist_path=f"{tmpdir}/graph.pkl")

            if store._graph is None:
                pytest.skip("networkx not available")

            result = store.find_related("nonexistent")

            assert result == []


class TestSearchEngineMore:
    """SearchEngine 更多测试"""

    def test_search_mode_text(self):
        """测试文本搜索模式"""
        from dimcause.core.models import Event, EventType
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)

            event = Event(
                id="evt_1",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="使用 FastAPI",
                content="决定使用 FastAPI 框架",
            )
            store.save(event)

            engine = SearchEngine(markdown_store=store, vector_store=None)

            results = engine.search("FastAPI", mode="text", top_k=5)

            assert isinstance(results, list)

    def test_search_mode_hybrid(self):
        """测试混合搜索模式"""
        from dimcause.search.engine import SearchEngine
        from dimcause.storage.markdown_store import MarkdownStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = MarkdownStore(base_dir=tmpdir)
            engine = SearchEngine(markdown_store=store, vector_store=None)

            results = engine.search("test", mode="hybrid")

            assert isinstance(results, list)


class TestASTAnalyzerMore:
    """AST 分析器更多测试"""

    def test_detect_language_python(self):
        """测试检测 Python 语言"""
        from dimcause.extractors.ast_analyzer import detect_language

        assert detect_language("main.py") == "python"
        assert detect_language("src/utils/helpers.py") == "python"

    def test_detect_language_javascript(self):
        """测试检测 JavaScript 语言"""
        from dimcause.extractors.ast_analyzer import detect_language

        assert detect_language("app.js") == "javascript"
        assert detect_language("component.jsx") == "javascript"

    def test_detect_language_typescript(self):
        """测试检测 TypeScript 语言"""
        from dimcause.extractors.ast_analyzer import detect_language

        assert detect_language("main.ts") == "typescript"
        assert detect_language("component.tsx") == "typescript"

    def test_detect_language_unknown(self):
        """测试检测未知语言"""
        from dimcause.extractors.ast_analyzer import detect_language

        assert detect_language("data.xyz") == "unknown"
