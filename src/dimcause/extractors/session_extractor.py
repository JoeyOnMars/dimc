"""
Session Extractor - Local-First Event Extraction

从对话日志中提取结构化事件，不依赖云端 LLM。
使用规则过滤 + embedding 分类的混合方案。

设计原则：
1. 规则过滤噪音（正则）- 快速去掉无用内容
2. 按对话轮次分块 - User → Assistant 为一轮
3. Embedding 分类 - 判断每轮类型
4. 关键词兜底 - 简单匹配作为 fallback
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from dimcause.extractors.chunking import Chunk

# 噪音模式（将被过滤的内容）
NOISE_PATTERNS = [
    # Claude Code 特有噪音
    r"Request interrupted",
    r"The user doesn't want to proceed",
    r"ToolUse \(.*?\): rejected",
    r"ToolUse \(.*?\): approved",  # 批准动作本身不是事件
    r"^\s*```\n\s*```\s*$",  # 空代码块
    r"^\s*$/m",  # 空行
    # 确认类消息
    r"^(yes|ok|okay|sure|go ahead|continue|proceed)\.?$",
    r"^[\s🎉👍✅✔]*$",  # 只有表情
]

# 类别关键词（用于兜底）
CATEGORY_KEYWORDS = {
    "completed_task": [
        "完成",
        "implemented",
        "fixed",
        "merged",
        "done",
        "已实现",
        "已修复",
        "已合并",
        "success",
        "创建了",
        "添加了",
        "修改了",
        "解决了",
    ],
    "problem": [
        "error",
        "failed",
        "exception",
        "bug",
        "crash",
        "错误",
        "失败",
        "异常",
        "崩溃",
        "问题",
        "解决",
        "修复",
        "bug",
    ],
    "decision": ["决定", "adopt", "choose", "选择", "决定采用", "decision", "选择", "采用", "确认"],
    "pending": ["pending", "未完成", "todo", "待处理", "还没", "暂时", "以后"],
    "code_change": [
        "修改了",
        "changed",
        "modified",
        "updated",
        "添加了",
        "added",
        "删除了",
        "removed",
    ],
}

# Embedding 类别向量（用于相似度匹配）
# 每个类别一个代表性文本
CATEGORY_EMBEDDING_PROMPTS = {
    "completed_task": "This describes a completed task or implemented feature. The work is done, finished, merged.",
    "problem": "This describes a problem, error, bug, or failure encountered during development.",
    "decision": "This describes a decision or choice made about architecture, design, or approach.",
    "pending": "This describes something that was not completed or needs to be done later.",
    "code_change": "This describes a code change, modification, or update to the codebase.",
}


@dataclass
class Turn:
    """对话轮次"""

    user: str
    assistant: str
    timestamp: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class ExtractionResult:
    """提取结果"""

    completed_tasks: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    code_changes: List[str] = field(default_factory=list)


class SessionExtractor:
    """
    本地会话提取器

    使用规则 + embedding 的混合方案进行事件提取。
    """

    def __init__(self, use_embedding: bool = True):
        self.use_embedding = use_embedding
        self._vector_store = None
        self._noise_regex = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE | re.MULTILINE)

    @property
    def vector_store(self):
        """延迟加载 VectorStore"""
        if self._vector_store is None:
            from dimcause.storage.vector_store import VectorStore

            self._vector_store = VectorStore()
        return self._vector_store

    def extract(self, markdown_text: str) -> ExtractionResult:
        """
        从 markdown 对话文本中提取结构化信息

        Args:
            markdown_text: Claude Code 或 Antigravity 导出的 markdown 内容

        Returns:
            ExtractionResult: 结构化提取结果
        """
        # Step 1: 过滤噪音
        cleaned = self._filter_noise(markdown_text)

        # Step 2: 分块为对话轮次
        turns = self._chunk_to_turns(cleaned)

        # Step 3: 分类每个轮次
        for turn in turns:
            self._classify_turn(turn)

        # Step 4: 汇总结果
        return self._aggregate_results(turns)

    def _filter_noise(self, text: str) -> str:
        """过滤噪音内容"""
        # 移除匹配噪音模式的内容
        filtered = self._noise_regex.sub("", text)

        # 移除多余的空行
        filtered = re.sub(r"\n{3,}", "\n\n", filtered)

        return filtered.strip()

    def _chunk_to_turns(self, text: str) -> List[Turn]:
        """
        将文本按对话轮次分块

        Claude Code 格式:
        ### USER (timestamp)
        ...内容...

        ### ASSISTANT (timestamp)
        ...内容...
        """
        turns = []

        # 按 USER-ASSISTANT 对分割
        # 匹配模式: ### USER ... ### ASSISTANT
        user_pattern = r"### USER \(.*?\)\n\n(.*?)(?=\n### |\Z)"
        assistant_pattern = r"### ASSISTANT \(.*?\)\n\n(.*?)(?=\n### |\Z)"

        users = re.findall(user_pattern, text, re.DOTALL)
        assistants = re.findall(assistant_pattern, text, re.DOTALL)

        # 配对 User 和 Assistant
        min_len = min(len(users), len(assistants))
        for i in range(min_len):
            turn = Turn(user=users[i].strip(), assistant=assistants[i].strip())
            turns.append(turn)

        # 如果数量不匹配，添加剩余的
        if len(users) > len(assistants):
            for i in range(len(assistants), len(users)):
                turns.append(Turn(user=users[i].strip(), assistant=""))

        return turns

    def _classify_turn(self, turn: Turn) -> None:
        """分类单个对话轮次"""
        combined = f"{turn.user}\n{turn.assistant}"

        # 优先用 Embedding 分类
        if self.use_embedding:
            category = self._classify_by_embedding(combined)
            if category:
                turn.category = category
                turn.summary = self._generate_summary(turn, category)
                return

        # Fallback: 关键词分类
        category = self._classify_by_keywords(combined)
        turn.category = category
        turn.summary = self._generate_summary(turn, category)

    def _classify_by_embedding(self, text: str) -> Optional[str]:
        """用 Embedding 相似度分类"""
        try:
            # 创建临时 chunk
            chunk = Chunk(
                event_id="temp",
                seq=0,
                pos=0,
                text=text[:2000],  # 限制长度
                token_count=len(text) // 4,
            )

            # 获取 embedding
            embeddings = self.vector_store.embed_chunks([chunk])
            if not embeddings:
                return None

            query_vec = embeddings[0]

            # 和每个类别 prompt 计算相似度
            best_category = None
            best_score = -1

            for category, prompt in CATEGORY_EMBEDDING_PROMPTS.items():
                # 获取类别 prompt 的 embedding
                cat_chunk = Chunk(
                    event_id="cat", seq=0, pos=0, text=prompt, token_count=len(prompt) // 4
                )
                cat_embeddings = self.vector_store.embed_chunks([cat_chunk])
                if not cat_embeddings:
                    continue

                cat_vec = cat_embeddings[0]

                # 余弦相似度
                score = self._cosine_similarity(query_vec, cat_vec)

                if score > best_score:
                    best_score = score
                    best_category = category

            # 设置阈值
            if best_score > 0.7:  # 相似度阈值
                return best_category

            return None

        except Exception:
            # Embedding 失败时返回 None，使用关键词兜底
            return None

    def _cosine_similarity(self, vec1, vec2) -> float:
        """计算余弦相似度"""
        import numpy as np

        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0

        return dot / (norm1 * norm2)

    def _classify_by_keywords(self, text: str) -> str:
        """用关键词分类"""
        text_lower = text.lower()

        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            scores[category] = score

        # 返回得分最高的类别
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)

        return "other"

    def _generate_summary(self, turn: Turn, category: str) -> str:
        """生成轮次摘要"""
        # 取用户消息的前100字符作为摘要
        user_preview = turn.user[:100].replace("\n", " ")

        if category == "completed_task":
            return f"完成: {user_preview}..."
        elif category == "problem":
            return f"问题: {user_preview}..."
        elif category == "decision":
            return f"决策: {user_preview}..."
        elif category == "pending":
            return f"待办: {user_preview}..."
        elif category == "code_change":
            return f"代码变更: {user_preview}..."
        else:
            return user_preview

    def _aggregate_results(self, turns: List[Turn]) -> ExtractionResult:
        """汇总所有轮次的分类结果"""
        result = ExtractionResult()

        for turn in turns:
            if not turn.category or turn.category == "other":
                continue

            summary = turn.summary or ""

            if turn.category == "completed_task":
                result.completed_tasks.append(summary)
            elif turn.category == "problem":
                result.problems.append(summary)
            elif turn.category == "decision":
                result.decisions.append(summary)
            elif turn.category == "pending":
                result.pending.append(summary)
            elif turn.category == "code_change":
                result.code_changes.append(summary)

        return result

    def to_markdown(self, result: ExtractionResult) -> str:
        """将提取结果转换为 markdown 格式"""
        lines = ["## 🤖 会话提取摘要 (Local Extraction)"]

        if result.completed_tasks:
            lines.append("\n### ✅ 完成的任务")
            for item in result.completed_tasks[:10]:  # 限制数量
                lines.append(f"- {item}")

        if result.problems:
            lines.append("\n### ❌ 遇到的问题")
            for item in result.problems[:10]:
                lines.append(f"- {item}")

        if result.decisions:
            lines.append("\n### 💡 决策")
            for item in result.decisions[:10]:
                lines.append(f"- {item}")

        if result.pending:
            lines.append("\n### ⏳ 待办事项")
            for item in result.pending[:10]:
                lines.append(f"- {item}")

        if result.code_changes:
            lines.append("\n### 🔧 代码变更")
            for item in result.code_changes[:10]:
                lines.append(f"- {item}")

        if not any(
            [
                result.completed_tasks,
                result.problems,
                result.decisions,
                result.pending,
                result.code_changes,
            ]
        ):
            lines.append("\n*未能识别出有效事件（可能对话内容不包含可提取信息）*")

        return "\n".join(lines)


def extract_session_events(markdown_text: str, use_embedding: bool = True) -> str:
    """
    便捷函数：从对话 markdown 提取事件并返回 markdown 格式

    Args:
        markdown_text: 对话 markdown 内容
        use_embedding: 是否使用 embedding 分类（默认 True）

    Returns:
        提取结果的 markdown 字符串
    """
    extractor = SessionExtractor(use_embedding=use_embedding)
    result = extractor.extract(markdown_text)
    return extractor.to_markdown(result)
