import json
import re
from typing import Any, Dict

from dimcause.brain.prompts import SystemPrompts
from dimcause.extractors.llm_client import LiteLLMClient


class Analyst:
    def __init__(self, client: LiteLLMClient):
        self.client = client

    def analyze_input(self, text: str) -> Dict[str, Any]:
        """
        Analyze user input to suggest type, tags, and summary.
        Returns dict with keys: type, tags, summary.
        Fallback to defaults on failure.
        """
        default_result = {"type": "thought", "tags": [], "summary": text[:50]}

        try:
            response = self.client.complete(
                prompt=f'Input: "{text}"', system=SystemPrompts.SMART_ADD
            )
            return self._parse_json(response, default_result)
        except Exception:
            # P2: Add logging here
            # print(f"Analysis failed: {e}")
            # Silent fail to default is safer for CLI
            return default_result

    def reflect_on_logs(self, logs_text: str) -> str:
        """
        Generate a reflection report from raw logs text.
        """
        try:
            return self.client.complete(
                prompt=f"Here are the logs:\n{logs_text}", system=SystemPrompts.REFLECTION
            )
        except Exception as e:
            return f"Reflection failed: {e}"

    def _parse_json(self, text: str, default: Dict) -> Dict:
        """Robust JSON parsing capable of handling markdown blocks"""
        try:
            # 1. Try clean parse
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            # 2. Try parsing markdown code block
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))

            # 3. Try finding bare JSON object
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass

        return default
