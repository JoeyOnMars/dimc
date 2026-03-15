import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# 测试环境检测：防止测试污染生产数据
def _get_usage_file() -> Path:
    if os.getenv("PYTEST_CURRENT_TEST"):
        # 测试环境使用临时文件
        return Path("/tmp/dimcause_test_usage.csv")
    return Path(os.path.expanduser("~/.dimcause/usage.csv"))


USAGE_FILE = _get_usage_file()


@dataclass
class Pricing:
    input_price: float  # per 1M tokens
    output_price: float  # per 1M tokens


# 价格表 (USD per 1M tokens) - 2026年1月参考价格
# 统一使用 "per 1M" 以避免过多小数位
PRICING_TABLE: Dict[str, Pricing] = {
    # OpenAI
    "gpt-4o": Pricing(5.0, 15.0),
    "gpt-4o-mini": Pricing(0.15, 0.6),
    # Anthropic
    "claude-3-5-sonnet": Pricing(3.0, 15.0),
    "claude-3-5-haiku": Pricing(0.25, 1.25),
    # DeepSeek (Very cheap!)
    "deepseek-chat": Pricing(0.14, 0.28),  # $0.14 / 1M input (!)
    "deepseek-reasoner": Pricing(0.55, 2.19),
    # Google
    "gemini-1.5-flash": Pricing(0.075, 0.3),
    "gemini-1.5-pro": Pricing(3.5, 10.5),
    # Local (Free)
    "ollama": Pricing(0.0, 0.0),
    "qwen": Pricing(0.0, 0.0),  # Assuming local/ollama
    "llama": Pricing(0.0, 0.0),
}


class CostTracker:
    def __init__(self):
        self._session_cost: float = 0.0
        self._session_input_tokens: int = 0
        self._session_output_tokens: int = 0
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        try:
            if not USAGE_FILE.exists():
                USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(USAGE_FILE, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["timestamp", "model", "input_tokens", "output_tokens", "cost_usd"]
                    )
        except Exception as e:
            logger.warning(f"Failed to init usage file: {e}")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算单次调用成本"""
        pricing = self._find_pricing(model)
        if not pricing:
            # 默认给一个警告，不做计算
            logger.debug(f"Pricing not found for model {model}, assuming 0.")
            return 0.0

        input_cost = (input_tokens / 1_000_000) * pricing.input_price
        output_cost = (output_tokens / 1_000_000) * pricing.output_price
        total = input_cost + output_cost

        # Persist to CSV
        try:
            with open(USAGE_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [datetime.now().isoformat(), model, input_tokens, output_tokens, total]
                )
        except Exception as e:
            logger.warning(f"Failed to persist usage to CSV: {e}")

        # Update session stats
        self._session_cost += total
        self._session_input_tokens += input_tokens
        self._session_output_tokens += output_tokens

        return total

    def _find_pricing(self, model_name: str) -> Optional[Pricing]:
        """模糊匹配模型价格"""
        model_lower = model_name.lower()

        # 1. 精确匹配
        if model_lower in PRICING_TABLE:
            return PRICING_TABLE[model_lower]

        # 2. 前缀/Substr匹配 (e.g. "gpt-4o-2024-05-13" -> "gpt-4o")
        # 优先匹配长名称以提高准确性
        sorted_keys = sorted(PRICING_TABLE.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in model_lower:
                return PRICING_TABLE[key]

        return None

    def get_session_stats(self) -> Dict:
        return {
            "total_cost_usd": round(self._session_cost, 6),
            "input_tokens": self._session_input_tokens,
            "output_tokens": self._session_output_tokens,
        }


# 全局单例
_tracker = CostTracker()


def get_tracker() -> CostTracker:
    return _tracker
