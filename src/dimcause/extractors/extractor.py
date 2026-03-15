"""
BasicExtractor - 信息提取器

使用 LLM 从原始文本提取结构化 Event
"""

import json
import re
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from dimcause.core.models import Entity, Event, EventType
from dimcause.extractors.llm_client import LiteLLMClient

# 提取 Prompt
EXTRACTION_PROMPT = """Analyze the following developer conversation and extract structured information.

INPUT:
{content}

OUTPUT (JSON only, no markdown):
{{
    "type": "decision|code_change|diagnostic|research|discussion|unknown",
    "type": "decision|code_change|diagnostic|research|discussion|unknown",
    "summary": "One sentence summary under 50 words (Use the same language as the input content)",
    "entities": [
    "entities": [
        {{"name": "entity_name", "type": "file|function|library|concept"}}
    ],
    "tags": ["tag1", "tag2"],
    "files": ["file1.py", "file2.js"]
}}
"""


class BasicExtractor:
    """
    基础信息提取器

    实现 IExtractor 接口
    """

    def __init__(self, llm_client: Optional[LiteLLMClient] = None):
        self.llm = llm_client

    def extract(self, content: str) -> Event:
        """
        从原始文本提取 Event

        流程：
        1. 尝试使用 LLM 提取
        2. LLM 失败则使用 Regex 降级
        """
        if self.llm:
            try:
                return self._extract_with_llm(content)
            except Exception as e:
                print(f"LLM extraction failed: {e}, falling back to regex")

        return self._extract_with_regex(content)

    def extract_batch(self, contents: List[str]) -> List[Event]:
        """批量提取"""
        return [self.extract(c) for c in contents]

    def _extract_with_llm(self, content: str) -> Event:
        """使用 LLM 提取"""
        prompt = EXTRACTION_PROMPT.format(content=content[:2000])  # 限制长度

        system = "You are a JSON extractor. Output valid JSON only, no explanation."
        response = self.llm.complete(prompt, system=system)

        # 解析 JSON
        data = self._parse_json_response(response)

        return self._create_event(content, data)

    def _extract_with_regex(self, content: str) -> Event:
        """使用 Regex 降级提取"""
        # 检测事件类型
        event_type = self._detect_type_regex(content)

        # 提取实体
        entities = self._extract_entities_regex(content)

        # 提取文件
        files = self._extract_files_regex(content)

        # 生成摘要（取前100字符）
        summary = content[:100].replace("\n", " ").strip()
        if len(content) > 100:
            summary += "..."

        return Event(
            id=f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            type=event_type,
            timestamp=datetime.now(),
            summary=summary,
            content=content,
            entities=entities,
            related_files=files,
            confidence=0.5,  # Regex 提取置信度较低
        )

    def _parse_json_response(self, response: str) -> dict:
        """解析 LLM 返回的 JSON"""
        # 移除可能的 markdown 代码块
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise

    def _create_event(self, content: str, data: dict) -> Event:
        """从提取数据创建 Event"""
        # 解析事件类型
        type_str = data.get("type", "unknown").lower()
        try:
            event_type = EventType(type_str)
        except ValueError:
            event_type = EventType.UNKNOWN

        # 解析实体
        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and "name" in e:
                entities.append(Entity(name=e["name"], type=e.get("type", "unknown")))

        return Event(
            id=f"event_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            type=event_type,
            timestamp=datetime.now(),
            summary=data.get("summary", content[:100]),
            content=content,
            entities=entities,
            tags=data.get("tags", []),
            related_files=data.get("files", []),
            confidence=0.9,  # LLM 提取置信度较高
        )

    def _detect_type_regex(self, content: str) -> EventType:
        """使用关键词检测事件类型"""
        content_lower = content.lower()

        # 决策关键词
        decision_keywords = [
            "decide",
            "决定",
            "选择",
            "choose",
            "will use",
            "采用",
            "決策",
            "選用",
            "採用",
        ]
        if any(kw in content_lower for kw in decision_keywords):
            return EventType.DECISION

        # 代码变更关键词
        code_keywords = [
            "修改",
            "修复",
            "fix",
            "change",
            "update",
            "implement",
            "实现",
            "修正",
            "實作",
            "重構",
            "refactor",
            "修復",
            "解決",
            "解决",
        ]
        if any(kw in content_lower for kw in code_keywords):
            return EventType.CODE_CHANGE

        # 诊断关键词
        diag_keywords = ["error", "bug", "问题", "issue", "debug", "调试", "錯誤", "異常", "排查"]
        if any(kw in content_lower for kw in diag_keywords):
            return EventType.DIAGNOSTIC

        # 调研关键词
        research_keywords = ["research", "调研", "了解", "learn", "study", "研究", "學習"]
        if any(kw in content_lower for kw in research_keywords):
            return EventType.RESEARCH

        # 任务/管理关键词
        task_keywords = [
            "task",
            "todo",
            "plan",
            "roadmap",
            "session",
            "wrap-up",
            "job",
            "summary",
            "汇报",
            "计划",
            "任务",
            "总结",
        ]
        if any(kw in content_lower for kw in task_keywords):
            return EventType.TASK

        # AI 对话关键词
        ai_keywords = [
            "ai conversation",
            "chat",
            "prompt",
            "llm",
            "user request",
            "assistant",
            "对话",
            "提问",
        ]
        if any(kw in content_lower for kw in ai_keywords):
            return EventType.AI_CONVERSATION

        # 默认尝试归类为 Reasoning 如果长度足够且不像代码
        if len(content) > 50 and "def " not in content and "class " not in content:
            # 这是一个弱假设，但比 unknown 好
            pass

        return EventType.UNKNOWN

    def _extract_entities_regex(self, content: str) -> List[Entity]:
        """使用 Regex 提取实体"""
        entities = []

        # 提取文件名
        file_pattern = r"[\w./\\-]+\.(py|js|ts|jsx|tsx|md|json|yaml|yml)"
        for match in re.findall(file_pattern, content):
            # 重新匹配完整路径
            full_pattern = rf"[\w./\\-]+\.{match}"
            for full_match in re.findall(full_pattern, content):
                entities.append(Entity(name=full_match, type="file"))

        # 提取函数名（Python 风格）
        func_pattern = r"(?:def|function)\s+(\w+)\s*\("
        for match in re.findall(func_pattern, content):
            entities.append(Entity(name=match, type="function"))

        return list(set(entities))  # 去重

    def _extract_files_regex(self, content: str) -> List[str]:
        """提取文件路径"""
        pattern = r"[\w./\\-]+\.(py|js|ts|jsx|tsx|md|json|yaml|yml|html|css|go|rs)"
        files = []
        for ext in re.findall(pattern, content):
            full_pattern = rf"[\w./\\-]+\.{ext}"
            files.extend(re.findall(full_pattern, content))
        return list(set(files))


# 便捷函数
def create_extractor(llm_client: Optional[LiteLLMClient] = None) -> BasicExtractor:
    """创建提取器实例"""
    return BasicExtractor(llm_client=llm_client)
