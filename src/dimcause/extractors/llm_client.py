"""
LiteLLM Client - 统一 LLM 接口

支持多种 LLM 后端：
- Ollama (本地)
- OpenAI
- Anthropic
- DeepSeek
- Gemini
"""

import os
from typing import List, Optional

import litellm
from litellm import completion

from dimcause.core.models import LLMConfig


class LiteLLMClient:
    """
    LiteLLM 客户端

    实现 ILLMClient 接口
    """

    def __init__(
        self, config: Optional[LLMConfig] = None, fallback_config: Optional[LLMConfig] = None
    ):
        self.config = config or LLMConfig()
        self.fallback_config = fallback_config

        # 配置 LiteLLM
        self._setup()

    def _setup(self) -> None:
        """配置 LiteLLM"""
        # 设置超时
        litellm.request_timeout = self.config.timeout

        # 禁用代理（localhost 连接不需要代理，避免 Antigravity Tools 等本地服务卡住）
        if self.config.base_url and (
            "127.0.0.1" in self.config.base_url or "localhost" in self.config.base_url
        ):
            os.environ["NO_PROXY"] = "127.0.0.1,localhost"
            os.environ["no_proxy"] = "127.0.0.1,localhost"

        # 通用兼容层：支持所有 Anthropic 兼容的中转服务
        # 如果用户设置了 ANTHROPIC_BASE_URL 但不是官方地址 (anthropic.com)，
        # 我们需要禁用 LiteLLM 的自动后缀拼接行为，防止出现 .../v1/v1/messages 这种错误
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
        # 只有在 provider 确实为 anthropic 时才启用此兼容逻辑
        if self.config.provider == "anthropic":
            if base_url and "anthropic.com" not in base_url:
                # 1. 禁用 LiteLLM 自动拼接 /v1/messages 后缀
                os.environ["LITELLM_ANTHROPIC_DISABLE_URL_SUFFIX"] = "True"

                # 2. 自动映射 Token -> API Key (兼容 AigoCode/Claude CLI)
                auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
                if auth_token and not os.environ.get("ANTHROPIC_API_KEY"):
                    os.environ["ANTHROPIC_API_KEY"] = auth_token
                    self.config.api_key = auth_token

            # 即便是官方 URL，如果只有 AUTH_TOKEN 也要映射（Claude Code CLI 场景）
            elif not os.environ.get("ANTHROPIC_API_KEY"):
                auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
                if auth_token:
                    os.environ["ANTHROPIC_API_KEY"] = auth_token
                    self.config.api_key = auth_token

        # 如果有 API Key，设置环境变量
        if self.config.api_key:
            key_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "gemini": "GOOGLE_API_KEY",
            }
            env_key = key_map.get(self.config.provider)
            if env_key:
                os.environ[env_key] = self.config.api_key

        # 特殊处理 Anthropic：兼容 Claude CLI 的 AUTH_TOKEN (如果前面的AigoCode逻辑没命中)
        if self.config.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
            if auth_token:
                os.environ["ANTHROPIC_API_KEY"] = auth_token

        # 特殊处理 DeepSeek：从环境变量读取 API Key 和 Base URL
        if self.config.provider == "deepseek":
            if not self.config.api_key:
                deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
                if deepseek_key:
                    self.config.api_key = deepseek_key
                    os.environ["DEEPSEEK_API_KEY"] = deepseek_key
            if not self.config.base_url:
                deepseek_url = os.environ.get("DEEPSEEK_BASE_URL")
                if deepseek_url:
                    self.config.base_url = deepseek_url
                else:
                    self.config.base_url = "https://api.deepseek.com"

    def _get_model_name(self, config: LLMConfig) -> str:
        """
        获取 LiteLLM 格式的模型名称

        格式: provider/model 或直接 model
        """
        if config.provider == "ollama":
            return f"ollama/{config.model}"
        elif config.provider == "openai":
            # OpenAI provider 特殊处理：如果模型名包含其他厂商关键词（claude/gemini/deepseek），
            # 必须加上 openai/ 前缀，防止 LiteLLM 自动判断协议导致 API Key 错误
            model_lower = config.model.lower()
            if any(keyword in model_lower for keyword in ["claude", "gemini", "deepseek"]):
                if "/" not in config.model:  # 避免重复添加前缀
                    return f"openai/{config.model}"
            return config.model
        elif config.provider == "anthropic":
            return f"anthropic/{config.model}"
        elif config.provider == "deepseek":
            return f"deepseek/{config.model}"
        elif config.provider == "gemini":
            return f"gemini/{config.model}"
        else:
            return config.model

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """
        单次 LLM 调用

        Args:
            prompt: 用户提示
            system: 系统提示（可选）

        Returns:
            LLM 响应文本
        """
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self._call_llm(self.config, messages)
            return response
        except Exception as e:
            # 尝试降级到备用模型
            if self.fallback_config:
                try:
                    return self._call_llm(self.fallback_config, messages)
                except Exception as fallback_error:
                    raise Exception(
                        f"Both primary and fallback failed: {e}, {fallback_error}"
                    ) from fallback_error
            raise

    def _call_llm(self, config: LLMConfig, messages: List[dict]) -> str:
        """调用 LLM"""
        model_name = self._get_model_name(config)
        temperature = config.temperature

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": config.max_tokens,
        }

        # 支持自定义 Base URL (适用于所有 Provider，包括 OpenAI/Anthropic 代理)
        if config.base_url:
            kwargs["api_base"] = config.base_url

        # 显式传递 API Key (防止环境变量未生效或 LiteLLM 读取延迟)
        if config.api_key:
            kwargs["api_key"] = config.api_key

        # 强制禁用代理（针对 localhost）- 直接配置 httpx 客户端
        if config.base_url and ("127.0.0.1" in config.base_url or "localhost" in config.base_url):
            import httpx

            # 创建不使用代理的 httpx 客户端（忽略环境变量中的代理设置）
            kwargs["client"] = httpx.Client(trust_env=False)

        response = completion(**kwargs)

        # Cost Tracking
        try:
            from dimcause.utils.cost_tracker import get_tracker

            usage = response.usage
            if usage:
                cost = get_tracker().calculate_cost(
                    model_name, usage.prompt_tokens, usage.completion_tokens
                )
                if cost > 0:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(f"💰 LLM Cost: ${cost:.6f} ({model_name})")
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            # P2 Audit Fix: Log cost tracking errors instead of silent fail
            logger.warning(f"Cost tracking failed for {model_name}: {e}")

        return response.choices[0].message.content

    async def complete_async(self, prompt: str, system: Optional[str] = None) -> str:
        """异步版本 (True Async with Async Fallback)"""
        import logging

        logger = logging.getLogger(__name__)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Try primary config
        try:
            response = await self._call_llm_async(self.config, messages)
            return response
        except Exception as primary_error:
            # P2 Audit Fix: Sanitize sensitive info in logs
            from dimcause.utils.security import sanitize_text

            safe_error, _ = sanitize_text(str(primary_error))
            logger.warning(f"Primary LLM failed: {safe_error}")

            # Try fallback config (also async)
            if self.fallback_config:
                try:
                    logger.info("Attempting fallback LLM...")
                    response = await self._call_llm_async(self.fallback_config, messages)
                    return response
                except Exception as fallback_error:
                    raise Exception(
                        f"Both primary and fallback LLMs failed: {primary_error}, {fallback_error}"
                    ) from fallback_error
            raise primary_error

    async def _call_llm_async(self, config: LLMConfig, messages: List[dict]) -> str:
        """异步调用 LLM (内部方法)"""
        import httpx
        from litellm import acompletion

        model_name = self._get_model_name(config)
        temperature = config.temperature

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": config.max_tokens,
        }

        if config.base_url:
            kwargs["api_base"] = config.base_url
        if config.api_key:
            kwargs["api_key"] = config.api_key

        # Force disable proxy for localhost
        if config.base_url and ("127.0.0.1" in config.base_url or "localhost" in config.base_url):
            kwargs["client"] = httpx.AsyncClient(trust_env=False)

        response = await acompletion(**kwargs)

        # Cost Tracking
        try:
            from dimcause.utils.cost_tracker import get_tracker

            usage = response.usage
            if usage:
                cost = get_tracker().calculate_cost(
                    model_name, usage.prompt_tokens, usage.completion_tokens
                )
                if cost > 0:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.info(f"💰 LLM Cost: ${cost:.6f} ({model_name})")
        except Exception as e:
            # Don't fail the call just because cost tracking failed, but log it
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Async cost tracking failed for {model_name}: {e}")

        return response.choices[0].message.content

    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        try:
            response = self.complete("Hi", system="Reply with 'ok' only.")
            return len(response) > 0
        except Exception:
            return False


# 便捷函数
def create_llm_client(
    provider: str = "ollama",
    model: str = "qwen2:7b",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LiteLLMClient:
    """创建 LLM 客户端"""
    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url or ("http://localhost:11434" if provider == "ollama" else None),
    )
    return LiteLLMClient(config=config)
