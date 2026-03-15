"""
DIMCAUSE v0.1 LiteLLM Client 真正测试

测试 LiteLLMClient 类（使用 Mock 拦截 API 调用）
"""

from unittest.mock import MagicMock, patch

import pytest


class TestLiteLLMClientInit:
    """测试 LiteLLMClient 初始化"""

    @patch("dimcause.extractors.llm_client.litellm")
    def test_client_creation(self, mock_litellm):
        """测试客户端创建"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        config = LLMConfig(provider="ollama", model="test")
        client = LiteLLMClient(config=config)

        assert client.config.provider == "ollama"
        assert client.config.model == "test"

    @patch("dimcause.extractors.llm_client.litellm")
    def test_client_with_fallback(self, mock_litellm):
        """测试带备用配置的客户端"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        primary = LLMConfig(provider="openai", model="gpt-4")
        fallback = LLMConfig(provider="ollama", model="qwen2:7b")

        client = LiteLLMClient(config=primary, fallback_config=fallback)

        assert client.config.provider == "openai"
        assert client.fallback_config.provider == "ollama"

    @patch("dimcause.extractors.llm_client.litellm")
    def test_get_model_name(self, mock_litellm):
        """测试模型名称格式化"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        client = LiteLLMClient()

        # Ollama
        ollama_config = LLMConfig(provider="ollama", model="qwen2:7b")
        assert client._get_model_name(ollama_config) == "ollama/qwen2:7b"

        # OpenAI
        openai_config = LLMConfig(provider="openai", model="gpt-4")
        assert client._get_model_name(openai_config) == "gpt-4"

        # Anthropic
        anthropic_config = LLMConfig(provider="anthropic", model="claude-3")
        assert client._get_model_name(anthropic_config) == "anthropic/claude-3"

        # DeepSeek
        deepseek_config = LLMConfig(provider="deepseek", model="deepseek-chat")
        assert client._get_model_name(deepseek_config) == "deepseek/deepseek-chat"

        # Gemini
        gemini_config = LLMConfig(provider="gemini", model="gemini-pro")
        assert client._get_model_name(gemini_config) == "gemini/gemini-pro"

    @patch("dimcause.extractors.llm_client.litellm")
    def test_setup_api_keys(self, mock_litellm):
        """测试 API Key 设置"""
        import os

        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        config = LLMConfig(provider="openai", model="gpt-4", api_key="test-openai-key")

        LiteLLMClient(config=config)

        assert os.environ.get("OPENAI_API_KEY") == "test-openai-key"


class TestLiteLLMClientComplete:
    """测试 LiteLLMClient 完成方法"""

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_complete_success(self, mock_litellm, mock_completion):
        """测试成功调用"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        # Mock 响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        config = LLMConfig(provider="openai", model="gpt-4")
        client = LiteLLMClient(config=config)

        result = client.complete("Hello")

        assert result == "Test response"
        mock_completion.assert_called_once()

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_complete_with_system_prompt(self, mock_litellm, mock_completion):
        """测试带系统提示的调用"""
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_completion.return_value = mock_response

        client = LiteLLMClient()

        result = client.complete("Hi", system="Reply with OK only")

        assert result == "OK"

        # 检查消息格式
        call_args = mock_completion.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages"))
        assert len(messages) == 2
        assert messages[0]["role"] == "system"

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_complete_with_fallback(self, mock_litellm, mock_completion):
        """测试降级到备用模型"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        # 第一次失败，第二次成功
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback response"

        mock_completion.side_effect = [Exception("Primary failed"), mock_response]

        primary = LLMConfig(provider="openai", model="gpt-4")
        fallback = LLMConfig(provider="ollama", model="qwen2:7b")

        client = LiteLLMClient(config=primary, fallback_config=fallback)

        result = client.complete("Hello")

        assert result == "Fallback response"
        assert mock_completion.call_count == 2

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_complete_both_fail(self, mock_litellm, mock_completion):
        """测试主备都失败"""
        from dimcause.core.models import LLMConfig
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_completion.side_effect = Exception("All failed")

        primary = LLMConfig(provider="openai", model="gpt-4")
        fallback = LLMConfig(provider="ollama", model="qwen2:7b")

        client = LiteLLMClient(config=primary, fallback_config=fallback)

        with pytest.raises(Exception) as excinfo:
            client.complete("Hello")

        assert "Both primary and fallback failed" in str(excinfo.value)


class TestLiteLLMClientAvailability:
    """测试 LiteLLMClient 可用性检查"""

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_is_available_true(self, mock_litellm, mock_completion):
        """测试可用性检查 - 成功"""
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_completion.return_value = mock_response

        client = LiteLLMClient()

        result = client.is_available()

        assert result is True

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_is_available_false(self, mock_litellm, mock_completion):
        """测试可用性检查 - 失败"""
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_completion.side_effect = Exception("Connection failed")

        client = LiteLLMClient()

        result = client.is_available()

        assert result is False


class TestCreateLLMClient:
    """测试便捷函数"""

    @patch("dimcause.extractors.llm_client.litellm")
    def test_create_llm_client_default(self, mock_litellm):
        """测试默认创建"""
        from dimcause.extractors.llm_client import create_llm_client

        client = create_llm_client()

        assert client.config.provider == "ollama"
        assert client.config.model == "qwen2:7b"

    @patch("dimcause.extractors.llm_client.litellm")
    def test_create_llm_client_openai(self, mock_litellm):
        """测试创建 OpenAI 客户端"""
        from dimcause.extractors.llm_client import create_llm_client

        client = create_llm_client(provider="openai", model="gpt-4", api_key="test-key")

        assert client.config.provider == "openai"
        assert client.config.model == "gpt-4"


class TestBasicExtractor:
    """测试 BasicExtractor"""

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_extractor_creation(self, mock_litellm, mock_completion):
        """测试提取器创建"""
        from dimcause.extractors.extractor import BasicExtractor
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"type": "decision", "summary": "test"}'
        mock_completion.return_value = mock_response

        client = LiteLLMClient()
        extractor = BasicExtractor(llm_client=client)

        assert extractor is not None

    @patch("dimcause.extractors.llm_client.completion")
    @patch("dimcause.extractors.llm_client.litellm")
    def test_extractor_extract(self, mock_litellm, mock_completion):
        """测试提取方法"""
        from dimcause.core.models import EventType
        from dimcause.extractors.extractor import BasicExtractor
        from dimcause.extractors.llm_client import LiteLLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
{
    "type": "decision",
    "summary": "选择 JWT 认证",
    "entities": ["auth.py", "jwt"],
    "tags": ["authentication"]
}
"""
        mock_completion.return_value = mock_response

        client = LiteLLMClient()
        extractor = BasicExtractor(llm_client=client)

        event = extractor.extract("我决定使用 JWT 进行身份验证")

        assert event is not None
        assert event.type in [EventType.DECISION, EventType.UNKNOWN]
