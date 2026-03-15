"""
Git 工具模块测试
"""

import subprocess
import tempfile
from pathlib import Path

import pytest


class TestGitUtils:
    """Git 工具测试"""

    @pytest.fixture
    def temp_git_repo(self):
        """创建临时 Git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            # 初始化 Git 仓库
            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            yield repo_dir

    def test_run_git(self, temp_git_repo, monkeypatch):
        """测试运行 Git 命令"""
        from dimcause.utils.git import run_git

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        code, out, err = run_git("status", cwd=temp_git_repo)
        assert code == 0
        assert "nothing to commit" in out or "working tree clean" in out

    def test_run_git_error(self, temp_git_repo, monkeypatch):
        """测试 Git 命令错误"""
        from dimcause.utils.git import run_git

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 无效命令
        code, out, err = run_git("invalid-command", cwd=temp_git_repo)
        assert code != 0

    def test_run_git_exception(self, monkeypatch):
        """测试 Git 命令异常"""
        from dimcause.utils.git import run_git

        # Mock subprocess to raise exception
        def raise_error(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr("subprocess.run", raise_error)

        code, out, err = run_git("status")
        assert code == 1
        assert "not found" in err

    def test_get_current_branch(self, temp_git_repo, monkeypatch):
        """测试获取当前分支"""
        from dimcause.utils.git import get_current_branch

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 默认分支可能是 main 或 master
        branch = get_current_branch()
        assert branch in ["main", "master"]

    def test_has_changes(self, temp_git_repo, monkeypatch):
        """测试检测更改"""
        from dimcause.utils.git import get_status, has_changes

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 初始状态无更改
        assert has_changes() is False

        # 添加新文件
        (temp_git_repo / "new_file.txt").write_text("test")
        assert has_changes() is True

        # 检查状态
        status = get_status()
        assert len(status) > 0

    def test_add_and_commit(self, temp_git_repo, monkeypatch):
        """测试添加和提交"""
        from dimcause.utils.git import add_all, commit, has_changes

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 创建新文件
        (temp_git_repo / "test.txt").write_text("test content")
        assert has_changes() is True

        # 添加并提交
        add_all()
        result = commit("test commit")
        assert result is True

        # 提交后无更改
        assert has_changes() is False

    def test_commit_no_changes(self, temp_git_repo, monkeypatch):
        """无更改时提交失败"""
        from dimcause.utils.git import commit

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 无更改时提交
        result = commit("empty commit")
        assert result is False

    def test_create_and_checkout_branch(self, temp_git_repo, monkeypatch):
        """测试创建和切换分支"""
        from dimcause.utils.git import checkout, create_branch, get_current_branch

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        original_branch = get_current_branch()

        # 创建新分支
        assert create_branch("test-branch") is True
        assert get_current_branch() == "test-branch"

        # 切回原分支
        assert checkout(original_branch) is True
        assert get_current_branch() == original_branch

    def test_push_no_remote(self, temp_git_repo, monkeypatch):
        """无远程时推送失败"""
        from dimcause.utils.git import push

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 没有远程仓库，推送应该失败
        result = push("main")
        assert result is False

    def test_push_with_branch(self, temp_git_repo, monkeypatch):
        """推送指定分支"""
        from dimcause.utils.git import get_current_branch, push

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 使用当前分支
        branch = get_current_branch()
        result = push(branch)
        # 没有远程，应该失败
        assert result is False

    def test_checkout_nonexistent(self, temp_git_repo, monkeypatch):
        """切换到不存在的分支"""
        from dimcause.utils.git import checkout

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        result = checkout("nonexistent-branch")
        assert result is False


class TestGitCommitFlow:
    """git_commit_flow 测试"""

    @pytest.fixture
    def temp_git_repo(self):
        """创建临时 Git 仓库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            # 创建 .agent 目录
            agent_dir = repo_dir / ".agent"
            agent_dir.mkdir()

            yield repo_dir

    def test_git_commit_flow_no_changes(self, temp_git_repo, monkeypatch):
        """无更改时的流程"""
        from dimcause.utils.git import git_commit_flow

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 无更改，应该直接返回
        git_commit_flow(interactive=False)
        # 不抛出异常即成功

    def test_git_commit_flow_non_interactive(self, temp_git_repo, monkeypatch):
        """非交互模式"""
        from dimcause.utils.git import git_commit_flow

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 创建更改
        (temp_git_repo / "new.txt").write_text("content")

        # 非交互模式：直接快速提交
        git_commit_flow(interactive=False)

        # 验证已提交
        from dimcause.utils.git import has_changes

        assert has_changes() is False


