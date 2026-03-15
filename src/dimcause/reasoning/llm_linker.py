"""
LLM Linker — 基于 LLM 的因果推理链接器

使用 DeepSeek / 其他 LLM 推理事件间的因果关系。
设计为可选功能，无 API Key 时向用户提示原因。
"""

import json
import logging
import os
from typing import List, Optional

from dimcause.core.models import Event
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.linker_base import BaseLinker

logger = logging.getLogger(__name__)

# 系统提示: 让 LLM 基于 Dimcause 本体分析因果关系
SYSTEM_PROMPT = """你是一个软件工程因果推理引擎。给定两个开发过程中的事件，判断它们之间是否存在因果关系。

Dimcause 本体定义了 6 类实体和 7 种因果关系：

实体类型:
- Requirement (需求): 用户需求、产品需求或技术需求
- Decision (决策): 技术决策或架构选择
- Commit (提交): 代码提交
- Function (函数): 代码中的函数或类
- Incident (事故): 生产或测试中的故障
- Experiment (实验): A/B 测试、POC 或技术验证

因果关系类型:
- implements: 决策(Decision) 实现了某个 需求(Requirement)
- realizes: 提交(Commit) 落地了某个 决策(Decision)
- modifies: 提交(Commit) 修改了某个 函数(Function)
- triggers: 事故(Incident) 触发了新的 决策(Decision)
- validates: 实验(Experiment) 验证了某个 决策(Decision)
- overrides: 决策(Decision) 覆盖了之前的 决策(Decision)
- fixes: 提交(Commit) 修复了某个 事故(Incident)

请以 JSON 格式返回分析结果:
{"has_relation": true/false, "relation": "关系类型", "confidence": 0.0-1.0, "reason": "简短理由"}

如果没有明确的因果关系，返回: {"has_relation": false}
"""


