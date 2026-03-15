"""
Git 工具函数

封装常用的 Git 操作
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from dimcause.utils.state import get_root_dir, set_pending_merge


def run_git(*args, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """
    运行 Git 命令

    Returns:
        (return_code, stdout, stderr)
    """
    if cwd is None:
        cwd = get_root_dir()

    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def get_current_branch() -> str:
    """获取当前分支名"""
    code, out, _ = run_git("rev-parse", "--abbrev-ref", "HEAD")
    return out if code == 0 else "unknown"


def get_status() -> list[str]:
    """获取 Git 状态 (修改的文件列表)"""
    code, out, _ = run_git("status", "--short")
    if code == 0 and out:
        return out.split("\n")
    return []


def has_changes() -> bool:
    """检查是否有未提交的更改"""
    return len(get_status()) > 0


def add_all():
    """添加所有更改"""
    run_git("add", ".")


def commit(message: str) -> bool:
    """
    提交更改

    Returns:
        是否成功
    """
    code, _, _ = run_git("commit", "-m", message)
    return code == 0


def push(branch: Optional[str] = None) -> bool:
    """
    推送到远程

    Returns:
        是否成功
    """
    if branch is None:
        branch = get_current_branch()

    code, _, _ = run_git("push", "origin", branch)
    return code == 0


def create_branch(branch_name: str) -> bool:
    """创建新分支"""
    code, _, _ = run_git("checkout", "-b", branch_name)
    return code == 0


def checkout(branch_name: str) -> bool:
    """切换分支"""
    code, _, _ = run_git("checkout", branch_name)
    return code == 0


# === New Class: GitRepo (Added to fix git_importer.py) ===


class GitRepo:
    """
    Git Repository Object Wrapper
    """

    def __init__(self, path: str = "."):
        self.path = Path(path).absolute()
        if not (self.path / ".git").exists():
            # Try to resolve if it's inside a repo
            code, out, _ = run_git("rev-parse", "--show-toplevel", cwd=self.path)
            if code == 0:
                self.path = Path(out)
            else:
                pass  # Allow initializing on non-repo, methods might fail

    def get_file_history(self, file_path: str, max_count: int = 10) -> list:
        """Wrapper around mal.extractors.git_history.get_file_history"""
        # Circular import avoidance: Import inside method
        try:
            # Check if mal.extractors.git_history exists (it should)
            from dimcause.extractors.git_history import get_file_history

            return get_file_history(file_path, max_count, cwd=self.path)
        except ImportError:
            return []

    def get_diff(self, commit_hash: str) -> str:
        """Get diff for a specific commit"""
        code, out, _ = run_git("show", commit_hash, cwd=self.path)
        return out if code == 0 else ""

    def get_diff_range(self, base_ref: str, target_ref: str = "HEAD") -> str:
        """Get diff between two revisions."""
        code, out, _ = run_git(
            "diff",
            "--no-ext-diff",
            "--unified=0",
            f"{base_ref}..{target_ref}",
            cwd=self.path,
        )
        return out if code == 0 else ""

    def get_working_tree_diff(self) -> str:
        """Get working tree diff against HEAD."""
        code, out, _ = run_git(
            "diff",
            "--no-ext-diff",
            "--unified=0",
            "HEAD",
            cwd=self.path,
        )
        return out if code == 0 else ""

    def get_head_commit(self) -> str:
        """Get current HEAD commit hash"""
        code, out, _ = run_git("rev-parse", "HEAD", cwd=self.path)
        return out.strip() if code == 0 else ""

    def get_changed_files(self, base_ref: str, target_ref: str = "HEAD") -> list[str]:
        """Get changed files between two revisions."""
        code, out, _ = run_git("diff", "--name-only", f"{base_ref}..{target_ref}", cwd=self.path)
        if code == 0 and out:
            return [line for line in out.split("\n") if line]
        return []

    def get_commit_files(self, commit_hash: str) -> list[str]:
        """Get files changed by a specific commit."""
        code, out, _ = run_git(
            "show", "--pretty=format:", "--name-only", commit_hash, cwd=self.path
        )
        if code == 0 and out:
            return [line for line in out.split("\n") if line]
        return []

    def get_status(self) -> list[str]:
        """Get git working tree status lines for this repo."""
        code, out, _ = run_git("status", "--short", cwd=self.path)
        if code == 0 and out:
            return out.split("\n")
        return []

    def get_commit_info(self, commit_hash: str) -> dict:
        """Get basic info about a commit"""
        code, out, _ = run_git("show", "-s", "--format=%an|%s", commit_hash, cwd=self.path)
        if code != 0 or not out:
            return {"author": "unknown", "message": "unknown"}

        parts = out.split("|", 1)
        return {"author": parts[0], "message": parts[1] if len(parts) > 1 else ""}


def git_commit_flow(interactive: bool = True):
    """
    收工时的 Git 提交流程

    Args:
        interactive: 是否交互式选择
    """
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    current_branch = get_current_branch()
    today_date = datetime.now().strftime("%Y-%m-%d")
    daily_branch = f"daily/{today_date}"

    # 检查是否有更改
    if not has_changes():
        console.print("[dim]没有需要提交的更改[/]")
        return

    # 显示状态
    console.print(f"\n[blue]当前分支: {current_branch}[/]")
    status = get_status()
    console.print(f"[dim]  {len(status)} 个文件有更改[/]")

    if not interactive:
        # 非交互模式: 直接提交到当前分支
        _quick_commit(console, current_branch, today_date)
        return

    # 交互模式: 选择提交方式
    console.print("\n请选择提交方式:")
    console.print(f"  [1] 直接提交到当前分支 ({current_branch}) - 快速模式")
    console.print(f"  [2] 新建 {daily_branch} 分支并提交 - 安全模式")
    console.print("  [3] 跳过 Git 操作")

    choice = Prompt.ask("选项", choices=["1", "2", "3"], default="1")

    if choice == "1":
        _quick_commit(console, current_branch, today_date)
    elif choice == "2":
        _safe_commit(console, current_branch, daily_branch, today_date)
    else:
        console.print("[dim]跳过 Git 操作[/]")


def _quick_commit(console, branch: str, date: str):
    """快速提交到当前分支"""
    add_all()

    if commit(f"chore(daily): end of day wrap-up {date}"):
        console.print("[green]✅ 已提交[/]")

        if push(branch):
            console.print(f"[green]✅ 已推送到 {branch}[/]")
        else:
            console.print("[yellow]⚠️ 推送失败，请稍后手动执行 git push[/]")
    else:
        console.print("[yellow]没有需要提交的更改[/]")


def _safe_commit(console, main_branch: str, daily_branch: str, date: str):
    """安全模式: 新建分支提交"""
    # 创建新分支
    if create_branch(daily_branch):
        console.print(f"[green]✅ 已创建分支 {daily_branch}[/]")
    else:
        console.print("[red]❌ 创建分支失败[/]")
        return

    # 提交
    add_all()
    commit(f"chore(daily): end of day wrap-up {date}")

    # 推送
    if push(daily_branch):
        console.print(f"[green]✅ 已推送到 {daily_branch}[/]")
    else:
        console.print("[yellow]⚠️ 推送失败[/]")

    # 切回主分支
    if checkout(main_branch):
        console.print(f"[green]✅ 已切回 {main_branch}[/]")

    # 记录待合并
    set_pending_merge(daily_branch)
    console.print("[blue]📝 已记录待合并分支，明天开工时会提醒[/]")
