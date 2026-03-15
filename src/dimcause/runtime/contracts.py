from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """最小运行状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class RunArtifact(BaseModel):
    """运行过程中可追踪的最小工件合同。"""

    name: str = Field(description="工件名称")
    kind: str = Field(description="工件类别")
    path: str = Field(description="工件路径")
    exists: bool = Field(description="当前路径是否存在")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="过渡期补充信息")


class RunState(BaseModel):
    """最小运行状态合同。"""

    status: RunStatus = Field(default=RunStatus.UNKNOWN, description="当前运行状态")
    started_at: Optional[str] = Field(default=None, description="开始时间")
    updated_at: Optional[str] = Field(default=None, description="最近更新时间")
    ended_at: Optional[str] = Field(default=None, description="结束时间")
    failure_reason: Optional[str] = Field(default=None, description="失败原因")
    resume_count: int = Field(default=0, ge=0, description="恢复次数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="过渡期状态元数据")


class Run(BaseModel):
    """最小运行合同。"""

    id: str = Field(description="运行唯一标识")
    run_type: str = Field(description="运行类型")
    state: RunState = Field(description="运行状态")
    workspace: Optional[str] = Field(default=None, description="当前运行工作空间")
    branch: Optional[str] = Field(default=None, description="当前运行所在分支")
    artifacts: List[RunArtifact] = Field(default_factory=list, description="运行工件")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="过渡期补充信息")
