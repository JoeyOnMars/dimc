"""
模板管理系统

负责管理和渲染日志模板 (System Templates + User Templates)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dimcause.utils.config import get_config

# 内置模板
BUILTIN_TEMPLATES = {
    "session-start": """---
id: "{session_id}"
type: session-start
created_at: "{iso_timestamp}"
date: "{date}"
agent: "{agent}"
status: active
---

# 🌅 会话开始: {date}

## 今日计划

- [ ]
""",
    "session-end": """---
id: "{session_id}"
type: session-end
created_at: "{iso_timestamp}"
date: "{date}"
agent: "{agent}"
status: done
description: ""
tags: []
---

# 🌙 会话结束: {date}

## 今日总结

### 完成的工作

-

### 遇到的问题

-

### 明日计划

-

## [待办]

-
""",
    "job-start": """---
id: job_start_{job_id}_{timestamp}
type: job_start
timestamp: {iso_timestamp}
tags: [{job_id}]
metadata:
  job_id: "{job_id}"
---

# 🎯 任务开始: {job_id}

## 任务目标


## 实施计划

""",
    "job-end": """---
id: job_end_{job_id}_{timestamp}
type: job_end
timestamp: {iso_timestamp}
tags: [{job_id}]
status: done
metadata:
  job_id: "{job_id}"
---

# ✅ 任务结束: {job_id}

## 任务总结


## 完成的内容


## 遗留问题

""",
    "bug-report": """---
type: bug-report
date: "{date}"
severity: medium
status: open
---

# 🐞 错误报告 (Bug Report)

## 问题描述


## 复现步骤

1.
2.
3.

## 预期行为


## 实际行为


## 截图/日志

```
粘贴日志在这里
```
""",
    "decision-log": """---
type: decision-log
date: "{date}"
status: proposed
---

# 💡 架构决策记录 (ADR)

## 背景




## 选项

### 选项 1: [方案名称]
- ✅ 优点:
- ❌ 缺点:

### 选项 2: [方案名称]
- ✅ 优点:
- ❌ 缺点:

## 决策

我们决定使用 **[方案名称]**，因为...

## 后果

""",
}


class TemplateManager:
    """模板管理器"""

    def __init__(self, user_template_dir: str = "~/.dimcause/templates"):
        self.user_template_dir = Path(os.path.expanduser(user_template_dir))
        self._ensure_user_dir()

    def _ensure_user_dir(self):
        """确保用户模板目录存在"""
        if not self.user_template_dir.exists():
            self.user_template_dir.mkdir(parents=True, exist_ok=True)

            # 创建示例文板
            example_path = self.user_template_dir / "example.md"
            if not example_path.exists():
                example_path.write_text(
                    """---
type: note
date: "{date}"
---
# 📝 My Custom Note

""",
                    encoding="utf-8",
                )

    def list_templates(self) -> List[str]:
        """列出所有可用模板名称"""
        templates = list(BUILTIN_TEMPLATES.keys())

        # 加载用户模板
        if self.user_template_dir.exists():
            for f in self.user_template_dir.glob("*.md"):
                name = f.stem
                if name not in templates:
                    templates.append(name)

        return sorted(templates)

    def get_template(self, name: str) -> Optional[str]:
        """获取模板内容"""
        # 1. 优先查找内置
        if name in BUILTIN_TEMPLATES:
            return BUILTIN_TEMPLATES[name]

        # 2. 查找用户模板
        user_path = self.user_template_dir / f"{name}.md"
        if user_path.exists():
            return user_path.read_text(encoding="utf-8")

        return None

    def render(self, name: str, **kwargs) -> str:
        """
        渲染模板

        自动注入基础变量:
        - date: YYYY-MM-DD
        - time: HH:MM:SS
        - datetime: YYYY-MM-DD HH:MM:SS

        Note: 使用 replace 而不是 format，避免因为 Markdown 中的代码块 {} 导致 crash
        """
        content = self.get_template(name)
        if not content:
            raise ValueError(f"Template not found: {name}")

        # 准备上下文
        now = datetime.now()
        timestamp_unix = int(now.timestamp())
        context = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": str(timestamp_unix),
            "iso_timestamp": now.isoformat(),
            "job_id": "JOB-ID",  # 默认占位符
            "agent": get_config().agent_id,
        }

        # 合并用户提供的变量
        context.update(kwargs)

        # 使用 replace 进行简单替换，避免 format 的副作用
        for k, v in context.items():
            content = content.replace("{" + str(k) + "}", str(v))

        return content


# 全局实例
_template_manager = None


def get_template_manager() -> TemplateManager:
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager
