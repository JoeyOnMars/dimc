import re
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.prompt import Prompt

from dimcause.extractors.data_collector import SessionData
from dimcause.utils.config import get_config


class ContextInjector:
    """
    负责从 Brain Artifacts, Logs, 和 Docs 中提取上下文，
    并注入到收工报告 (end.md) 中。
    """

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.config = get_config()
        self.brain_dir = self.config.brain_dir

    def scan_context(
        self, session_id: str, date_str: str, session_data: Optional[SessionData] = None
    ) -> Dict[str, str]:
        context = {
            "achievements": "",
            "tasks_status": "",
            "code_status": "",
            "legacy_issues": "",
            "session_objective": "",
        }

        # 0. Scan Active Session Logs (AG_Exports) -> Objective
        objective = ""
        if session_data and session_data.raw_chat_files:
            # Use collected raw chats from SessionData
            # Logic: Look for objective in the provided files.
            # Assuming first or all? Let's take the first one that has an objective.
            for p in session_data.raw_chat_files:
                obj = self._extract_user_objective(p)
                if obj:
                    objective = obj
                    break
        else:
            # Fallback to internal scan (Legacy/Interactive)
            objective = self._scan_ag_exports(session_id, date_str)

        # 0.5 Fallback: Extract objective from Claude Code JSONL markdown
        if not objective and session_data and session_data.claude_code_markdown:
            objective = self._extract_session_objective_from_jsonl_md(
                session_data.claude_code_markdown
            )

        if objective:
            context["session_objective"] = objective

        if not self.brain_dir:
            return context

        # 1. Scan task.md
        task_content = ""
        if session_data and "task.md" in session_data.brain_artifacts:
            task_content = session_data.brain_artifacts["task.md"]
        elif self.brain_dir:
            task_md = self.brain_dir / "task.md"
            if task_md.exists():
                task_content = task_md.read_text(encoding="utf-8")

        if task_content:
            context["achievements"] += self._extract_checked_items(task_content)
            context["tasks_status"] = self._extract_unchecked_items_table(task_content)

        # 2. Scan walkthrough.md
        walkthrough_content = ""
        if session_data and "walkthrough.md" in session_data.brain_artifacts:
            walkthrough_content = session_data.brain_artifacts["walkthrough.md"]
        elif self.brain_dir:
            walkthrough_md = self.brain_dir / "walkthrough.md"
            if walkthrough_md.exists():
                walkthrough_content = walkthrough_md.read_text(encoding="utf-8")

        if walkthrough_content:
            summary = self._extract_section_content(
                walkthrough_content, "Verification", "Validation", "Test"
            )
            if not summary:
                summary = "\n".join(
                    [line for line in walkthrough_content.splitlines()[:20] if line.strip()]
                )

            if summary:
                context["achievements"] += f"\n\n### 验证结果 (Walkthrough)\n{summary}"

        # 3. Scan implementation_plan.md / Plan Content
        plan_content = ""
        if session_data and "implementation_plan.md" in session_data.brain_artifacts:
            plan_content = session_data.brain_artifacts["implementation_plan.md"]
        elif self.brain_dir:
            plan_md = self.brain_dir / "implementation_plan.md"
            if plan_md.exists():
                plan_content = plan_md.read_text(encoding="utf-8")

        if plan_content:
            context["legacy_issues"] = self._extract_section_content(
                plan_content, "Legacy", "Known Issues", "Todo"
            )

        # 4. Scan STATUS.md (DataCollector doesn't collect this yet, keep verifying logic locally)
        status_md = self.root_dir / "docs/STATUS.md"
        if status_md.exists():
            content = status_md.read_text(encoding="utf-8")
            # 提取最后更新状态
            status_row = self._extract_table_row(content, "V6.1")
            if status_row:
                context["code_status"] = f"| 版本 | 内容 | 状态 |\n|---|---|---|\n{status_row}"

        # 5. Determine Next Session Guide (Auto Logic)
        # Priority 1: "## Next Steps" section from implementation_plan.md
        # Priority 2: "## Pending Tasks" (top 3) from task.md

        next_steps = ""
        if plan_content:
            next_steps = self._extract_section_content(plan_content, "Next Steps", "Future Work")

        if not next_steps:
            # Fallback to Top 3 Pending Tasks from task.md
            if task_content:
                pending = self._extract_unchecked_items_list(task_content, limit=3)
                if pending:
                    next_steps = "### 建议优先级 (Suggested Priorities)\n" + pending

        if next_steps:
            context["next_session_guide"] = next_steps

        return context

    def _scan_ag_exports(self, session_id: str, date_str: str) -> str:
        """
        Scan AG_Exports for the session log.
        Priority:
        1. Strict Match: File contains both {date_str} and {session_id}.
        2. Interactive Selection: List recent files and ask user to choose.
        """
        # Use config or default path
        export_dir = self.root_dir / "docs/logs/raw/AG_Exports"
        if not export_dir.exists():
            # Try user home documents fallback
            export_dir = Path.home() / "Documents/AG_Exports"

        if not export_dir.exists():
            return ""

        from datetime import datetime

        while True:
            try:
                files = list(export_dir.glob("*.md"))
                if not files:
                    # No files at all -> Prompt to export
                    if not self._prompt_no_files(export_dir, date_str, session_id):
                        return ""
                    continue

                # 1. Try Strict Match First (Auto-Select)
                strict_matches = []
                for f in files:
                    if session_id in f.name and date_str in f.name:
                        strict_matches.append(f)

                if strict_matches:
                    # If multiple strict matches, take the latest one
                    best_file = max(strict_matches, key=lambda f: f.stat().st_mtime)
                    return self._extract_user_objective(best_file)

                # 2. No strict match -> Prepare Recent Candidates for Menu
                # Filter files modified in the last 48 hours to reduce noise
                threshold = datetime.now().timestamp() - 48 * 3600
                recent_files = [f for f in files if f.stat().st_mtime > threshold]
                recent_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

                if not recent_files:
                    if not self._prompt_no_files(export_dir, date_str, session_id):
                        return ""
                    continue

                # 3. Interactive Selection Menu
                console = Console()
                console.print(
                    f"\n[bold yellow]⚠️  未找到严格匹配 ({date_str}*{session_id}*) 的归档文件[/]"
                )
                console.print("[bold]请从最近修改的文件中选择:[/]")

                options = {}
                for idx, f in enumerate(recent_files[:9]):  # Show top 9
                    mtime_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M")
                    console.print(f"  [green]{idx + 1}[/]. {f.name} ([dim]{mtime_str}[/])")
                    options[str(idx + 1)] = f

                console.print("  [bold]s[/]. 跳过 (Skip)")
                console.print("  [bold]r[/]. 重试/刷新 (Rescan)")

                choice = Prompt.ask("请选择 (Select)", default="1")

                if choice.lower() == "s":
                    return ""
                if choice.lower() == "r":
                    continue

                if choice in options:
                    return self._extract_user_objective(options[choice])

                console.print("[red]无效选择，请重试[/]")
                continue

            except Exception as e:
                # If error occurs, print and return empty to avoid infinite loop
                print(f"[red]Error scanning exports: {e}[/]")
                return ""

    def _prompt_no_files(self, export_dir: Path, date_str: str, session_id: str) -> bool:
        """Prompt user when no candidate files are found. Returns True to retry, False to skip."""
        console = Console()
        console.print("\n[yellow]⚠️  目录中没有最近的 .md 文件[/]")
        console.print(f"请导出 Markdown 到:\n[bold]{export_dir}[/]")
        choice = Prompt.ask("按 [bold]Enter[/] 重试 (Rescan)，或 [bold]s[/] 跳过", default="")
        return choice.lower() != "s"

    def _extract_user_objective(self, file_path: Path) -> str:
        """Helper to read file and regex extract objective."""
        try:
            content = file_path.read_text(encoding="utf-8")
            match = re.search(r"### USER Objective:\s*(.*?)(?=\n##|\Z)", content, re.DOTALL)
            if match:
                return match.group(1).strip()
            return ""
        except Exception:
            return ""

    def _extract_session_objective_from_jsonl_md(self, md: str) -> str:
        """
        Extract the first substantial user message as the session objective
        from JSONL-generated markdown.
        """
        user_blocks = re.findall(r"### USER \(.*?\)\n\n(.*?)(?=\n### |$)", md, re.DOTALL)
        for block in user_blocks:
            text = block.strip()
            # Skip short messages and noise
            if len(text) >= 30 and not text.startswith("[Request interrupted"):
                return text[:500]  # Cap at 500 chars for objective
        return ""

    def _extract_checked_items(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            if "- [x] " in line:
                clean_line = line.replace("- [x] ", "").strip()
                lines.append(f"- {clean_line}")

        if not lines:
            return ""
        return "### 核心任务 (From task.md)\n" + "\n".join(lines)

    def _extract_unchecked_items_table(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            if "- [ ] " in line:
                clean_line = line.replace("- [ ] ", "").strip()
                if not clean_line:
                    continue
                # | 任务 | 描述 | 状态 | 下一步 |
                # Truncate description for table validity
                desc = clean_line
                task_name = clean_line.split(" ")[0] if " " in clean_line else clean_line

                lines.append(f"| {task_name[:15]} | {desc[:40]}... | 🔴 Pending | 实现 |")

        if not lines:
            return ""
        return "\n".join(lines)

    def _extract_unchecked_items_list(self, content: str, limit: int = 3) -> str:
        lines = []
        count = 0
        for line in content.splitlines():
            if "- [ ] " in line:
                clean_line = line.replace("- [ ] ", "").strip()
                if not clean_line:
                    continue
                lines.append(f"{count + 1}. {clean_line}")
                count += 1
                if count >= limit:
                    break

        if not lines:
            return ""
        return "\n".join(lines)

    def _extract_section_content(self, content: str, *keywords) -> str:
        """Extract content of a section matched by keywords."""
        lines = content.splitlines()
        capturing = False
        captured_lines = []

        for line in lines:
            if line.startswith("#"):
                # Check if new header matches any keyword
                if any(k.lower() in line.lower() for k in keywords):
                    capturing = True
                    continue
                else:
                    if capturing:  # Stop capturing on next header
                        break

            if capturing:
                captured_lines.append(line)

        return "\n".join(captured_lines).strip()

    def _replace_section(self, content: str, header: str, new_body: str) -> str:
        """Robustly replace a markdown section (header + body)"""
        # Finds the header and everything until the next '## ' or EOF
        # Header must be exact regex match (escape special chars if needed, but here simple str)
        escaped_header = re.escape(header)
        pattern = re.compile(f"^{escaped_header}.*?(?=^## |\\Z)", re.MULTILINE | re.DOTALL)

        replacement = f"{header}\n\n{new_body}\n\n"

        if pattern.search(content):
            return pattern.sub(replacement, content)
        else:
            # Append if not found? No, usually we expect template to have header.
            # But let's append just in case
            return content + f"\n\n{replacement}"

    def _extract_job_highlights(self, session_dir: Path) -> str:
        """
        Extract highlights from all job-end.md files in the session directory.
        """
        jobs_dir = session_dir / "jobs"
        if not jobs_dir.exists():
            return ""

        highlights = []
        # Sort by mtime
        job_dirs = sorted(jobs_dir.iterdir(), key=lambda d: d.stat().st_mtime)

        for job_d in job_dirs:
            if not job_d.is_dir():
                continue

            job_end_md = job_d / "job-end.md"
            if not job_end_md.exists():
                continue

            try:
                content = job_end_md.read_text(encoding="utf-8")
                # Extract "## 📝 任务总结" or "## 🎉 完成的内容"
                summary = self._extract_section_content(content, "任务总结", "Summary")
                achieved = self._extract_section_content(content, "完成的内容", "Completed")

                job_id = job_d.name
                entry = f"### Job: {job_id}\n"
                if summary:
                    entry += f"**Summary**:\n{summary}\n"
                if achieved:
                    entry += f"**Achieved**:\n{achieved}\n"

                highlights.append(entry)
            except Exception:
                # Log error but don't crash
                continue

        if not highlights:
            return ""

        return "\n".join(highlights)

    def _extract_table_row(self, content: str, key: str) -> str:
        for line in content.splitlines():
            if key in line and "|" in line:
                return line.strip()
        return ""

    def inject(self, target_file: Path, session_data: Optional[SessionData] = None):
        """Inject context into the target end.md file."""
        if not target_file.exists():
            return

        # Extract session_id and date_str from target_file path
        # Path structure: docs/logs/YYYY/MM-DD/{seq}-end.md
        try:
            session_id = target_file.name.split("-")[0]  # "02"

            # Parent is MM-DD, Grandparent is YYYY
            mm_dd = target_file.parent.name
            yyyy = target_file.parent.parent.name
            date_str = f"{yyyy}-{mm_dd}"
        except Exception:
            session_id = ""
            date_str = ""

        content = target_file.read_text(encoding="utf-8")
        ctx = self.scan_context(session_id, date_str, session_data=session_data)

        # 1. Achievements (Combine Objective + Completed Tasks + Walkthrough)
        achievements_body = ""
        if ctx.get("session_objective"):
            achievements_body += f"### 用户目标 (Session Objective)\n{ctx['session_objective']}\n"
        if ctx.get("achievements"):
            achievements_body += f"\n{ctx['achievements']}"

        if achievements_body:
            content = self._replace_section(
                content, "## 📅 今日成果 (Achievements)", achievements_body
            )

        # 2. Task Status (Unchecked items)
        if ctx.get("tasks_status"):
            content = self._replace_section(
                content, "## 🔴 未完任务 (Pending Tasks)", ctx["tasks_status"]
            )

        # 3. Code Status (STATUS.md)
        if ctx.get("code_status"):
            # "## ⭐ 代码现状 (Code Status)"
            content = self._replace_section(
                content, "## ⭐ 代码现状 (Code Status)", ctx["code_status"]
            )

        # 3.5 Job Highlights (From jobs/ directory)
        # Derive session_dir from target_file parent
        session_dir = target_file.parent
        job_highlights = self._extract_job_highlights(session_dir)
        if job_highlights:
            content = self._replace_section(
                content, "## 🧩 任务详情 (Job Highlights)", job_highlights
            )

        # 4. Legacy Issues (Implementation Plan)
        if ctx.get("legacy_issues"):
            content = self._replace_section(
                content, "## 🧱 遗留问题 (Legacy Issues)", ctx["legacy_issues"]
            )

        # 5. Next Session Guide (Auto)
        if ctx.get("next_session_guide"):
            content = self._replace_section(
                content, "## 🚀 明日开工指南 (Next Session Guide)", ctx["next_session_guide"]
            )

        # 6. Append Claude Code Transcript
        if session_data and session_data.claude_code_markdown:
            if "## 🤖 AI Session Transcript (Claude Code)" not in content:
                content += "\n\n## 🤖 AI Session Transcript (Claude Code)\n\n"
                content += session_data.claude_code_markdown

        target_file.write_text(content, encoding="utf-8")