class TestQuickCommit:
    """_quick_commit 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            yield repo_dir

    def test_quick_commit_with_changes(self, temp_git_repo, monkeypatch):
        """快速提交有更改"""
        from rich.console import Console

        from dimcause.utils.git import _quick_commit, has_changes

        monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: temp_git_repo)

        # 创建更改
        (temp_git_repo / "new.txt").write_text("content")

        console = Console()
        _quick_commit(console, "main", "2026-01-17")

        # 验证已提交
        assert has_changes() is False


class TestSafeCommit:
    """_safe_commit 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            # 创建 .agent 目录
            agent_dir = repo_dir / ".agent"
            agent_dir.mkdir()

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)
            monkeypatch.setattr("dimcause.utils.state.get_root_dir", lambda: repo_dir)
            monkeypatch.setattr("dimcause.utils.state.get_agent_dir", lambda: agent_dir)

            yield repo_dir

    def test_safe_commit_creates_branch(self, temp_git_repo, monkeypatch):
        """安全提交创建分支"""
        from rich.console import Console

        from dimcause.utils.git import _safe_commit, get_current_branch

        # 创建更改
        (temp_git_repo / "new.txt").write_text("content")

        console = Console()
        _safe_commit(console, "main", "daily/2026-01-17", "2026-01-17")

        # 验证切回主分支
        assert get_current_branch() == "main"


class TestPushWithoutBranch:
    """push 无分支参数测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_push_default_branch(self, temp_git_repo):
        """push 使用当前分支"""
        from dimcause.utils.git import push

        # 没有远程，会失败但不抛出异常
        result = push()
        assert result is False  # 没有远程


class TestCreateBranch:
    """create_branch 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_create_branch_success(self, temp_git_repo):
        """创建分支成功"""
        from dimcause.utils.git import create_branch, get_current_branch

        result = create_branch("feature-test")
        assert result is True
        assert get_current_branch() == "feature-test"


class TestGitCheckout:
    """checkout 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            # 创建初始提交
            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            # 创建另一个分支
            subprocess.run(["git", "branch", "feature"], cwd=repo_dir, capture_output=True)

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_checkout_success(self, temp_git_repo):
        """切换分支成功"""
        from dimcause.utils.git import checkout, get_current_branch

        result = checkout("feature")
        assert result is True
        assert get_current_branch() == "feature"

    def test_checkout_nonexistent(self, temp_git_repo):
        """切换不存在的分支"""
        from dimcause.utils.git import checkout

        result = checkout("nonexistent-branch")
        assert result is False


class TestGitHasChanges:
    """has_changes 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_no_changes(self, temp_git_repo):
        """无更改"""
        from dimcause.utils.git import has_changes

        assert has_changes() is False

    def test_with_changes(self, temp_git_repo):
        """有更改"""
        from dimcause.utils.git import has_changes

        (temp_git_repo / "newfile.txt").write_text("new content")

        assert has_changes() is True


class TestGitQuickCommit:
    """_quick_commit 测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_quick_commit(self, temp_git_repo):
        """快速提交"""
        from rich.console import Console

        from dimcause.utils.git import _quick_commit

        console = Console(force_terminal=True)

        # 创建新文件
        (temp_git_repo / "new.txt").write_text("new content")

        # 执行 quick commit
        _quick_commit(console, "main", "2026-01-17")

        # 应该已提交 (不崩溃即可)


class TestRunGit:
    """run_git 函数测试"""

    @pytest.fixture
    def temp_git_repo(self, monkeypatch):
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir)

            subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True
            )

            (repo_dir / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True
            )

            monkeypatch.setattr("dimcause.utils.git.get_root_dir", lambda: repo_dir)

            yield repo_dir

    def test_run_git_status(self, temp_git_repo):
        """运行 git status"""
        from dimcause.utils.git import run_git

        code, stdout, stderr = run_git("status")
        assert code == 0

    def test_run_git_log(self, temp_git_repo):
        """运行 git log"""
        from dimcause.utils.git import run_git

        code, stdout, stderr = run_git("log", "--oneline", "-n", "1")
        assert code == 0
        assert "Initial" in stdout
