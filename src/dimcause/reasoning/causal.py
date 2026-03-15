from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CausalLink:
    """表示两个语义实体之间的因果关系。"""

    source: str  # 源 URI
    target: str  # 目标 URI
    relation: str  # 本体中的关系类型
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
