"""
上下文加载器测试
"""

from datetime import datetime
from pathlib import Path

import pytest

from dimcause.core.context import (
    TODO_PATTERNS,
    Context,
    IndexEntry,
    extract_todos_from_file,
    find_recent_end_files,
    load_context,
    parse_index_table,
)


class TestIndexEntry:
    """IndexEntry 测试"""

    def test_create_entry(self):
        """创建条目"""
        entry = IndexEntry(
            date="2026-01-17",
            job="fix-bug",
            status="done",
            summary="Fixed a critical bug",
            tags="bugfix",
            path="2026/01-17/end.md",
        )
        assert entry.date == "2026-01-17"
        assert entry.job == "fix-bug"
        assert entry.status == "done"

    def test_default_path(self):
        """默认路径为空"""
        entry = IndexEntry(
            date="2026-01-17",
            job="test",
            status="done",
            summary="",
            tags="",
        )
        assert entry.path == ""


class TestContext:
    """Context 测试"""

    def test_empty_context(self):
        """空上下文"""
        ctx = Context()
        assert ctx.pending_merge is None
        assert ctx.recent_entries == []
        assert ctx.todos == []
        assert ctx.orphan_jobs == []

    def test_to_rich_empty(self):
        """空上下文生成 Rich 输出"""
        ctx = Context()
        output = ctx.to_rich()
        assert isinstance(output, str)

    def test_to_rich_with_data(self):
        """有数据时生成 Rich 输出"""
        ctx = Context(
            pending_merge="feature/test",
            orphan_jobs=["job-1", "job-2"],
            recent_entries=[
                IndexEntry(
                    date="2026-01-17",
                    job="test",
                    status="done",
                    summary="Test summary",
                    tags="test",
                ),
            ],
            todos=["Todo item 1", "Todo item 2"],
        )
        output = ctx.to_rich()
        assert "feature/test" in output
        assert "job-1" in output
        assert "test" in output
        assert "Todo item 1" in output


class TestParseIndexTable:
    """parse_index_table 测试"""

    def test_parse_valid_table(self, tmp_path):
        """解析有效的表格"""
        index_file = tmp_path / "INDEX.md"
        index_file.write_text("""# Index

| Date | Job | Status | Summary | Tags |
|------|-----|--------|---------|------|
| **2026-01-17** | [daily](2026/01-17/end.md) | done | Test summary | test |
| **2026-01-16** | [task](2026/01-16/end.md) | done | Another task | work |
""")

        entries = parse_index_table(index_file)
        assert len(entries) == 2
        assert entries[0].date == "2026-01-17"
        assert entries[0].job == "daily"
        assert entries[0].status == "done"
        assert entries[1].date == "2026-01-16"
        assert entries[1].job == "task"

    def test_parse_nonexistent_file(self, tmp_path):
        """不存在的文件返回空列表"""
        entries = parse_index_table(tmp_path / "nonexistent.md")
        assert entries == []

    def test_parse_empty_file(self, tmp_path):
        """空文件返回空列表"""
        index_file = tmp_path / "INDEX.md"
        index_file.write_text("")
        entries = parse_index_table(index_file)
        assert entries == []

    def test_parse_no_table(self, tmp_path):
        """无表格内容"""
        index_file = tmp_path / "INDEX.md"
        index_file.write_text("# Just a heading\n\nSome text")
        entries = parse_index_table(index_file)
        assert entries == []


class TestExtractTodosFromFile:
    """extract_todos_from_file 测试"""

    def test_extract_todos_bracket_format(self, tmp_path):
        """提取 [待办] 格式"""
        file = tmp_path / "end.md"
        file.write_text("""# End

## [待办]
- 完成功能 A
- 修复 Bug B
- 优化性能

## Notes
Something else
""")

        todos = extract_todos_from_file(file)
        assert "完成功能 A" in todos
        assert "修复 Bug B" in todos
        assert "优化性能" in todos

    def test_extract_todos_section_format(self, tmp_path):
        """提取 ## 待办 格式"""
        file = tmp_path / "end.md"
        file.write_text("""# End

## 待办
- Item 1
- Item 2

## Other
""")

        todos = extract_todos_from_file(file)
        assert "Item 1" in todos
        assert "Item 2" in todos

    def test_extract_todos_next_steps(self, tmp_path):
        """提取 [明日切入点] 格式"""
        file = tmp_path / "end.md"
        file.write_text("""# End

## [明日切入点]
- Start with feature X
- Review PR

## Done
""")

        todos = extract_todos_from_file(file)
        assert "Start with feature X" in todos
        assert "Review PR" in todos

    def test_extract_todos_nonexistent(self, tmp_path):
        """不存在的文件返回空列表"""
        todos = extract_todos_from_file(tmp_path / "nonexistent.md")
        assert todos == []

    def test_extract_todos_no_todos(self, tmp_path):
        """没有待办时返回空列表"""
        file = tmp_path / "end.md"
        file.write_text("""# End

## Completed
- Done item 1

## Notes
Nothing here
""")

        todos = extract_todos_from_file(file)
        assert todos == []

    def test_extract_todos_dedup(self, tmp_path):
        """去重"""
        file = tmp_path / "end.md"
        file.write_text("""# End

## [待办]
- Same todo

## [遗留]
- Same todo
""")

        todos = extract_todos_from_file(file)
        assert todos.count("Same todo") == 1


class TestFindRecentEndFiles:
    """find_recent_end_files 测试"""

    def test_find_files(self):
        """查找文件"""
        # 由于使用全局路径，只能验证返回类型
        files = find_recent_end_files(limit=3)
        assert isinstance(files, list)
        for f in files:
            assert isinstance(f, Path)

    def test_limit_parameter(self):
        """限制参数"""
        files = find_recent_end_files(limit=1)
        assert len(files) <= 1


