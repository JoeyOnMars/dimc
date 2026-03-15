"""
测试 Phase 5 功能补全:
- LLMLinker 基本行为
- dimc graph link / query 命令
"""

import json
from unittest.mock import MagicMock, patch

from dimcause.reasoning.causal import CausalLink


class TestLLMLinker:
    """测试 LLM Linker"""

    def test_llm_linker_unavailable_without_key(self):
        """无 API Key 时 LLMLinker 应不可用"""
        with patch.dict("os.environ", {}, clear=True):
            # 确保环境变量中没有 KEY
            import os

            os.environ.pop("DEEPSEEK_API_KEY", None)

            from dimcause.reasoning.llm_linker import LLMLinker

            linker = LLMLinker(api_key=None)
            # 手动清除缓存
            linker._available = None
            linker.api_key = None
            assert linker.available is False

    def test_llm_linker_returns_empty_when_unavailable(self):
        """不可用时 link() 应返回空列表"""
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker(api_key=None)
        linker._available = False
        result = linker.link([])
        assert result == []

    def test_llm_linker_parse_response_valid(self):
        """测试 LLM 响应解析 — 有效 JSON"""
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker()

        # 构造 mock 事件
        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"

        response = json.dumps(
            {"has_relation": True, "relation": "realizes", "confidence": 0.9, "reason": "测试理由"}
        )

        result = linker._parse_response(response, evt_a, evt_b)
        assert result is not None
        assert isinstance(result, CausalLink)
        assert result.source == "evt_001"
        assert result.target == "evt_002"
        assert result.relation == "realizes"
        assert result.weight == 0.9

    def test_llm_linker_parse_response_no_relation(self):
        """测试 LLM 响应解析 — 无关系"""
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker()
        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"

        response = json.dumps({"has_relation": False})
        result = linker._parse_response(response, evt_a, evt_b)
        assert result is None

    def test_llm_linker_parse_response_low_confidence(self):
        """测试 LLM 响应解析 — 置信度不足"""
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker(min_confidence=0.8)
        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"

        response = json.dumps(
            {"has_relation": True, "relation": "realizes", "confidence": 0.5, "reason": "不太确定"}
        )

        result = linker._parse_response(response, evt_a, evt_b)
        assert result is None

    def test_llm_linker_parse_response_invalid_relation(self):
        """测试 LLM 响应解析 — 无效关系类型"""
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker()
        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"

        response = json.dumps(
            {
                "has_relation": True,
                "relation": "invented_relation",
                "confidence": 0.9,
            }
        )

        result = linker._parse_response(response, evt_a, evt_b)
        assert result is None

    def test_llm_linker_parse_response_markdown_codeblock(self):
        """测试 LLM 响应解析 — Markdown code block 包装"""
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        linker = LLMLinker()
        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"

        response = '```json\n{"has_relation": true, "relation": "fixes", "confidence": 0.85, "reason": "修复了bug"}\n```'
        result = linker._parse_response(response, evt_a, evt_b)
        assert result is not None
        assert result.relation == "fixes"

    def test_llm_linker_analyze_pair_uses_configured_model(self):
        from dimcause.core.models import Event
        from dimcause.reasoning.llm_linker import LLMLinker

        evt_a = MagicMock(spec=Event)
        evt_a.id = "evt_001"
        evt_a.type = "decision"
        evt_a.timestamp = "2026-03-07T00:00:00"
        evt_a.summary = "a"
        evt_a.content = "a"

        evt_b = MagicMock(spec=Event)
        evt_b.id = "evt_002"
        evt_b.type = "decision"
        evt_b.timestamp = "2026-03-07T00:01:00"
        evt_b.summary = "b"
        evt_b.content = "b"

        linker = LLMLinker(model="deepseek/deepseek-reasoner", api_key="sk-test")

        with patch("dimcause.extractors.llm_client.LiteLLMClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete.return_value = json.dumps({"has_relation": False})
            mock_client_cls.return_value = mock_client
            linker._analyze_pair(evt_a, evt_b)

        config = mock_client_cls.call_args.kwargs["config"]
        assert config.provider == "deepseek"
        assert config.model == "deepseek-reasoner"


class TestEngineIntegration:
    """测试 HybridInferenceEngine 集成 LLMLinker"""

    def test_engine_has_llm_linker(self):
        """验证 Engine 初始化时包含 LLMLinker"""
        from dimcause.reasoning.engine import HybridInferenceEngine

        engine = HybridInferenceEngine()
        # LLMLinker 应该被初始化 (可能不可用但不应为 None)
        assert hasattr(engine, "llm_linker")
