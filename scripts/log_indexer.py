#!/usr/bin/env python3
"""
⚠️ DEPRECATED: 此脚本已被 v4.0 版本替代
请使用: dimc index

log_indexer.py - 智能索引生成器
新版本使用 SQLite 增量索引，性能更好

使用方式：
    dimc index  # 推荐
    dimc index --rebuild  # 强制重建
"""

import warnings

warnings.warn("log_indexer.py 已废弃，请使用 'dimc index' 命令", DeprecationWarning, stacklevel=2)

import datetime  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

# Configuration
LOGS_DIR = os.getenv("LOGS_ROOT", "./docs/logs")
INDEX_FILE = os.path.join(LOGS_DIR, "INDEX.md")


def parse_frontmatter(content):
    """
    极简 YAML Frontmatter 解析器 (零依赖)
    """
    if not content.startswith("---"):
        return {}

    try:
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        yaml_block = parts[1]
        metadata = {}

        # 逐行解析 key: value
        for line in yaml_block.strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")

                # 简单列表处理 [a, b]
                if val.startswith("[") and val.endswith("]"):
                    items = val[1:-1].split(",")
                    metadata[key] = [i.strip().strip('"').strip("'") for i in items if i.strip()]
                else:
                    metadata[key] = val
        return metadata
    except Exception as e:
        print(f"Warning: Failed to parse frontmatter: {e}")
        return {}


def extract_summary(content):
    """提取 Summary 标题后的内容"""
    try:
        # 寻找 ## Summary 或 ### Summary
        match = re.search(r"#+\s*Summary\s*\n(.*?)(?=\n#+|$)", content, re.DOTALL | re.IGNORECASE)
        if match:
            # 取第一段非空文本，限制长度
            summary = match.group(1).strip()
            summary = re.sub(r">\s*", "", summary)  # 去掉引用符号
            lines = [line for line in summary.split("\n") if line.strip()]
            if lines:
                return lines[0][:150] + "..." if len(lines[0]) > 150 else lines[0]
    except Exception:
        pass
    return "No summary provided."


def scan_logs():
    """扫描所有 jobs 目录下的 end.md"""
    jobs_data = []

    logs_path = Path(LOGS_DIR)
    if not logs_path.exists():
        print(f"Logs directory not found: {LOGS_DIR}")
        return []

    # 遍历: YYYY/MM-DD/jobs/JOB_NAME/end.md
    # 使用 glob 匹配更灵活
    for end_file in logs_path.glob("**/jobs/*/end.md"):
        try:
            content = end_file.read_text(encoding="utf-8")
            meta = parse_frontmatter(content)

            # 如果没有 metadata，尝试从路径推断
            job_name = end_file.parent.name
            date_str = end_file.parent.parent.name  # MM-DD
            year_str = end_file.parent.parent.parent.name  # YYYY
            full_date = f"{year_str}-{date_str}"

            # 优先使用 Frontmatter 中的 description，否则从正文提取
            summary = meta.get("description")
            if not summary or summary.startswith("Key outcome"):
                # 如果没填或者是模板占位符，回退到正文提取
                summary = extract_summary(content)

            entry = {
                "date": meta.get("date", full_date),
                "job_id": meta.get("job_id", job_name),
                "status": meta.get("status", "done"),
                "tags": meta.get("tags", []),
                "summary": summary,
                "path": str(end_file.relative_to(logs_path.parent)),  # 相对 docs/logs 的路径
            }
            jobs_data.append(entry)
        except Exception as e:
            print(f"Error reading {end_file}: {e}")

    # 按日期倒序，然后按 job_id 排序
    jobs_data.sort(key=lambda x: (x["date"], x["job_id"]), reverse=True)
    return jobs_data


def generate_table(jobs, detailed=True):
    lines = []
    lines.append("| Date | Job | Status | Summary | Tags |")
    lines.append("|---|---|---|---|---|")

    current_date = ""
    for job in jobs:
        date = job["date"]
        date_display = f"**{date}**" if date != current_date else ""
        current_date = date

        tags_str = ", ".join([f"`{t}`" for t in job["tags"]])
        link = f"[{job['job_id']}]({job['path']})"

        # Archive 模式下只显示第一行摘要或不显示
        summary = job["summary"]
        if not detailed:
            summary = summary.split(".")[0]  # 极简摘要

        lines.append(f"| {date_display} | {link} | {job['status']} | {summary} | {tags_str} |")
    return "\n".join(lines)


def main():
    print("🔄 Scanning logs for Intelligent Indexing...")
    jobs = scan_logs()

    if not jobs:
        print("No job logs found.")
        return

    # === Split Logic ===
    # 设定热数据阈值：最近 7 天
    today = datetime.date.today()
    threshold = today - datetime.timedelta(days=7)

    hot_jobs = []
    archive_jobs = []

    for job in jobs:
        try:
            job_date = datetime.datetime.strptime(job["date"], "%Y-%m-%d").date()
            if job_date >= threshold:
                hot_jobs.append(job)
            else:
                archive_jobs.append(job)
        except ValueError:
            # 日期格式不对的归入 archive
            archive_jobs.append(job)

    # === Generate HOT Index (High Resolution) ===
    # 这是 Agent 必读的，Token 占用极少
    hot_content = f"""# 🔥 Active Context (Last 7 Days)
> High-resolution index for immediate context.

{generate_table(hot_jobs, detailed=True)}

---
*For older history, see [INDEX_ARCHIVE.md](INDEX_ARCHIVE.md)*
"""
    with open(os.path.join(LOGS_DIR, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write(hot_content)

    # === Generate ARCHIVE Index (Low Resolution) ===
    # 只有当找不到信息时才读取这个
    if archive_jobs:
        archive_content = f"""# 🏛️ Knowledge Archive (Older than 7 days)
> Low-resolution index for long-term recall.

{generate_table(archive_jobs, detailed=False)}
"""
        with open(os.path.join(LOGS_DIR, "INDEX_ARCHIVE.md"), "w", encoding="utf-8") as f:
            f.write(archive_content)

    print("✅ Index Optimized:")
    print(f"   - HOT Index (INDEX.md): {len(hot_jobs)} items (Agent Context)")
    print(f"   - ARCHIVE (INDEX_ARCHIVE.md): {len(archive_jobs)} items")


if __name__ == "__main__":
    main()
