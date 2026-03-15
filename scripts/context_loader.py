#!/usr/bin/env python3
"""
⚠️ DEPRECATED: 此脚本已被 v4.0 版本替代
请使用: dimc context

context_loader.py - 自动加载最近的日志上下文

三层逻辑：
1. Raw (原始对话) → 汇总到 MD
2. MD (end.md / job/end.md) → 汇总到 INDEX
3. INDEX.md → Agent 首先读取的高层索引

本脚本优先读取 INDEX.md，提取最近的工作记录和待办事项。
只有当 INDEX.md 信息不足时，才深入读取具体的 end.md 文件。

使用方式：
    dimc context  # 推荐
    python3 scripts/context_loader.py  # 旧方式
"""

import warnings

warnings.warn(
    "context_loader.py 已废弃，请使用 'dimc context' 命令", DeprecationWarning, stacklevel=2
)

import glob  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
LOGS_DIR = os.path.join(ROOT_DIR, "docs", "logs")
INDEX_FILE = os.path.join(LOGS_DIR, "INDEX.md")
ARCHIVE_FILE = os.path.join(LOGS_DIR, "INDEX_ARCHIVE.md")

# 关键字模式，用于匹配 TODO 相关的标题
TODO_PATTERNS = [
    r"\[待办\]",
    r"\[TODO\]",
    r"\[遗留\]",
    r"\[遗留问题\]",
    r"\[明日切入点\]",
    r"\[Next Steps?\]",
    r"\[下一步\]",
    r"### 待办",
    r"### TODO",
    r"### 遗留",
    r"### Next",
]


def parse_index_table(filepath):
    """解析 INDEX.md 中的表格，提取最近的工作记录"""
    entries = []

    if not os.path.exists(filepath):
        return entries

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return entries

    # 匹配表格行: | Date | Job | Status | Summary | Tags |
    # 跳过表头和分隔行
    lines = content.split("\n")
    in_table = False

    for line in lines:
        line = line.strip()

        # 检测表格开始
        if line.startswith("| Date") or line.startswith("|---|"):
            in_table = True
            continue

        # 解析表格行
        if in_table and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]  # 去除空字符串

            if len(parts) >= 4:
                date = parts[0].replace("**", "")  # 去除 markdown 加粗
                job = parts[1]
                status = parts[2]
                summary = parts[3]
                tags = parts[4] if len(parts) > 4 else ""

                entries.append(
                    {"date": date, "job": job, "status": status, "summary": summary, "tags": tags}
                )

    return entries


def extract_todos_from_file(filepath):
    """从单个 end.md 文件中提取 TODO 相关内容"""
    todos = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return todos

    for pattern in TODO_PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        for match in matches:
            start_pos = match.end()
            remaining = content[start_pos:]
            next_section = re.search(r"\n###?\s", remaining)

            if next_section:
                section_content = remaining[: next_section.start()]
            else:
                section_content = remaining[:500]

            items = re.findall(r"^\s*[-*]\s*(.+)$", section_content, re.MULTILINE)
            for item in items:
                item = item.strip()
                if item and len(item) > 3:
                    todos.append(item)

    return todos


def find_recent_end_files(limit=3):
    """查找最近的 end.md 文件用于深度提取"""
    end_files = []
    year_dirs = sorted(glob.glob(os.path.join(LOGS_DIR, "20*")), reverse=True)

    for year_dir in year_dirs:
        if not os.path.isdir(year_dir):
            continue
        for pattern in ["*-end.md", "*/*-end.md", "*/jobs/*/end.md"]:
            matches = glob.glob(os.path.join(year_dir, pattern))
            end_files.extend(matches)

    end_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return end_files[:limit]


def main():
    print("=" * 60)
    print("📋 上下文恢复 (Context Loader v2.0)")
    print("=" * 60)

    # ===== 检查待合并分支 =====
    pending_merge_file = os.path.join(ROOT_DIR, ".agent", "pending_merge.txt")
    if os.path.exists(pending_merge_file):
        with open(pending_merge_file, "r") as f:
            pending_branch = f.read().strip()

        print("\n" + "⚠️" * 20)
        print(f"⚠️  检测到未合并的分支: {pending_branch}")
        print("")
        print("昨天您做的改动都提交到了新的分支。")
        print("您的本地主开发分支在 Git 上的最新版本并没有包含这些改动。")
        print("如果您想让昨天的改动生效，需要将新建分支的改动合并到本地分支并提交。")
        print("")
        print("请执行以下命令合并：")
        print(f"   git merge {pending_branch}")
        print("   git push")
        print(f"   rm {pending_merge_file}")
        print("⚠️" * 20 + "\n")

    # ===== Layer 1: 读取 INDEX.md (Hot Index) =====
    print("\n📊 Layer 1: 读取 INDEX.md (Hot Index)")

    index_entries = parse_index_table(INDEX_FILE)

    if index_entries:
        print(f"   找到 {len(index_entries)} 条近期记录:")
        for entry in index_entries[:5]:  # 最多显示 5 条
            status_icon = "✅" if entry["status"] == "done" else "🔄"
            print(f"   {status_icon} [{entry['date']}] {entry['job']}")
            print(f"      📝 {entry['summary'][:80]}...")
    else:
        print("   ⚠️  INDEX.md 为空或不存在")

    # ===== Layer 2: 深度读取 end.md 提取 TODO =====
    print("\n🔍 Layer 2: 深度读取 end.md 提取待办")

    end_files = find_recent_end_files(limit=3)
    all_todos = []

    for filepath in end_files:
        todos = extract_todos_from_file(filepath)
        for todo in todos:
            if todo not in all_todos:
                all_todos.append(todo)

    if all_todos:
        print(f"   找到 {len(all_todos)} 条遗留待办:")
        for i, todo in enumerate(all_todos, 1):
            print(f"   {i}. {todo[:100]}")
    else:
        print("   ✅ 未发现明确的遗留待办")

    # ===== 输出建议 =====
    print("\n" + "=" * 60)
    print("💡 开工建议:")

    if all_todos:
        print("   根据历史记录，今天应该继续处理以下任务：")
        for _, todo in enumerate(all_todos[:3], 1):  # 最多 3 条
            print(f"   → {todo[:80]}")
        print("\n   询问用户：是否按此计划开工？")
    elif index_entries:
        print("   近期工作已完成，无明确遗留。")
        print("   询问用户：今天是否有新的任务？")
    else:
        print("   这是一个新项目，暂无历史记录。")
        print("   询问用户：今天想从哪里开始？")

    print("=" * 60)


if __name__ == "__main__":
    main()