class TestLoadContext:
    """load_context 测试"""

    def test_load_context_structure(self):
        """验证返回结构"""
        ctx = load_context()
        assert isinstance(ctx, Context)
        assert isinstance(ctx.recent_entries, list)
        assert isinstance(ctx.todos, list)
        assert isinstance(ctx.orphan_jobs, list)


class TestTodoPatterns:
    """TODO_PATTERNS 测试"""

    def test_patterns_match(self):
        """验证模式能匹配"""
        import re

        test_cases = [
            "[待办]",
            "[TODO]",
            "[遗留]",
            "[遗留问题]",
            "[明日切入点]",
            "[Next Steps]",
            "[下一步]",
            "## 待办",
            "## TODO",
            "## 遗留",
            "## 明日",
            "## ⏭️",
        ]

        for test in test_cases:
            matched = False
            for pattern in TODO_PATTERNS:
                if re.search(pattern, test, re.IGNORECASE):
                    matched = True
                    break
            assert matched, f"Pattern should match: {test}"


class TestPrintContext:
    """print_context 测试"""

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
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)

            yield root_dir, logs_dir, agent_dir

    def test_print_context_runs(self, temp_project, capsys):
        """print_context 正常运行"""
        from dimcause.core.context import print_context

        ctx = print_context()

        # 验证有输出
        captured = capsys.readouterr()
        assert "上下文恢复" in captured.out or "Context" in captured.out

        # 验证返回 Context 对象
        assert ctx is not None


class TestContextWithData:
    """带数据的上下文测试"""

    @pytest.fixture
    def temp_project_with_data(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            agent_dir = root_dir / ".agent"
            logs_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)

            # 创建 INDEX.md
            index_content = """# Index

| Date | Job | Status | Summary | Tags |
|------|-----|--------|---------|------|
| **2026-01-17** | [test](2026/01-17/end.md) | done | Test | test |
"""
            (logs_dir / "INDEX.md").write_text(index_content)

            # 创建 end.md 文件带有 TODO
            day_dir = logs_dir / "2026" / "01-17"
            day_dir.mkdir(parents=True)
            (day_dir / "end.md").write_text("""---
type: daily-end
date: 2026-01-17
---

## [待办]
- 完成测试 A
- 优化代码 B
""")

            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: root_dir)
            monkeypatch.setattr("dimcause.utils.state.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)
            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)

            yield root_dir, logs_dir, agent_dir

    def test_load_context_with_todos(self, temp_project_with_data):
        """加载带 TODO 的上下文"""
        ctx = load_context()

        # 应该有 TODO
        assert len(ctx.todos) >= 1
        assert any("测试" in todo or "优化" in todo for todo in ctx.todos)

    def test_load_context_with_index(self, temp_project_with_data):
        """加载带 INDEX 的上下文"""
        ctx = load_context()

        # 应该有近期条目
        assert len(ctx.recent_entries) >= 1

    def test_print_context_with_data(self, temp_project_with_data, capsys):
        """print_context 有数据时的输出"""
        from dimcause.core.context import print_context

        ctx = print_context()

        captured = capsys.readouterr()
        # 验证输出包含上下文信息
        assert "上下文恢复" in captured.out
        assert ctx is not None

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)

            yield root_dir, logs_dir

    def test_find_empty(self, temp_project):
        """空目录"""
        from dimcause.core.context import find_recent_end_files

        files = find_recent_end_files()
        assert isinstance(files, list)
        assert len(files) == 0

    def test_find_with_files(self, temp_project):
        """有文件"""
        from dimcause.core.context import find_recent_end_files

        root_dir, logs_dir = temp_project

        # 创建一个 end.md 文件
        year = datetime.now().strftime("%Y")
        day = datetime.now().strftime("%m-%d")
        day_dir = logs_dir / year / day
        day_dir.mkdir(parents=True)
        (day_dir / "end.md").write_text("---\ntype: daily-end\n---")

        files = find_recent_end_files()
        assert len(files) >= 1


class TestParseIndexTableFailure:
    """parse_index_table 文件读取失败"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)

            yield root_dir, logs_dir

    def test_parse_nonexistent_file(self, temp_project):
        """解析不存在的文件"""
        from dimcause.core.context import parse_index_table

        root_dir, logs_dir = temp_project

        # 传入不存在的文件路径
        entries = parse_index_table(logs_dir / "nonexistent.md")
        assert entries == []


class TestExtractTodos:
    """提取 todos 测试"""

    @pytest.fixture
    def temp_project(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root_dir = Path(tmpdir)
            logs_dir = root_dir / "docs" / "logs"
            logs_dir.mkdir(parents=True)

            monkeypatch.setattr("dimcause.core.context.get_logs_dir", lambda: logs_dir)
            monkeypatch.setattr("dimcause.core.context.get_root_dir", lambda: root_dir)

            yield root_dir, logs_dir

    def test_extract_todos_from_file(self, temp_project):
        """从文件提取 todos"""
        from dimcause.core.context import extract_todos_from_file

        root_dir, logs_dir = temp_project

        # 创建带待办的日志
        year = datetime.now().strftime("%Y")
        day = datetime.now().strftime("%m-%d")
        day_dir = logs_dir / year / day
        day_dir.mkdir(parents=True)

        (day_dir / "end.md").write_text("""---
type: daily-end
---

## [待办]
- Task 1
- Task 2
""")

        todos = extract_todos_from_file(day_dir / "end.md")
        assert isinstance(todos, list)
