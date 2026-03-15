"""
MarkdownStore - Markdown 日志存储

人类可读的长期存储
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dimcause.core.models import Event


class MarkdownStore:
    """
    Markdown 存储

    实现 IMarkdownStore 接口
    """

    def __init__(self, base_dir: str = "~/.dimcause/events"):
        self.base_dir = Path(os.path.expanduser(base_dir))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, event: Event) -> str:
        """
        保存 Event 到 Markdown 文件

        文件结构: base_dir/YYYY/MM/DD/{event_id}.md
        """
        # 创建日期目录
        date_dir = self.base_dir / event.timestamp.strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件路径
        file_path = date_dir / f"{event.id}.md"

        # 写入 Markdown
        content = event.to_markdown()
        file_path.write_text(content, encoding="utf-8")

        return str(file_path)

    def load(self, path: str) -> Optional[Event]:
        """从文件加载 Event"""
        file_path = Path(path)
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            return Event.from_markdown(content, file_path=str(file_path))
        except Exception as e:
            print(f"Error loading {path}: {e}")

        return None

    def list_by_date(self, start: datetime, end: datetime) -> List[str]:
        """按日期范围列出文件"""
        from datetime import timedelta

        files = []
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            date_dir = self.base_dir / current.strftime("%Y/%m/%d")
            if date_dir.exists():
                files.extend([str(f) for f in date_dir.glob("*.md")])
            current = current + timedelta(days=1)

        return sorted(files)