class LLMLinker(BaseLinker):
    """基于 LLM 推理的因果链接器。"""

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        api_key: Optional[str] = None,
        min_confidence: float = 0.7,
    ):
        configured_provider = "deepseek"
        configured_model = model
        configured_api_key = api_key

        try:
            from dimcause.utils.config import get_config_value

            raw_llm = get_config_value("llm_primary", default={})
            if isinstance(raw_llm, dict):
                provider = raw_llm.get("provider", configured_provider)
                model_name = raw_llm.get("model")
                if model_name and model == "deepseek/deepseek-chat":
                    configured_provider = provider
                    configured_model = (
                        model_name if "/" in model_name else f"{provider}/{model_name}"
                    )
                if configured_api_key is None:
                    configured_api_key = raw_llm.get("api_key")
        except Exception:
            pass

        self.model = model
        self.model = configured_model
        self.api_key = configured_api_key
        self.min_confidence = min_confidence
        self._available: Optional[bool] = None
        self._unavailable_reason: Optional[str] = None

    def _provider_and_model(self) -> tuple[str, str]:
        provider = "deepseek"
        model_name = self.model
        if "/" in self.model:
            provider, model_name = self.model.split("/", 1)
        return provider, model_name

    @property
    def available(self) -> bool:
        """检查 LLM 是否可用"""
        if self._available is not None:
            return self._available

        provider, _ = self._provider_and_model()
        if not self.api_key:
            env_key = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "gemini": "GOOGLE_API_KEY",
            }.get(provider)
            if env_key:
                self.api_key = os.environ.get(env_key)

        if not self.api_key:
            self._unavailable_reason = (
                f"未设置 {provider.upper()} API Key。请在 .env 文件或环境变量中配置对应密钥。"
            )
            logger.info(f"LLMLinker: {self._unavailable_reason}")
            self._available = False
            return False

        try:
            from dimcause.extractors.llm_client import LiteLLMClient  # noqa: F401

            self._available = True
        except ImportError:
            self._unavailable_reason = "litellm 未安装。请运行: pip install litellm"
            logger.warning(f"LLMLinker: {self._unavailable_reason}")
            self._available = False

        return self._available

    @property
    def unavailable_reason(self) -> Optional[str]:
        """返回 LLM 不可用的原因 (供 CLI 向用户展示)。"""
        if self._available is None:
            _ = self.available  # 触发检查
        return self._unavailable_reason

    def link(self, events: List[Event], **kwargs) -> List[CausalLink]:
        """分析事件对并推理因果关系。"""
        if not self.available:
            return []

        max_pairs = kwargs.get("max_pairs", 20)
        links = []

        # 只分析最近的事件对 (避免 API 超量调用)
        pairs = self._select_candidate_pairs(events, max_pairs=max_pairs)
        logger.info(f"LLMLinker: 分析 {len(pairs)} 对候选事件")

        for evt_a, evt_b in pairs:
            result = self._analyze_pair(evt_a, evt_b)
            if result:
                links.append(result)

        logger.info(f"LLMLinker: 发现 {len(links)} 个因果链接")
        return links

    def _select_candidate_pairs(self, events: List[Event], max_pairs: int = 20) -> List[tuple]:
        """选择候选事件对 (按时间邻近性)。"""
        if len(events) < 2:
            return []

        # 按时间排序
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        pairs = []

        # 滑动窗口：相邻事件对
        for i in range(len(sorted_events) - 1):
            if len(pairs) >= max_pairs:
                break
            pairs.append((sorted_events[i], sorted_events[i + 1]))

        return pairs

    def _analyze_pair(self, evt_a: Event, evt_b: Event) -> Optional[CausalLink]:
        """使用 LLM 分析一对事件的因果关系。"""
        try:
            from dimcause.core.models import LLMConfig
            from dimcause.extractors.llm_client import LiteLLMClient

            provider, model_name = self._provider_and_model()

            config = LLMConfig(
                provider=provider,
                model=model_name,
                api_key=self.api_key,
            )
            client = LiteLLMClient(config=config)

            prompt = self._build_prompt(evt_a, evt_b)
            response = client.complete(prompt, system=SYSTEM_PROMPT)

            return self._parse_response(response, evt_a, evt_b)

        except Exception as e:
            logger.warning(f"LLMLinker: 分析失败 ({evt_a.id} <> {evt_b.id}): {e}")
            return None

    def _build_prompt(self, evt_a: Event, evt_b: Event) -> str:
        """构建 LLM 提示。"""
        return f"""请分析以下两个事件之间的因果关系:

事件 A:
- ID: {evt_a.id}
- 类型: {getattr(evt_a.type, "value", str(evt_a.type))}
- 时间: {evt_a.timestamp}
- 摘要: {evt_a.summary}
- 内容: {(evt_a.content or "")[:500]}

事件 B:
- ID: {evt_b.id}
- 类型: {getattr(evt_b.type, "value", str(evt_b.type))}
- 时间: {evt_b.timestamp}
- 摘要: {evt_b.summary}
- 内容: {(evt_b.content or "")[:500]}

请判断 A 和 B 之间是否存在因果关系，并以 JSON 格式返回结果。"""

    def _parse_response(self, response: str, evt_a: Event, evt_b: Event) -> Optional[CausalLink]:
        """解析 LLM 响应为 CausalLink。"""
        try:
            # 尝试从响应中提取 JSON
            text = response.strip()

            # 处理 markdown code block
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            if not data.get("has_relation", False):
                return None

            relation = data.get("relation", "")
            confidence = float(data.get("confidence", 0.0))

            if confidence < self.min_confidence:
                logger.debug(f"LLMLinker: 置信度不足 ({confidence:.2f} < {self.min_confidence})")
                return None

            # 验证关系合法性
            valid_relations = [
                "implements",
                "realizes",
                "modifies",
                "triggers",
                "validates",
                "overrides",
                "fixes",
            ]
            if relation not in valid_relations:
                logger.warning(f"LLMLinker: 无效关系 '{relation}'")
                return None

            return CausalLink(
                source=evt_a.id,
                target=evt_b.id,
                relation=relation,
                weight=confidence,
                metadata={
                    "origin": "llm",
                    "model": self.model,
                    "reason": data.get("reason", ""),
                },
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"LLMLinker: 解析响应失败: {e}")
            return None
