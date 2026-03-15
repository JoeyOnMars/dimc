#!/usr/bin/env python3
import datetime
import os
import re
import sys
from pathlib import Path

# ANSI Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"  # Done
C_YELLOW = "\033[33m"  # Active
C_CYAN = "\033[36m"  # Planned
C_RED = "\033[31m"  # Error/Unplanned


def get_today_dir():
    # 从环境变量获取，或者默认构建
    root = os.getenv("LOGS_ROOT")
    if not root:
        # Fallback to finding git root
        cwd = Path.cwd()
        while cwd != cwd.parent:
            if (cwd / ".git").exists() or (cwd / ".logger-config").exists():
                root = cwd / "docs" / "logs"
                break
            cwd = cwd.parent

    if not root:
        root = Path("./docs/logs")
    else:
        root = Path(root)

    today = datetime.date.today()
    return root / f"{today.year}" / today.strftime("%m-%d")


def parse_daily_plan(daily_dir):
    """
    解析 daily start.md 中的任务列表
    Task pattern: "- [ ] ID-Name" or "- [x] ID-Name"
    """
    start_file = daily_dir / "start.md"
    tasks = {}  # id -> {raw_name, source_status}

    if start_file.exists():
        content = start_file.read_text(encoding="utf-8")
        # Regex to match markdown list items: - [ ] or - [x] followed by text
        # We assume the first word satisfying ID format is the Job ID
        pattern = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$", re.MULTILINE)

        for match in pattern.finditer(content):
            status_char = match.group(1).lower()
            text = match.group(2).strip()

            # 简单的 Job ID 提取逻辑: 取第一个空格前的部分，或者整体
            # E.g. "1-i18n Fix typos" -> ID: "1-i18n"
            parts = text.split(" ")
            job_id = parts[0]
            desc = " ".join(parts[1:])

            tasks[job_id] = {
                "id": job_id,
                "desc": desc,
                "planned": True,
                "marked_done": status_char == "x",
            }

    return tasks


def scan_actual_status(daily_dir, tasks):
    """
    扫描文件系统状态，覆盖或补充 tasks
    """
    jobs_dir = daily_dir / "jobs"

    # 1. 扫描已存在的文件夹
    if jobs_dir.exists():
        for job_path in jobs_dir.iterdir():
            if job_path.is_dir():
                job_id = job_path.name

                if job_id not in tasks:
                    tasks[job_id] = {
                        "id": job_id,
                        "desc": "(Unplanned Task)",
                        "planned": False,
                        "marked_done": False,
                    }

                # Check status
                if (job_path / "end.md").exists():
                    tasks[job_id]["fs_status"] = "done"
                elif (job_path / "start.md").exists():
                    tasks[job_id]["fs_status"] = "active"
                else:
                    tasks[job_id]["fs_status"] = "broken"

    return tasks


def print_dashboard(tasks):
    sorted_ids = sorted(tasks.keys())

    print(f"\n{C_BOLD}=== 📅 Task Dashboard ({datetime.date.today()}) ==={C_RESET}\n")
    print(f"{'#':<4} {'ID':<20} {'Status':<15} {'Source':<10} {'Description'}")
    print("-" * 70)

    menu_map = {}

    for idx, jid in enumerate(sorted_ids, 1):
        t = tasks[jid]
        menu_map[str(idx)] = jid

        # Determine display status
        fs_status = t.get("fs_status", "none")
        planned = t.get("planned", False)

        status_str = "Available"
        color = C_CYAN

        if fs_status == "done":
            status_str = "Done"
            color = C_GREEN
        elif fs_status == "active":
            status_str = "Active"
            color = C_YELLOW
        elif not planned and fs_status != "none":
            status_str = "Unplanned"
            color = C_RED  # 加塞任务

        source_str = "Plan.md" if planned else "Filesystem"

        print(
            f"{C_BOLD}[{idx}]{C_RESET}  {color}{jid:<20}{C_RESET} {color}{status_str:<15}{C_RESET} {source_str:<10} {t.get('desc', '')}"
        )

    print("-" * 70)
    print(f"{C_BOLD}[0]{C_RESET}  Create New Task")
    print(f"{C_BOLD}[q]{C_RESET}  Quit")

    return menu_map


def main():
    daily_dir = get_today_dir()

    # Init daily dir if not exists (lazy init)
    if not daily_dir.exists():
        # Let bash handle creation, but we can't show plan
        print(f"{C_YELLOW}No daily log found for today yet.{C_RESET}")
        tasks = {}
    else:
        tasks = parse_daily_plan(daily_dir)

    tasks = scan_actual_status(daily_dir, tasks)

    # Interactive Loop
    if not tasks:
        print("No planned tasks found.")

    menu = print_dashboard(tasks)

    try:
        choice = input(f"\n{C_BOLD}Select task number > {C_RESET}").strip()
    except EOFError:
        sys.exit(1)

    if choice == "q":
        sys.exit(0)
    elif choice == "0":
        # New task
        new_name = input("Enter new JOB name (e.g. 4-refactor): ").strip()
        if new_name:
            print(new_name)  # Output for Bash to capture
            sys.exit(0)
    elif choice in menu:
        print(menu[choice])  # Output for Bash to capture
        sys.exit(0)
    else:
        print(f"Invalid selection: {choice}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
