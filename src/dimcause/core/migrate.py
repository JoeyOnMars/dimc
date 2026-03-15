"""
Core migration logic from v1 to v2 schema.
"""

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import frontmatter


def generate_migration_id(date_str: str) -> str:
    """
    生成迁移时的 Event ID

    格式: evt_migrated_YYYYMMDD_<8位随机hex>
    例如: evt_migrated_20260122_a1b2c3d4

    策略:
    - 使用 UUID4 的前 8 位作为随机部分
    - 保留 date 以便追溯原始日期
    - 前缀 "migrated" 标识这是迁移生成的 ID
    """
    # 移除连字符以获得紧凑的日期字符串
    date_part = str(date_str).replace("-", "")
    random_part = uuid.uuid4().hex[:8]
    return f"evt_migrated_{date_part}_{random_part}"


def detect_schema_version(data: Dict[str, Any]) -> int:
    """
    检测 frontmatter 的 schema 版本

    规则:
    - 有 schema_version 字段 → 使用该值
    - 有 id 和 timestamp → v2
    - 有 date 字段 → v1
    - 否则返回 0 (未知)
    """
    if "schema_version" in data:
        try:
            return int(data["schema_version"])
        except (ValueError, TypeError):
            pass

    if "id" in data and "timestamp" in data:
        return 2

    if "date" in data:
        return 1

    return 0


def merge_description_to_content(description: Optional[str], content: str) -> str:
    """
    将 description 合并到 content

    在第一个 # 标题后插入引用块。如果找不到标题，插入到最前面。
    > **[迁移自 v1]** {description}
    """
    if not description or not description.strip():
        return content

    # 清理 description (去除首尾空白)
    desc_text = description.strip()
    injection = f"> **[迁移自 v1]** {desc_text}\n\n"

    # 尝试找到第一个标题
    # 匹配行首的 # (H1-H6)
    match = re.search(r"^(#+\s+.*)$", content, re.MULTILINE)

    if match:
        # 在标题行的下一行插入
        end_pos = match.end()
        prefix = content[:end_pos]
        suffix = content[end_pos:]

        # 策略: 移除 suffix 开头的所有换行符，然后重新构建标准格式
        # 结果应为: Title\n\nInjection\n\nBody...
        suffix_stripped = suffix.lstrip("\n")

        return f"{prefix}\n\n{injection}{suffix_stripped}"
    else:
        # 没有标题，插入到最前面
        return injection + content


def migrate_event(
    data: Dict[str, Any], content: str, from_version: int = 1, to_version: int = 2
) -> Tuple[Dict[str, Any], str]:
    """
    迁移 frontmatter 和 content

    Args:
        data: frontmatter dict
        content: markdown body
        from_version: 源版本 (默认 1)
        to_version: 目标版本 (默认 2)

    Returns:
        (new_data, new_content)

    v1 → v2 转换:
    - id: 调用 generate_migration_id(data['date'])
    - type: 保留（下划线替换连字符: daily-end → daily_end）
    - timestamp: date + "T00:00:00"
    - source: "manual"
    - tags: 保留
    - schema_version: 2
    - description: 合并到 content
    """
    if from_version != 1 or to_version != 2:
        raise ValueError(f"Unsupported migration: v{from_version} -> v{to_version}")

    new_data = {}

    # 1. ID Generation
    date_str = str(data.get("date", datetime.now().strftime("%Y-%m-%d")))
    new_data["id"] = generate_migration_id(date_str)

    # 2. Type Conversion (hyphen to underscore)
    old_type = str(data.get("type", "unknown"))
    new_data["type"] = old_type.replace("-", "_")

    # 3. Timestamp (date -> timestamp)
    # yyyy-mm-dd -> yyyy-mm-ddT00:00:00
    new_data["timestamp"] = f"{date_str}T00:00:00"

    # 4. Source (default manual for migrated)
    new_data["source"] = "manual"

    # 5. Tags (keep as list)
    tags = data.get("tags", [])
    if isinstance(tags, str):
        # Handle comma-separated string if present
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    new_data["tags"] = tags

    # 6. Schema Version
    new_data["schema_version"] = 2

    # 7. Description -> Content
    description = data.get("description")
    new_content = merge_description_to_content(description, content)

    return new_data, new_content


def migrate_file(path: Union[str, Path], dry_run: bool = True, backup: bool = True) -> bool:
    """
    迁移单个文件

    Args:
        path: 文件路径
        dry_run: 是否仅预览
        backup: 是否创建备份 (.v1.backup)

    Returns:
        bool: 是否进行了迁移 (True 表示已迁移/需迁移, False 表示跳过)
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        post = frontmatter.load(file_path)
        data = post.metadata
        content = post.content
    except Exception:
        # 无法解析 frontmatter
        return False

    version = detect_schema_version(data)

    # 仅迁移 v1
    if version != 1:
        return False

    # 如果是 dry_run，只要检测到是 v1 就算成功识别
    if dry_run:
        return True

    # 执行迁移逻辑
    new_data, new_content = migrate_event(data, content)

    # 构造新文件内容
    new_post = frontmatter.Post(new_content, **new_data)
    # frontmatter.dumps 会处理 YAML 分隔符
    new_file_text = frontmatter.dumps(new_post)

    # 备份
    if backup:
        # 命名规则: {filename}.v1.backup
        backup_path = file_path.with_name(file_path.name + ".v1.backup")
        shutil.copy2(file_path, backup_path)

    # 写入新内容
    file_path.write_text(new_file_text, encoding="utf-8")

    return True


def migrate_directory(
    dir_path: Union[str, Path], dry_run: bool = True, backup: bool = True
) -> Dict[str, Any]:
    """
    迁移目录下所有 .md 文件

    Returns:
        {
            "scanned": int,
            "needs_migration": int,
            "migrated": int,
            "skipped": int,
            "errors": List[Dict]
        }
    """
    path = Path(dir_path)
    stats = {"scanned": 0, "needs_migration": 0, "migrated": 0, "skipped": 0, "errors": []}

    if not path.exists():
        return stats

    # 递归查找 .md 文件
    # 排除备份文件
    files = [f for f in path.rglob("*.md") if not f.name.endswith(".backup")]
    stats["scanned"] = len(files)

    for f in files:
        try:
            # 预检版本
            try:
                post = frontmatter.load(f)
                version = detect_schema_version(post.metadata)
            except Exception:
                version = 0  # Parse error treated as unknown/skip

            if version == 1:
                stats["needs_migration"] += 1
                # 如果 dry_run=True, migrate_file 返回 True 表示"如果是真的话会迁移"
                # 如果 dry_run=False, migrate_file 返回 True 表示"已迁移"
                if migrate_file(f, dry_run=dry_run, backup=backup):
                    if not dry_run:
                        stats["migrated"] += 1
            else:
                stats["skipped"] += 1

        except Exception as e:
            stats["errors"].append({"file": str(f), "error": str(e)})

    return stats
