"""
Dimcause 数据模型定义 (Phase 1)

所有 Frontmatter 字段必须遵循此 Schema，否则被索引器拒绝。
使用 Pydantic v2 进行严格验证。
"""

import time
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class LogType(str, Enum):
    """日志类型枚举"""

    SESSION_START = "session-start"
    SESSION_END = "session-end"
    JOB_START = "job-start"
    JOB_END = "job-end"


class Status(str, Enum):
    """任务状态枚举"""

    ACTIVE = "active"
    PLANNING = "planning"
    DONE = "done"
    PENDING = "pending"  # 添加 Event 使用的状态
    IN_PROGRESS = "in_progress"  # 添加 Event 使用的状态
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


class EventStatus(str, Enum):
    """Event 专用状态枚举（与 Status 不同）"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


class BaseFrontmatter(BaseModel):
    """所有日志的基础 Schema"""

    type: LogType
    date: date
    status: Status = Status.ACTIVE
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        """支持多种日期格式"""
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            # 尝试多种格式
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"]:
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format: {v}")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        """支持字符串和列表格式的 tags"""
        if isinstance(v, str):
            # "ui, frontend, polish" -> ["ui", "frontend", "polish"]
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            return [str(t).strip() for t in v if t]
        return []


class SessionStartFrontmatter(BaseFrontmatter):
    """每日开工日志的 Schema (Session Start)"""

    type: LogType = LogType.SESSION_START
    supervisor_status: str = "Planning"


class SessionEndFrontmatter(BaseFrontmatter):
    """每日收工日志的 Schema (Session End)"""

    type: LogType = LogType.SESSION_END


class JobStartFrontmatter(BaseFrontmatter):
    """Job 开始日志的 Schema"""

    type: LogType = LogType.JOB_START
    job_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @field_validator("job_id", mode="before")
    @classmethod
    def normalize_job_id(cls, v):
        """标准化 job_id: 转小写，替换空格为横杠"""
        if isinstance(v, str):
            return v.lower().replace(" ", "-").replace("_", "-")
        return v


class JobEndFrontmatter(BaseFrontmatter):
    """Job 结束日志的 Schema"""

    type: LogType = LogType.JOB_END
    job_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @field_validator("job_id", mode="before")
    @classmethod
    def normalize_job_id(cls, v):
        """标准化 job_id"""
        if isinstance(v, str):
            return v.lower().replace(" ", "-").replace("_", "-")
        return v


class EventFrontmatter(BaseModel):
    """
    Event 文件的 Frontmatter Schema (对应 Event 模型)
    用于 ~/.dimcause/events 目录下的事件文件
    """

    id: str
    type: str  # EventType 的字符串值（decision, task, code_change等）
    timestamp: datetime
    tags: list[str] = Field(default_factory=list)
    # 可选字段
    status: Optional[str] = None  # EventStatus 字符串值
    added_via: Optional[str] = None
    type_hint: Optional[str] = None  # 实际类型提示

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        """解析 ISO 格式时间戳"""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                # 尝试其他格式
                try:
                    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError(f"Invalid timestamp format: {v}") from None
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        """支持字符串和列表格式的 tags"""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        if isinstance(v, list):
            return [str(t).strip() for t in v if t]
        return []

    @property
    def date(self):
        """从 timestamp 派生 date，兼容 indexer 的 meta.date 访问"""
        return self.timestamp.date()

    @property
    def description(self) -> str:
        """兼容 indexer 的 meta.description 访问，EventFrontmatter 无此字段"""
        return ""

    @property
    def job_id(self) -> str:
        """兼容 indexer 的 meta.job_id 访问"""
        return ""


def parse_yaml_frontmatter(content: str) -> dict[str, Any]:
    """
    极简 YAML Frontmatter 解析器 (零外部依赖)

    支持:
    - 基本 key: value
    - 引号值: key: "value with: colons"
    - 数组: key: [a, b, c]
    """
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    yaml_block = parts[1].strip()
    data = {}

    for line in yaml_block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        # 分割 key 和 value
        idx = line.index(":")
        key = line[:idx].strip()
        val = line[idx + 1 :].strip()

        # 标准化 key (支持 job-id 和 job_id)
        key = key.lower().replace("-", "_")

        # 处理引号
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]

        # 处理数组 [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            items = val[1:-1].split(",")
            val = [i.strip().strip('"').strip("'") for i in items if i.strip()]

        data[key] = val

    return data


def parse_frontmatter(content: str) -> Optional[BaseFrontmatter]:
    """
    解析 YAML Frontmatter 并验证 Schema

    Args:
        content: 包含 YAML Frontmatter 的 Markdown 内容

    Returns:
        验证通过的 Frontmatter 对象，或 None (格式无效)
    """
    data = parse_yaml_frontmatter(content)
    if not data:
        return None

    # 根据 type 选择对应的 Schema
    log_type = data.get("type", "")

    # Backward compatibility for legacy types
    if log_type == "daily-start":
        log_type = "session-start"
        data["type"] = LogType.SESSION_START
    elif log_type == "daily-end":
        log_type = "session-end"
        data["type"] = LogType.SESSION_END

    try:
        if log_type == "job-end":
            return JobEndFrontmatter(**data)
        elif log_type == "job-start":
            return JobStartFrontmatter(**data)
        elif log_type == "session-end":
            return SessionEndFrontmatter(**data)
        elif log_type == "session-start":
            return SessionStartFrontmatter(**data)
        elif log_type in ["session-start", "session-end", "job-start", "job-end"]:
            # 日志类型
            return BaseFrontmatter(**data)
        else:
            # 尝试作为 Event 解析（来自 ~/.dimcause/events 的文件）
            return EventFrontmatter(**data)
    except Exception:
        # 静默失败，返回 None
        return None


def validate_frontmatter(content: str) -> tuple[bool, Optional[str]]:
    """
    验证 Frontmatter 并返回错误信息

    Returns:
        (is_valid, error_message)
    """
    data = parse_yaml_frontmatter(content)
    if not data:
        return False, "No valid YAML frontmatter found"

    log_type = data.get("type", "")

    # Backward compatibility for legacy types
    if log_type == "daily-start":
        log_type = "session-start"
        data["type"] = LogType.SESSION_START
    elif log_type == "daily-end":
        log_type = "session-end"
        data["type"] = LogType.SESSION_END

    try:
        if log_type == "job-end":
            JobEndFrontmatter(**data)
        elif log_type == "job-start":
            JobStartFrontmatter(**data)
        elif log_type == "session-end":
            SessionEndFrontmatter(**data)
        elif log_type == "session-start":
            SessionStartFrontmatter(**data)
        else:
            BaseFrontmatter(**data)
        return True, None
    except Exception as e:
        return False, str(e)


class ChunkRecord(BaseModel):
    """文档片段记录，对应 chunks 表一行。"""

    chunk_id: str
    source_event_id: str
    session_id: str
    content: Optional[str] = None
    status: str = "raw"  # raw | embedded | extracted
    confidence: Optional[str] = "low"  # low | high
    needs_extraction: bool = True
    embedding_version: int = 0
    extraction_version: int = 0
    retry_count: int = 0
    extraction_failed: bool = False
    event_ids: List[str] = Field(default_factory=list)
    last_error: Optional[str] = None
    created_at: float = Field(default_factory=time.time)  # REAL float
    updated_at: float = Field(default_factory=time.time)  # REAL float


class ExtractedEventRecord(BaseModel):
    """从 chunk 提取出的候选事件，骨架定义，供后续 Task 003 扩展。"""

    id: str
    chunk_id: str
    type: str
    content: str
    metadata: Optional[Any] = None
