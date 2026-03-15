from datetime import datetime
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from dimcause.core.trace import TraceNode

console = Console()


class TraceView:
    """
    负责将 Trace 结果渲染为可视化树状结构 (使用 Rich)
    """

    def render_trace_tree(self, query: str, nodes: List[TraceNode]) -> None:
        """
        渲染追踪结果树

        Root: Query
          ├── 💎 Code Definitions
          │     └── Class: EventIndex (src/dimcause/core/event_index.py:25-127)
          ├── 🔗 Code References
          │     └── Imported by src/dimcause/cli.py (Line 390)
          ├── 📂 Files
          │     └── file.py (mtime)
          └── 🧠 Events
                └── [Type] Summary (date)
        """
        root = Tree(f"🔍 Trace: [bold cyan]{query}[/]")

        # 分组节点
        code_defs = [n for n in nodes if n.type == "code_definition"]
        code_refs = [n for n in nodes if n.type == "code_reference"]
        files = [n for n in nodes if n.type == "file"]
        events = [n for n in nodes if n.type not in ("file", "code_definition", "code_reference")]

        # 1. Code Definitions (优先级最高)
        if code_defs:
            defs_branch = root.add(f"💎 代码定义 ({len(code_defs)})", style="bold green")
            for d in code_defs:
                # Format: Class: EventIndex (src/.../file.py:25-127)
                label = Text()
                label.append(
                    f"{d.entity_type.capitalize() if d.entity_type else 'Code'}: ", style="yellow"
                )
                label.append(f"{d.entity_name or d.summary}", style="bold white")

                # 文件路径和行号
                if d.path:
                    line_range = f"{d.line_start}"
                    if d.line_end and d.line_end != d.line_start:
                        line_range += f"-{d.line_end}"
                    label.append(f"\n   📄 {d.path}:{line_range}", style="dim cyan")

                # Docstring (如果有)
                if d.docstring:
                    first_line = d.docstring.split("\n")[0].strip()
                    if first_line:
                        label.append(f"\n   💬 {first_line[:60]}...", style="dim italic")

                defs_branch.add(label)

        # 2. Code References
        if code_refs:
            refs_branch = root.add(f"🔗 代码引用 ({len(code_refs)})", style="bold blue")
            for r in code_refs:
                # Format: Imported by src/dimcause/cli.py (Line 390)
                label = Text()
                label.append("导入自: ", style="dim")
                label.append(f"{r.path}", style="cyan")
                if r.line_start:
                    label.append(f" (行 {r.line_start})", style="dim yellow")
                refs_branch.add(label)

        # 3. Files Branch (降级为后备)
        if files:
            files_branch = root.add(f"📂 其他文件 ({len(files)})", style="yellow")
            for f in files:
                mtime_str = datetime.fromtimestamp(f.timestamp).strftime("%Y-%m-%d %H:%M")
                path_str = f.path if f.path else f.id
                label = Text()
                label.append(path_str, style="bold")
                if f.line_start:
                    label.append(f":{f.line_start}", style="yellow")
                label.append(f" ({mtime_str})", style="dim")
                if f.summary:
                    label.append(f"\n   🔎 {f.summary}", style="dim white")
                files_branch.add(label)

        # 4. Events Branch
        if events:
            events_branch = root.add(f"🧠 相关事件 ({len(events)})", style="magenta")
            for e in events:
                time_str = datetime.fromtimestamp(e.timestamp).strftime("%Y-%m-%d")
                summary = e.summary.replace("\n", " ")[:60]  # Truncate summary

                # Format: [Type] Summary (Date)
                label = Text()
                label.append(f"[{e.type}] ", style="bold green")
                label.append(f"{summary} ", style="white")
                label.append(f"({time_str})", style="dim")

                events_branch.add(label)

        if not (code_defs or code_refs or files or events):
            root.add("[dim italic]未找到结果[/]")

        console.print(Panel(root, title="Trace 结果", border_style="blue"))
