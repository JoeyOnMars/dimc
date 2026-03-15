import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from dimcause.core.models import Event, EventType, SourceType
from dimcause.extractors.llm_client import LiteLLMClient

logger = logging.getLogger(__name__)


class EventExtractor:
    """
    智能事件提取器 (Brain Layer)

    使用 LLM 从非结构化文本（日志、Diff）中提取工程事件。
    """

    SYSTEM_PROMPT = """Role: You are an Expert Engineering Auditor for the Dimcause (Dimcause) project.
Objective: Extract structured engineering events from the provided development log or git diff.

Input Context:
- Project: Dimcause (Python, CLI, SQLite, LLM)
- Architecture: 4-Layer "Brain" (Raw Logs -> Semantics -> Index -> Knowledge Graph).
- Philosophy: "Local-First", "Event-First" (tracking *why* code changed, not just *what*).
- Context: A development session log or git diff containing engineering activities.

Target Event Types:
1. **decision**: High-leverage architectural or design choices.
   - Example directly affecting the system structure, data models, or adding new features.
   - *Constraint*: Must be a deliberate choice, not just "implemented X".
2. **failed_attempt**: Actions that failed, were rejected, or rolled back.
   - *Key*: Extract the *cause* of failure and the *correction*.
3. **reasoning**: The intellectual "Why" behind a tricky implementation.
   - *Key*: Explain the logic, trade-off, or algorithm choice.
4. **convention**: Establishment of new project rules, patterns, or architecture constraints.
   - Example: "All timestamps must be UTC", "Use 'mal' prefix for CLI commands".
5. **ai_conversation**: Critical interactions with AI that shaped the outcome.
   - Example: Prompt engineering refinements, AI-suggested refactoring plans.

Output Format (JSON List):
[
  {
    "type": "decision" | "failed_attempt" | "reasoning" | "convention" | "ai_conversation",
    "summary": "Concise title (<50 chars, e.g. 'Adopt SQLite over JSON')",
    "description": "Detailed explanation. For 'failed_attempt', include error and fix.",
    "tags": ["tag1", "tag2"],
    "priority": "P1" (Strategic) | "P2" (Tactical)
  }
]

Constraints & Noise Filtering:
- **IGNORE** formatting, lint fixes, or import sorting (e.g. `isort`, `black`).
- **IGNORE** trivial refactors (e.g. renaming variables) UNLESS it reveals a semantic shift.
- **IGNORE** tool execution logs (e.g. "Command completed") UNLESS it shows a significant failure.
- **DISTINGUISH** `decision` vs `reasoning`: A `decision` changes the *direction* (Choice A vs B). `reasoning` explains the *path* (How A works).
- Output ONLY valid JSON.
"""

    def __init__(self, llm_client: Optional[LiteLLMClient] = None):
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = LiteLLMClient()

    def extract_from_text(self, text: str, source_id: Optional[str] = None) -> List[Event]:
        """从文本日志提取事件"""
        return self._run_extraction(text, source_id=source_id)

    def extract_from_diff(self, diff: str, source_id: Optional[str] = None) -> List[Event]:
        """从 Git Diff 提取事件"""
        # Truncate diff if too long to save tokens
        if len(diff) > 20000:  # Bumped to 20k for DeepSeek's larger context
            diff_snippet = diff[:20000] + "\n...(truncated)..."
        else:
            diff_snippet = diff

        prompt = (
            f"Analyze the following Git Diff and extract key engineering events:\n\n{diff_snippet}"
        )
        return self._run_extraction(prompt, source_id=source_id)

    def _run_extraction(self, input_text: str, source_id: Optional[str] = None) -> List[Event]:
        """执行 LLM 提取并解析结果"""
        try:
            response = self.llm.complete(input_text, system=self.SYSTEM_PROMPT)
            raw_events = self._parse_json(response)

            events = []
            for item in raw_events:
                event = self._map_to_event(item, source_id)
                if event:
                    events.append(event)

            return events

        except Exception as e:
            logger.error(f"Event extraction failed: {e}")
            return []

    def _parse_json(self, text: str) -> List[Dict]:
        """解析 LLM 返回的 JSON"""
        # Strip code blocks
        text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Simple repair: try to close a truncated JSON array of objects
            try:
                # Find the last '}'
                last_brace = text.rfind("}")
                if last_brace != -1:
                    repaired_text = text[: last_brace + 1] + "]"
                    return json.loads(repaired_text)
            except json.JSONDecodeError:
                pass

            logger.warning(f"Failed to parse JSON: {text[:100]}...")
            return []

    def _map_to_event(self, item: Dict, source_id: Optional[str]) -> Optional[Event]:
        """将字典映射为 Event 对象"""
        try:
            # Map specific types, fallback to UNKNOWN
            type_str = item.get("type", "unknown").lower()
            evt_type = EventType.UNKNOWN

            # Exact match first
            try:
                evt_type = EventType(type_str)
            except ValueError:
                # Fuzzy matching fallback
                if "fail" in type_str:
                    evt_type = EventType.FAILED_ATTEMPT
                elif "decision" in type_str:
                    evt_type = EventType.DECISION
                elif "reason" in type_str:
                    evt_type = EventType.REASONING
                elif "convention" in type_str:
                    evt_type = EventType.CONVENTION
                elif "ai" in type_str or "conversation" in type_str:
                    evt_type = EventType.AI_CONVERSATION
                elif "diff" in type_str or "commit" in type_str:
                    evt_type = EventType.GIT_COMMIT

            # Generate stable-ish ID if possible, else random
            # Format: evt_ai_{timestamp}_{random}
            now_str = datetime.now().strftime("%Y%m%d%H%M%S")
            short_id = uuid.uuid4().hex[:8]
            evt_id = f"evt_ai_{now_str}_{short_id}"

            tags = item.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]

            priority = item.get("priority")
            metadata = {"extractor": "llm-v2"}
            if priority:
                metadata["priority"] = priority
            if source_id:
                metadata["source_ref"] = source_id

            return Event(
                id=evt_id,
                type=evt_type,
                timestamp=datetime.now(),
                summary=item.get("summary", "No summary"),
                content=item.get("description", ""),
                tags=tags,
                source=SourceType.MANUAL,  # Mark as manual-like since it's high level, or should add AI_GENERATED? 'manual' fits best for now as it mimics human input.
                metadata=metadata,
                raw_data_id=source_id,
            )

        except Exception as e:
            logger.warning(f"Failed to map item to event: {item}, error: {e}")
            return None
