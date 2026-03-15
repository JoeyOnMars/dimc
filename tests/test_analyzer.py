from unittest.mock import MagicMock

import pytest

from dimcause.brain.analyzer import Analyst
from dimcause.extractors.llm_client import LiteLLMClient


class TestAnalyzer:
    @pytest.fixture
    def mock_client(self):
        return MagicMock(spec=LiteLLMClient)

    def test_smart_add_success(self, mock_client):
        mock_client.complete.return_value = (
            '{"type": "progress", "tags": ["test"], "summary": "Done"}'
        )
        analyst = Analyst(mock_client)

        res = analyst.analyze_input("Did something")

        assert res["type"] == "progress"
        assert res["tags"] == ["test"]
        mock_client.complete.assert_called_once()

    def test_json_parse_markdown(self, mock_client):
        # LLM returns markdown code block
        mock_client.complete.return_value = (
            'Here is the JSON:\n```json\n{"type": "issue", "tags": [], "summary": "Bug"}\n```'
        )
        analyst = Analyst(mock_client)

        res = analyst.analyze_input("Fix bug")
        assert res["type"] == "issue"
        assert res["summary"] == "Bug"

    def test_failure_fallback(self, mock_client):
        mock_client.complete.side_effect = Exception("API Error")
        analyst = Analyst(mock_client)

        res = analyst.analyze_input("My Input")
        assert res["type"] == "thought"  # Default
        assert res["summary"] == "My Input"
