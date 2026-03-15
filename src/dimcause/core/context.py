"""
上下文加载器 (Phase 1 的依赖)

核心功能:
1. 读取 INDEX.md 提取近期记录
2. 读取 end.md 提取 Task/遗留
3. 生成开工建议
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dimcause.utils.state import get_logs_dir, get_root_dir  # noqa: F401

# 关键字模式，用于匹配 Task 相关的标题
TODO_PATTERNS = [
    r"\[待办\]",
    r"\[TODO\]",
    r"\[遗留\]",
    r"\[遗留问题\]",
    r"\[明日切入点\]",
    r"\[Next Steps?\]",
    r"\[下一步\]",
    r"##\s*待办",
    r"##\s*TODO",
    r"##\s*遗留",
    r"##\s*明日",
    r"##\s*⏭️",
]


@dataclass
class IndexEntry:
    """INDEX.md 中的一条记录"""

    date: str
    job: str
    status: str
    summary: str
    tags: str
    path: str = ""


@dataclass
class Context:
    """加载的上下文"""

    pending_merge: Optional[str] = None
    recent_entries: list[IndexEntry] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    orphan_jobs: list[str] = field(default_factory=list)

    def to_rich(self) -> str:
        """生成 Rich 格式的输出"""
        lines = []

        if self.pending_merge:
            lines.append(f"[yellow]⚠️ 待合并分支: {self.pending_merge}[/]")

        if self.orphan_jobs:
            lines.append(f"[yellow]⚠️ 未闭合任务: {', '.join(self.orphan_jobs)}[/]")

        if self.recent_entries:
            lines.append("\n[blue]📊 近期记录:[/]")
            for entry in self.recent_entries[:5]:
                icon = "✅" if entry.status == "done" else "🔄"
                lines.append(f"  {icon} [{entry.date}] {entry.job}")

        if self.todos:
            lines.append("\n[green]📝 待办事项:[/]")
            for i, todo in enumerate(self.todos[:5], 1):
                lines.append(f"  {i}. {todo[:80]}")

        return "\n".join(lines)


def parse_index_table(filepath: Path) -> list[IndexEntry]:
    """解析 INDEX.md 中的表格"""
    entries = []

    if not filepath.exists():
        return entries

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return entries

    lines = content.split("\n")
    in_table = False
    current_date = ""

    for line in lines:
        line = line.strip()

        # 检测表格开始 (header row)
        if "| Date" in line or "| Job" in line:
            in_table = True
            continue

        # Skip separator line
        if line.startswith("|") and "---" in line:
            continue

        # 解析表格行
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p is not None]  # Keep empty strings
            # Remove leading/trailing empty from split
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]

            if len(parts) >= 2:
                # First column is date (may be empty for continuation rows)
                raw_date = parts[0].replace("**", "").strip()
                if raw_date:
                    current_date = raw_date

                # Second column is job
                job_raw = parts[1] if len(parts) > 1 else ""
                # 提取链接中的 job 名
                link_match = re.search(r"\[([^\]]+)\]", job_raw)
                if link_match:
                    job = link_match.group(1)
                else:
                    job = job_raw

                entries.append(
                    IndexEntry(
                        date=current_date,
                        job=job,
                        status=parts[2] if len(parts) > 2 else "",
                        summary=parts[3] if len(parts) > 3 else "",
                        tags=parts[4] if len(parts) > 4 else "",
                    )
                )

    return entries


def extract_todos_from_file(filepath: Path) -> list[str]:
    """从单个 end.md 文件中提取 Task 相关内容"""
    todos = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return todos

    for pattern in TODO_PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        for match in matches:
            start_pos = match.end()
            remaining = content[start_pos:]

            # 找到下一个 section
            next_section = re.search(r"\n##", remaining)
            if next_section:
                section_content = remaining[: next_section.start()]
            else:
                section_content = remaining[:500]

            # 提取列表项
            items = re.findall(r"^\s*[-*]\s*(.+)$", section_content, re.MULTILINE)
            for item in items:
                item = item.strip()
                if item and len(item) > 3 and item not in todos:
                    todos.append(item)

    return todos


def find_recent_end_files(limit: int = 3) -> list[Path]:
    """查找最近的 end.md 文件"""
    logs_dir = get_logs_dir()
    end_files = []

    # 查找所有 end.md
    for pattern in ["*/*/end.md", "*/*/jobs/*/end.md"]:
        matches = list(logs_dir.glob(pattern))
        end_files.extend(matches)

    # 按修改时间排序
    end_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return end_files[:limit]


def load_context() -> Context:
    """
    加载完整的上下文

    Returns:
        包含所有上下文信息的 Context 对象
    """
    from dimcause.utils.state import check_orphan_jobs, check_pending_merge

    ctx = Context()
    logs_dir = get_logs_dir()

    # 1. 检查待合并分支
    ctx.pending_merge = check_pending_merge()

    # 2. 检查 orphan jobs
    orphans = check_orphan_jobs(days=3)
    ctx.orphan_jobs = [o["id"] for o in orphans]

    # 3. 读取 INDEX.md
    index_file = logs_dir / "INDEX.md"
    ctx.recent_entries = parse_index_table(index_file)

    # 4. 提取 Tasks
    end_files = find_recent_end_files(limit=3)
    for filepath in end_files:
        todos = extract_todos_from_file(filepath)
        for todo in todos:
            if todo not in ctx.todos:
                ctx.todos.append(todo)

    return ctx


def print_context():
    """打印上下文到终端 (用于 CLI)"""
    ctx = load_context()

    print("=" * 60)
    print("📋 上下文恢复 (Context Loader)")
    print("=" * 60)

    if ctx.pending_merge:
        print(f"\n⚠️  待合并分支: {ctx.pending_merge}")
        print("    请执行: git merge {ctx.pending_merge}")

    if ctx.orphan_jobs:
        print(f"\n⚠️  未闭合任务: {', '.join(ctx.orphan_jobs)}")

    if ctx.recent_entries:
        print(f"\n📊 近期记录 ({len(ctx.recent_entries)} 条):")
        for entry in ctx.recent_entries[:5]:
            icon = "✅" if entry.status == "done" else "🔄"
            print(f"   {icon} [{entry.date}] {entry.job}")
            if entry.summary:
                print(f"      📝 {entry.summary[:60]}...")

    if ctx.todos:
        print(f"\n📝 待办事项 ({len(ctx.todos)} 条):")
        for i, todo in enumerate(ctx.todos[:5], 1):
            print(f"   {i}. {todo[:80]}")
    else:
        print("\n✅ 未发现明确的遗留待办")

    print("=" * 60)

    return ctx
