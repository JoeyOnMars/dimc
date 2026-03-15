from unittest.mock import MagicMock, patch

import pytest

from dimcause.extractors.llm_client import create_llm_client


class TestDeepSeekClient:
    @pytest.fixture
    def mock_completion(self):
        with patch("dimcause.extractors.llm_client.completion") as mock:
            # Setup a successful response structure
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Mock Response"))]
            mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
            mock.return_value = mock_response
            yield mock

    @pytest.fixture
    def mock_tracker(self):
        with patch("dimcause.utils.cost_tracker.get_tracker") as mock_get:
            mock_inst = MagicMock()
            mock_get.return_value = mock_inst
            yield mock_inst

    def test_deepseek_config_passed(self, mock_completion, mock_tracker):
        """测试 DeepSeek 配置参数是否正确传递给 litellm"""
        client = create_llm_client(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
        )

        response = client.complete("Hello")

        assert response == "Mock Response"

        # Verify litellm call args
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]

        assert call_kwargs["model"] == "deepseek/deepseek-chat"
        assert call_kwargs["api_key"] == "sk-test"
        assert call_kwargs["api_base"] == "https://api.deepseek.com/v1"

    def test_cost_tracking_integration(self, mock_completion, mock_tracker):
        """测试调用成功后是否触发计费"""
        client = create_llm_client(provider="deepseek", model="deepseek-chat")

        client.complete("Hello")

        # Verify tracker called with correct token counts from mock response (100, 50)
        mock_tracker.calculate_cost.assert_called_once()
        args = mock_tracker.calculate_cost.call_args

        # args[0] is positional args: (model_name, input, output)
        assert args[0][0] == "deepseek/deepseek-chat"
        assert args[0][1] == 100
        assert args[0][2] == 50

    def test_env_var_pickup(self):
        """测试从环境变量读取 Key 和 URL"""
        with patch.dict(
            "os.environ",
            {"DEEPSEEK_API_KEY": "sk-env", "DEEPSEEK_BASE_URL": "https://env.deepseek.com"},
        ):
            # Re-import or create new instance (Config is loaded in __init__ usually,
            # but create_llm_client uses default args.
            # In llm_client.py: `if deepseek_key: self.config.api_key = deepseek_key` logic is inside __init__)

            client = create_llm_client(provider="deepseek", model="chat")

            assert client.config.api_key == "sk-env"
            assert client.config.base_url == "https://env.deepseek.com"
