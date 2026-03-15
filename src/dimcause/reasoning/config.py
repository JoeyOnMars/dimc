from dataclasses import dataclass
from datetime import timedelta


@dataclass
class ReasoningConfig:
    """ReasoningEngine 的配置类。"""

    # 基于时间窗口的启发式规则配置
    time_window: timedelta = timedelta(hours=2)
    time_weight: float = 0.8

    # 语义模型配置
    # 默认使用 BAAI/bge-m3 (多语言支持好)，但在开发/测试环境可用更小的模型
    import os

    model_name: str = os.getenv("DIMCAUSE_EMBEDDING_MODEL", "BAAI/bge-m3")

    # 语义相似度阈值 (HybridInferenceEngine 使用)
    # 支持通过环境变量覆盖默认值 0.85
    semantic_threshold: float = float(os.getenv("DIMCAUSE_SEMANTIC_THRESHOLD", "0.85"))
