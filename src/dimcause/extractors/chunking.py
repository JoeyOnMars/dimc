"""
事件分块模块 (Event Chunking Module)

将 Event 内容分块以供向量检索使用。

遵循 MODEL_SELECTION_RULES.md:
- 不依赖具体模型或数据库
- 只负责 Event -> Chunk 转换

MAL-SEARCH-001 v5.2
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from dimcause.core.models import Event


@dataclass
class Chunk:
    """
    事件分块数据结构

    Attributes:
        event_id: 来源事件 ID
        seq: 分块序号 (从 0 开始)
        pos: 在原始 token 序列中的起始位置
        text: 分块文本内容
        token_count: token 数量
    """

    event_id: str
    seq: int
    pos: int
    text: str
    token_count: int


class EventChunker:
    """
    事件分块器

    使用 tiktoken 进行 token 计数和分块。
    策略: 800 tokens 每块，15% 重叠。

    遵循 MODEL_SELECTION_RULES.md:
    - 分块逻辑独立于 embedding 模型
    - 不访问磁盘/数据库
    """

    CHUNK_SIZE = 800  # 单块 token 数
    OVERLAP_RATIO = 0.15  # 15% 重叠

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        初始化分块器

        Args:
            encoding_name: tiktoken 编码名称 (默认 cl100k_base, GPT-4 使用)
        """
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(encoding_name)
        except ImportError:
            # 降级: 使用简单字符计数 (约 4 字符 = 1 token)
            self._encoding = None
            self._fallback_ratio = 4

    def chunk_event(self, event: "Event") -> List[Chunk]:
        """
        将事件内容分块

        Args:
            event: Event 对象

        Returns:
            Chunk 列表，通常 1-3 个分块
        """
        formatted = self._format_event(event)

        if self._encoding is not None:
            tokens = self._encoding.encode(formatted)
            return self._chunk_tokens(event.id, tokens)
        else:
            # 降级模式: 按字符分块
            return self._chunk_text_fallback(event.id, formatted)

    def _chunk_tokens(self, event_id: str, tokens: List[int]) -> List[Chunk]:
        """使用 tiktoken 进行精确分块"""
        step = int(self.CHUNK_SIZE * (1 - self.OVERLAP_RATIO))
        chunks: List[Chunk] = []

        for i in range(0, len(tokens), step):
            window = tokens[i : i + self.CHUNK_SIZE]
            if not window:
                break

            text = self._encoding.decode(window)
            chunks.append(
                Chunk(
                    event_id=event_id,
                    seq=len(chunks),
                    pos=i,
                    text=text,
                    token_count=len(window),
                )
            )

            # 如果窗口已经是最后一部分，停止
            if i + self.CHUNK_SIZE >= len(tokens):
                break

        return (
            chunks if chunks else [Chunk(event_id=event_id, seq=0, pos=0, text="", token_count=0)]
        )

    def _chunk_text_fallback(self, event_id: str, text: str) -> List[Chunk]:
        """降级模式: 按字符数分块 (约 4 字符 = 1 token)"""
        char_size = self.CHUNK_SIZE * self._fallback_ratio
        step = int(char_size * (1 - self.OVERLAP_RATIO))
        chunks: List[Chunk] = []

        for i in range(0, len(text), step):
            window = text[i : i + char_size]
            if not window:
                break

            chunks.append(
                Chunk(
                    event_id=event_id,
                    seq=len(chunks),
                    pos=i,
                    text=window,
                    token_count=len(window) // self._fallback_ratio,
                )
            )

            if i + char_size >= len(text):
                break

        return (
            chunks if chunks else [Chunk(event_id=event_id, seq=0, pos=0, text="", token_count=0)]
        )

    def _format_event(self, event: "Event") -> str:
        """
        格式化事件为可分块文本

        格式: type: {type} | time: {timestamp} | source: {source} | {content}
        """
        # 从 Event 对象提取字段
        event_type = getattr(event, "type", "unknown")
        if hasattr(event_type, "value"):
            event_type = event_type.value

        timestamp = getattr(event, "timestamp", "")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()

        source = getattr(event, "source", "unknown")
        if hasattr(source, "value"):
            source = source.value

        # 主要内容
        summary = getattr(event, "summary", "")
        content = getattr(event, "content", "")

        # 组合
        parts = [
            f"type: {event_type}",
            f"time: {timestamp}",
            f"source: {source}",
        ]

        if summary:
            parts.append(f"summary: {summary}")

        if content:
            parts.append(content)

        return " | ".join(parts[:3]) + "\n" + "\n".join(parts[3:])
