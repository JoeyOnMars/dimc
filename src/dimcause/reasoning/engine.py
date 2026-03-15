import logging
from typing import List, Optional

from dimcause.core.models import Event
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.config import ReasoningConfig
from dimcause.reasoning.semantic_linker import SemanticLinker
from dimcause.reasoning.time_window import TimeWindowLinker

logger = logging.getLogger(__name__)


class HybridInferenceEngine:
    """
    P2.1 Hybrid Inference Engine (Graph Builder).
    Combines Time-Window Heuristics, Semantic Similarity, and optional LLM Inference.
    """

    def __init__(
        self, config: Optional[ReasoningConfig] = None, semantic_threshold: Optional[float] = None
    ):
        self.config = config or ReasoningConfig()

        # Overlay runtime override if provided
        if semantic_threshold is not None:
            self.config.semantic_threshold = semantic_threshold

        # Initialize Linkers
        self.time_linker = TimeWindowLinker(window_seconds=self.config.time_window.total_seconds())
        self.semantic_linker = SemanticLinker(model_name=self.config.model_name)  # Lazy loads model

        # LLM Linker (可选, 无 API Key 时自动跳过)
        self.llm_linker = None
        try:
            from dimcause.reasoning.llm_linker import LLMLinker

            self.llm_linker = LLMLinker()
        except ImportError:
            logger.warning(
                "LLMLinker 不可用 (缺少 litellm 依赖)，因果推理将跳过 LLM 增强层。"
                "如需完整功能: pip install 'dimcause[full]'"
            )

    def infer(self, events: List[Event]) -> List[CausalLink]:
        """
        Run all linkers and aggregate results.
        """
        logger.info(f"Inferring links for {len(events)} events...")
        all_links = []

        # 1. Time Window Heuristics (Deterministic)
        time_links = self.time_linker.link(events)
        all_links.extend(time_links)
        logger.info(f"TimeWindowLinker found {len(time_links)} links")

        # 2. Semantic Linking (Probabilistic)
        semantic_links = self.semantic_linker.link(events, threshold=self.config.semantic_threshold)
        all_links.extend(semantic_links)
        logger.info(f"SemanticLinker found {len(semantic_links)} links")

        # 3. LLM Inference (可选)
        if self.llm_linker and self.llm_linker.available:
            llm_links = self.llm_linker.link(events, max_pairs=20)
            all_links.extend(llm_links)
            logger.info(f"LLMLinker found {len(llm_links)} links")
        else:
            reason = self.llm_linker.unavailable_reason if self.llm_linker else "litellm 未安装"
            logger.warning(f"LLMLinker 已跳过: {reason}。本次因果图不含 LLM 推理层。")

        # 4. Deduplication (Optional)
        # For now, we allow multiple edges between nodes if reasons differ

        return all_links


# Alias for backward compatibility if needed, but we prefer HybridInferenceEngine
ReasoningEngine = HybridInferenceEngine
