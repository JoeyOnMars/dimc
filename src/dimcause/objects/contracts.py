from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    """最小命题状态。"""

    PROPOSED = "proposed"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class RelationState(str, Enum):
    """最小关系状态。"""

    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RelationDirectionality(str, Enum):
    """最小关系方向性。"""

    DIRECTED = "directed"
    UNDIRECTED = "undirected"


class CheckStatus(str, Enum):
    """最小检查状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ResultOutcome(str, Enum):
    """最小结果结论。"""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ObjectContract(BaseModel):
    """对象家族的最小公共合同。"""

    id: str = Field(description="对象唯一标识")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="过渡期补充信息")


class Material(ObjectContract):
    """材料对象合同。"""

    object_family: Literal["material"] = Field(default="material", description="对象家族")
    material_type: str = Field(description="材料类型")
    source_ref: Optional[str] = Field(default=None, description="材料来源引用")
    title: Optional[str] = Field(default=None, description="材料标题或简述")
    evidence_refs: List[str] = Field(default_factory=list, description="相关证据引用")


class Claim(ObjectContract):
    """命题对象合同。"""

    object_family: Literal["claim"] = Field(default="claim", description="对象家族")
    claim_type: str = Field(description="命题类型")
    statement: str = Field(description="命题陈述")
    target_refs: List[str] = Field(default_factory=list, description="命题涉及的对象引用")
    evidence_refs: List[str] = Field(default_factory=list, description="支持或反驳命题的证据引用")
    status: ClaimStatus = Field(default=ClaimStatus.PROPOSED, description="命题当前状态")
    grade_refs: Dict[str, str] = Field(default_factory=dict, description="等级引用")


class RelationStateHistoryEntry(BaseModel):
    """关系状态历史条目。"""

    state: RelationState = Field(description="关系状态")
    changed_at: Optional[str] = Field(default=None, description="状态变更时间")


class Relation(ObjectContract):
    """关系对象合同。"""

    object_family: Literal["relation"] = Field(default="relation", description="对象家族")
    relation_type: str = Field(description="关系类型")
    from_ref: str = Field(description="关系起点对象引用")
    to_ref: str = Field(description="关系终点对象引用")
    directionality: RelationDirectionality = Field(
        default=RelationDirectionality.DIRECTED,
        description="关系方向性",
    )
    state: RelationState = Field(default=RelationState.CANDIDATE, description="关系当前状态")
    state_history: List[RelationStateHistoryEntry] = Field(
        default_factory=list,
        description="关系状态迁移历史",
    )
    evidence_refs: List[str] = Field(default_factory=list, description="关系证据引用")
    grade_refs: Dict[str, str] = Field(default_factory=dict, description="等级引用")


class Check(ObjectContract):
    """检查对象合同。"""

    object_family: Literal["check"] = Field(default="check", description="对象家族")
    check_type: str = Field(description="检查类型")
    target_refs: List[str] = Field(default_factory=list, description="检查目标对象引用")
    status: CheckStatus = Field(default=CheckStatus.PENDING, description="检查状态")
    evidence_refs: List[str] = Field(default_factory=list, description="检查相关证据引用")


class Result(ObjectContract):
    """结果对象合同。"""

    object_family: Literal["result"] = Field(default="result", description="对象家族")
    result_type: str = Field(description="结果类型")
    producer_ref: Optional[str] = Field(default=None, description="产生该结果的检查或运行引用")
    target_refs: List[str] = Field(default_factory=list, description="结果作用对象引用")
    outcome: ResultOutcome = Field(default=ResultOutcome.UNKNOWN, description="结果结论")
    evidence_refs: List[str] = Field(default_factory=list, description="结果相关证据引用")
