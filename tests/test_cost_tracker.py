from pathlib import Path
from unittest.mock import patch

import pytest

from dimcause.utils.cost_tracker import CostTracker


class TestCostTracker:
    @pytest.fixture
    def tracker(self):
        # 每次测试重新实例化，避免单例状态污染
        return CostTracker()

    def test_deepseek_pricing(self, tracker):
        """验证 DeepSeek 价格计算准确性"""
        # DeepSeek V3 Pricing: Input $0.14/1M, Output $0.28/1M

        # Case 1: 1M input, 1M output
        cost = tracker.calculate_cost("deepseek-chat", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.14 + 0.28)

        # Case 2: Small usage (1000 tokens)
        # Input: 1000 * 0.14 / 1M = 0.00014
        # Output: 1000 * 0.28 / 1M = 0.00028
        cost = tracker.calculate_cost("deepseek-chat", 1000, 1000)
        assert cost == pytest.approx(0.00042)

        # Case 3: Reasoner (DeepSeek R1)
        cost = tracker.calculate_cost("deepseek-reasoner", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.55 + 2.19)

    def test_fuzzy_matching(self, tracker):
        """测试模型名称模糊匹配"""
        # "deepseek-chat-v3" should match "deepseek-chat"
        cost = tracker.calculate_cost("deepseek-chat-v3", 1_000_000, 0)
        assert cost == pytest.approx(0.14)

        # "openai/gpt-4o-2024-08-06" should match "gpt-4o"
        cost = tracker.calculate_cost("openai/gpt-4o-2024-08-06", 1_000_000, 0)
        assert cost == pytest.approx(5.0)

    def test_unknown_model(self, tracker):
        """测试未知模型返回0"""
        cost = tracker.calculate_cost("unknown-model-xyz", 1000, 1000)
        assert cost == 0.0

    def test_session_stats(self, tracker):
        """测试会话统计累加"""
        tracker.calculate_cost("deepseek-chat", 1000, 1000)  # 0.00042
        tracker.calculate_cost("deepseek-chat", 1000, 1000)  # 0.00042

        stats = tracker.get_session_stats()
        assert stats["input_tokens"] == 2000
        assert stats["output_tokens"] == 2000
        assert stats["total_cost_usd"] == pytest.approx(0.00084)

    def test_csv_persistence(self, tracker):
        """测试 CSV 写入"""
        test_path = Path("/tmp/dimcause_test_usage_patched.csv")
        if test_path.exists():
            test_path.unlink()

        # Patch USAGE_FILE in the module where CostTracker is defined
        with patch("dimcause.utils.cost_tracker.USAGE_FILE", test_path):
            # Init a fresh tracker inside patch context so __init__ uses the patched path
            t = CostTracker()

            assert test_path.exists()

            # Write record
            t.calculate_cost("deepseek-chat", 100, 100)

            content = test_path.read_text()
            assert "timestamp,model,input_tokens,output_tokens,cost_usd" in content
            assert "deepseek-chat,100,100" in content
