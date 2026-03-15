"""
Dimcause v5.1 Protocol 定义

所有组件必须实现这些 Protocol，确保：
1. 接口稳定：组件可独立开发
2. 类型安全：静态检查
3. 可测试：Mock 友好
"""

from datetime import datetime
from typing import TYPE_CHECKING, Callable, List, Optional, Protocol, runtime_checkable

# =============================================================================
# Layer 1: Ghost Mode Watchers
# =============================================================================


@runtime_checkable
class IWatcher(Protocol):
    """
    IDE 对话监听器接口

    实现类：
    - ClaudeWatcher: Claude Code 日志监听
    - CursorWatcher: Cursor 日志监听
    - WindsurfWatcher: Windsurf 日志监听
    """

    @property
    def name(self) -> str:
        """监听器名称，如 'claude', 'cursor'"""
        ...

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        ...

    def start(self) -> None:
        """启动监听"""
        ...

    def stop(self) -> None:
        """停止监听"""
        ...

    def on_new_data(self, callback: "Callable[[RawData], None]") -> None:
        """
        注册新数据回调

        Args:
            callback: 当检测到新对话时调用
        """
        ...


# =============================================================================
# Layer 2: LLM Refinery
# =============================================================================


@runtime_checkable
class ILLMClient(Protocol):
    """
    LLM 客户端接口

    支持多种后端：Ollama, OpenAI, Anthropic, DeepSeek 等
    """

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """
        单次 LLM 调用

        Args:
            prompt: 用户提示
            system: 系统提示（可选）

        Returns:
            LLM 响应文本
        """
        ...

    async def complete_async(self, prompt: str, system: Optional[str] = None) -> str:
        """异步版本"""
        ...

    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        ...


@runtime_checkable
class IExtractor(Protocol):
    """
    信息提取器接口

    从原始文本提取结构化 Event
    """

    def extract(self, content: str) -> "Event":
        """
        从原始文本提取 Event

        Args:
            content: 原始对话内容

        Returns:
            结构化 Event
        """
        ...

    def extract_batch(self, contents: List[str]) -> List["Event"]:
        """批量提取"""
        ...


@runtime_checkable
class IASTAnalyzer(Protocol):
    """
    AST 分析器接口

    从代码提取结构化 CodeEntity
    """

    def extract_functions(self, code: str, language: str) -> List["CodeEntity"]:
        """提取函数定义"""
        ...

    def extract_classes(self, code: str, language: str) -> List["CodeEntity"]:
        """提取类定义"""
        ...

    def extract_imports(self, code: str, language: str) -> List[str]:
        """提取导入依赖"""
        ...

    def supported_languages(self) -> List[str]:
        """返回支持的语言列表"""
        ...


# =============================================================================
# Layer 3: Hybrid Storage
# =============================================================================


@runtime_checkable
class IMarkdownStore(Protocol):
    """
    Markdown 日志存储接口

    人类可读的长期存储
    """

    def save(self, event: "Event") -> str:
        """
        保存 Event 到 Markdown 文件

        Returns:
            文件路径
        """
        ...

    def load(self, path: str) -> Optional["Event"]:
        """从文件加载 Event"""
        ...

    def list_by_date(self, start: datetime, end: datetime) -> List[str]:
        """按日期范围列出文件"""
        ...


@runtime_checkable
class IVectorStore(Protocol):
    """
    向量数据库接口

    语义搜索
    """

    def add(self, event: "Event") -> str:
        """
        添加 Event 到向量库

        Returns:
            向量 ID
        """
        ...

    def search(self, query: str, top_k: int = 10) -> List["Event"]:
        """语义搜索"""
        ...

    def delete(self, event_id: str) -> bool:
        """删除 Event"""
        ...


@runtime_checkable
class IGraphStore(Protocol):
    """
    知识图谱接口

    关系查询
    """

    def add_entity(self, entity: "Entity") -> None:
        """添加实体"""
        ...

    def add_structural_relation(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        metadata=None,
    ) -> None:
        """添加结构边（白名单校验：calls/imports/contains/depends_on）"""
        ...

    def find_related(self, entity_name: str, depth: int = 1) -> List["Entity"]:
        """查找相关实体"""
        ...

    def find_experts(self, file_path: str) -> List[str]:
        """查找文件专家（修改过该文件的开发者）"""
        ...


# =============================================================================
# Layer 4: Query Interface
# =============================================================================


@runtime_checkable
class ISearchEngine(Protocol):
    """
    统一搜索引擎接口

    聚合多种搜索方式
    """

    def search(
        self,
        query: str,
        mode: str = "hybrid",  # "text", "semantic", "graph", "hybrid"
        top_k: int = 10,
    ) -> List["Event"]:
        """
        统一搜索接口

        Args:
            query: 搜索词
            mode: 搜索模式
            top_k: 返回数量

        Returns:
            匹配的 Events
        """
        ...

    def trace(self, file_path: str, function_name: Optional[str] = None) -> List["Event"]:
        """
        追溯代码历史

        Args:
            file_path: 文件路径
            function_name: 函数名（可选）

        Returns:
            相关的修改历史
        """
        ...


# =============================================================================
# Type Hints（前向引用）
# =============================================================================


if TYPE_CHECKING:
    from dimcause.core.models import CodeEntity, Entity, Event, RawData
