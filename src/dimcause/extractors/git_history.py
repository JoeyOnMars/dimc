"""
Git History Extractor

Extracts file modification history for Causal Chain (mal why) feature.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dimcause.utils.git import run_git


@dataclass
class GitCommit:
    """Represents a single commit in file history"""

    hash: str
    date: str
    message: str
    author: str
    files_changed: int = 0


def get_file_history(
    file_path: str, max_count: int = 10, cwd: Optional[Path] = None
) -> List[GitCommit]:
    """
    Get Git history for a specific file.

    Args:
        file_path: Relative path to the file
        max_count: Maximum number of commits to retrieve
        cwd: Working directory (defaults to project root)

    Returns:
        List of GitCommit objects, ordered from newest to oldest

    Example:
        >>> history = get_file_history("src/mal/cli.py", max_count=5)
        >>> for commit in history:
        ...     print(f"{commit.date}: {commit.message}")
    """
    # Use --follow to track file renames
    # Format: hash|date|author|message
    code, out, err = run_git(
        "log",
        "--follow",
        f"--max-count={max_count}",
        "--format=%H|%ad|%an|%s",
        "--date=short",
        "--",
        file_path,
        cwd=cwd,
    )

    if code != 0 or not out:
        return []

    commits = []
    for line in out.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", maxsplit=3)
        if len(parts) != 4:
            continue

        hash_val, date, author, message = parts
        commits.append(GitCommit(hash=hash_val, date=date, message=message, author=author))

    return commits


def yield_file_history(file_path: str, max_count: int = 10, cwd: Optional[Path] = None):
    """
    Generator version of get_file_history.
    Yields GitCommit objects one by one to avoid OOM.

    Args:
        file_path: Relative path to the file
        max_count: Maximum number of commits to retrieve
        cwd: Working directory (defaults to project root)

    Yields:
        GitCommit objects
    """
    import subprocess

    from dimcause.utils.git import get_root_dir

    if cwd is None:
        cwd = get_root_dir()

    # Use --follow to track file renames
    # Format: hash|date|author|message
    cmd = [
        "git",
        "log",
        "--follow",
        f"--max-count={max_count}",
        "--format=%H|%ad|%an|%s",
        "--date=short",
        "--",
        file_path,
    ]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        if process.stdout:
            for line in process.stdout:
                if not line.strip():
                    continue

                parts = line.strip().split("|", maxsplit=3)
                if len(parts) != 4:
                    continue

                hash_val, date, author, message = parts
                yield GitCommit(hash=hash_val, date=date, message=message, author=author)

        process.wait()

    except Exception as e:
        print(f"Error streaming git history: {e}")


def get_file_creation_date(file_path: str, cwd: Optional[Path] = None) -> Optional[str]:
    """
    Get the date when a file was first created (added to Git).

    Args:
        file_path: Relative path to the file
        cwd: Working directory

    Returns:
        Date string in YYYY-MM-DD format, or None if not found
    """
    history = get_file_history(file_path, max_count=1000, cwd=cwd)
    if not history:
        return None

    # Last commit in history is the creation
    return history[-1].date


def get_recent_changes(
    file_path: str, since_date: Optional[str] = None, cwd: Optional[Path] = None
) -> List[GitCommit]:
    """
    Get recent changes to a file since a specific date.

    Args:
        file_path: Relative path to the file
        since_date: Get changes since this date (YYYY-MM-DD)
        cwd: Working directory

    Returns:
        List of commits
    """
    args = [
        "log",
        "--follow",
        "--format=%H|%ad|%an|%s",
        "--date=short",
    ]

    if since_date:
        args.append(f"--since={since_date}")

    args.extend(["--", file_path])

    code, out, err = run_git(*args, cwd=cwd)

    if code != 0 or not out:
        return []

    commits = []
    for line in out.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", maxsplit=3)
        if len(parts) != 4:
            continue

        hash_val, date, author, message = parts
        commits.append(GitCommit(hash=hash_val, date=date, message=message, author=author))

    return commits


def format_history_timeline(commits: List[GitCommit]) -> str:
    """
    Format commit history as a readable timeline.

    Args:
        commits: List of GitCommit objects

    Returns:
        Formatted string suitable for display
    """
    if not commits:
        return "No commit history found."

    lines = ["📅 Git History Timeline:", ""]
    for i, commit in enumerate(commits, 1):
        lines.append(f"{i}. [{commit.date}] {commit.message}")
        lines.append(f"   Commit: {commit.hash[:8]} by {commit.author}")
        lines.append("")

    return "\n".join(lines)


def get_file_at_commit(
    file_path: str, commit_hash: str, cwd: Optional[Path] = None
) -> Optional[str]:
    """
    Get file content at a specific commit.

    Args:
        file_path: Relative path to the file
        commit_hash: Git commit hash (full or short)
        cwd: Working directory

    Returns:
        File content as string, or None if not found
    """
    from dimcause.utils.git import run_git

    code, out, err = run_git("show", f"{commit_hash}:{file_path}", cwd=cwd)

    if code != 0:
        return None

    return out


def get_file_diff(
    file_path: str, commit1: str, commit2: str = "HEAD", cwd: Optional[Path] = None
) -> Optional[str]:
    """
    Get diff between two commits for a file.

    Args:
        file_path: Relative path to the file
        commit1: First commit hash (older)
        commit2: Second commit hash (newer, defaults to HEAD)
        cwd: Working directory

    Returns:
        Diff output as string, or None if error
    """
    from dimcause.utils.git import run_git

    code, out, err = run_git("diff", commit1, commit2, "--", file_path, cwd=cwd)

    if code != 0:
        return None

    return out


def get_file_snapshots(
    file_path: str, dates: List[str], cwd: Optional[Path] = None
) -> List[tuple[str, Optional[str]]]:
    """
    Get file content at multiple dates.

    Args:
        file_path: Relative path to the file
        dates: List of dates in YYYY-MM-DD format
        cwd: Working directory

    Returns:
        List of (date, content) tuples
    """
    from dimcause.utils.git import run_git

    snapshots = []

    for date in dates:
        # Get commit closest to this date
        code, out, err = run_git(
            "rev-list", "-1", f"--before={date}", "HEAD", "--", file_path, cwd=cwd
        )

        if code != 0 or not out:
            snapshots.append((date, None))
            continue

        commit_hash = out.strip()
        content = get_file_at_commit(file_path, commit_hash, cwd)
        snapshots.append((date, content))

    return snapshots
