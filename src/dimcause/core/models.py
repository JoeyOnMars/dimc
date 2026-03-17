"""
Dimcause v5.1 数据模型定义

基于 Pydantic v2，定义四层架构的核心数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dimcause.reasoning.causal import CausalLink

# =============================================================================
# Enums
# =============================================================================


class EventType(str, Enum):
    """Event 类型"""

    # 现有核心类型
    DECISION = "decision"  # 技术决策
    CODE_CHANGE = "code_change"  # 代码变更
    DIAGNOSTIC = "diagnostic"  # 诊断/调试
    RESEARCH = "research"  # 调研/学习
    DISCUSSION = "discussion"  # 讨论
    TASK = "task"  # 任务管理
    RESOURCE = "resource"  # 外部资源/文档
    UNKNOWN = "unknown"  # 无法分类

    # H2 新增类型 (Hybrid Timeline)
    FAILED_ATTEMPT = "failed_attempt"  # 失败尝试 - 记录未成功的方案
    ABANDONED_IDEA = "abandoned_idea"  # 被放弃的方案 - 为什么不选择某方案
    AI_CONVERSATION = "ai_conversation"  # AI 对话完整上下文
    REASONING = "reasoning"  # 推理过程 - 决策的思考链
    CONVENTION = "convention"  # 项目约定 - 团队/项目规范
    GIT_COMMIT = "git_commit"  # Git Commit - 从 Git 导入

    # Ontology 1.0 New Types
    INCIDENT = "incident"  # 事故/故障
    EXPERIMENT = "experiment"  # 实验/POC
    REQUIREMENT = "requirement"  # 需求


class CodeEntityType(str, Enum):
    """代码实体类型"""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"


class SourceType(str, Enum):
    """数据来源类型"""

    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    CONTINUE_DEV = "continue_dev"
    WINDSURF = "windsurf"
    MANUAL = "manual"
    FILE = "file"


# =============================================================================
# Layer 1: Raw Data
# =============================================================================


class RawData(BaseModel):
    """
    Layer 1 输出：原始对话数据

    由 Watcher 产生，传递给 Layer 2 处理
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="唯一标识，格式: {source}_{timestamp}")
    source: SourceType = Field(description="数据来源")
    timestamp: datetime = Field(description="捕获时间")
    content: str = Field(description="原始对话内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    # 可选：文件上下文
    files_mentioned: List[str] = Field(default_factory=list, description="提到的文件")
    project_path: Optional[str] = Field(default=None, description="项目路径")


# =============================================================================
# Layer 2: Structured Event
# =============================================================================


class Entity(BaseModel):
    """
    命名实体

    从对话中提取的关键实体（文件、函数、库等）
    """

    name: str = Field(description="实体名称")
    type: str = Field(description="实体类型：file, function, library, concept")
    context: Optional[str] = Field(default=None, description="上下文说明")

    def __hash__(self):
        return hash((self.name, self.type))

    def __eq__(self, other):
        if isinstance(other, Entity):
            return self.name == other.name and self.type == other.type
        return False


class CodeEntity(BaseModel):
    """
    Code实体（AST 分析结果）

    Dimcause 的核心差异化：代码级深度
    """

    name: str = Field(description="实体名称，如 'login', 'UserClass'")
    type: CodeEntityType = Field(description="实体类型")
    file: str = Field(description="所在文件，如 'auth.py'")
    line_start: int = Field(description="起始行号")
    line_end: int = Field(description="结束行号")
    signature: Optional[str] = Field(default=None, description="签名，如 'def login(user, pwd)'")
    docstring: Optional[str] = Field(default=None, description="文档字符串")
    imports: List[str] = Field(default_factory=list, description="依赖导入")
    language: str = Field(default="python", description="编程语言")

    @property
    def full_path(self) -> str:
        """完整路径，如 'auth.py:login'"""
        return f"{self.file}:{self.name}"


class Event(BaseModel):
    """
    Layer 2 输出：结构化事件

    由 Extractor 产生，传递给 Layer 3 存储
    """

    model_config = ConfigDict(frozen=False)

    # 基础字段
    id: str = Field(description="唯一标识")
    type: EventType = Field(description="事件类型")
    timestamp: datetime = Field(description="发生时间")
    summary: str = Field(description="一句话摘要（<50字）")

    # 内容
    content: str = Field(description="完整内容")
    raw_data_id: Optional[str] = Field(default=None, description="关联的原始数据 ID")

    # 提取的结构化信息
    entities: List[Entity] = Field(default_factory=list, description="提取的实体")
    code_entities: List[CodeEntity] = Field(default_factory=list, description="代码实体（AST）")
    tags: List[str] = Field(default_factory=list, description="标签")

    # 关系（用于图谱）
    related_files: List[str] = Field(default_factory=list, description="相关文件")
    related_event_ids: List[str] = Field(default_factory=list, description="相关事件 ID")

    # 元数据
    source: SourceType = Field(default=SourceType.CLAUDE_CODE)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="提取置信度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """验证 metadata 只包含 JSON-serializable 类型"""
        import json

        if not isinstance(v, dict):
            raise ValueError("metadata must be a dict")

        # 尝试 JSON 序列化以检查类型安全
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"metadata contains non-JSON-serializable values: {e}") from e

        return v

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        try:
            import frontmatter
        except ImportError:
            frontmatter = None

        metadata = {
            "id": self.id,
            "type": getattr(self.type, "value", str(self.type)),
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "tags": self.tags,
            "source": getattr(self.source, "value", str(self.source)),
            "confidence": self.confidence,
            "raw_data_id": self.raw_data_id,
            "related_files": self.related_files,
            "related_event_ids": self.related_event_ids,
            "entities": [entity.model_dump(mode="json") for entity in self.entities],
            "code_entities": [
                {
                    **entity.model_dump(mode="json"),
                    "full_path": entity.full_path,
                }
                for entity in self.code_entities
            ],
        }

        for key, value in self.metadata.items():
            if key not in metadata:
                metadata[key] = value

        clean_metadata = {
            key: value for key, value in metadata.items() if value not in (None, [], {})
        }
        body = f"# {self.summary}\n\n{self.content}" if self.summary else self.content

        if frontmatter is not None:
            post = frontmatter.Post(body, **clean_metadata)
            return frontmatter.dumps(post)

        import yaml

        return f"---\n{yaml.safe_dump(clean_metadata, sort_keys=False, allow_unicode=True)}---\n\n{body}"

    @staticmethod
    def from_markdown(content: str, file_path: Optional[str] = None) -> "Event":
        """
        从 Markdown 内容解析 Event

        优先使用 python-frontmatter，降级使用 regex
        """
        metadata = {}
        body = content

        try:
            import frontmatter

            post = frontmatter.loads(content)
            metadata = post.metadata
            body = post.content
        except (ImportError, Exception):
            # Fallback to regex if frontmatter fails (e.g., malformed YAML)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = parts[1]
                    body = parts[2]
                    try:
                        import yaml

                        metadata = yaml.safe_load(fm) or {}
                    except Exception:
                        for line in fm.split("\n"):
                            if ":" in line:
                                k, v = line.split(":", 1)
                                k = k.strip()
                                v = v.strip()
                                if v.startswith("[") and v.endswith("]"):
                                    v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                                metadata[k] = v

        # Ensure metadata values are JSON serializable (convert datetime to str)
        for k, v in metadata.items():
            if isinstance(v, datetime):
                metadata[k] = v.isoformat()
            elif hasattr(v, "isoformat"):
                metadata[k] = v.isoformat()

        if not isinstance(metadata, dict):
            metadata = {}

        # Extract fields
        evt_id = metadata.get("id", "unknown")
        if file_path and evt_id == "unknown":
            from pathlib import Path

            evt_id = Path(file_path).stem

        # Parse Type
        try:
            evt_type = EventType(metadata.get("type", "unknown"))
        except ValueError:
            evt_type = EventType.UNKNOWN

        # Parse Timestamp
        ts_val = metadata.get("timestamp")
        timestamp = datetime.now()

        if ts_val:
            if isinstance(ts_val, datetime):
                timestamp = ts_val
            elif isinstance(ts_val, str):
                try:
                    timestamp = datetime.fromisoformat(ts_val)
                except ValueError:
                    pass

        # Parse Tags
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            # Fallback if regex parser returned string
            tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]

        source_val = metadata.get("source", SourceType.CLAUDE_CODE.value)
        try:
            source = SourceType(source_val)
        except ValueError:
            source = SourceType.CLAUDE_CODE

        try:
            confidence = float(metadata.get("confidence", 1.0))
        except (TypeError, ValueError):
            confidence = 1.0

        raw_data_id = metadata.get("raw_data_id")

        related_files = metadata.get("related_files", [])
        if isinstance(related_files, str):
            related_files = [related_files]

        related_event_ids = metadata.get("related_event_ids", [])
        if isinstance(related_event_ids, str):
            related_event_ids = [related_event_ids]

        entities = []
        for item in metadata.get("entities", []) or []:
            if isinstance(item, dict):
                try:
                    entities.append(Entity.model_validate(item))
                except Exception:
                    continue

        code_entities = []
        for item in metadata.get("code_entities", []) or []:
            if isinstance(item, dict):
                try:
                    code_entities.append(CodeEntity.model_validate(item))
                except Exception:
                    continue

        # Generate Summary from Body if missing
        summary = metadata.get("summary")
        if not summary:
            # Try finding H1
            for line in body.split("\n"):
                if line.startswith("# "):
                    summary = line[2:].strip()
                    break
            if not summary:
                summary = body[:50].replace("\n", " ")

        heading = f"# {summary}"
        stripped_body = body.lstrip()
        if stripped_body.startswith(heading):
            stripped_body = stripped_body[len(heading) :].lstrip("\n")
            body = stripped_body.lstrip()

        reserved_keys = {
            "id",
            "type",
            "timestamp",
            "summary",
            "tags",
            "source",
            "confidence",
            "raw_data_id",
            "related_files",
            "related_event_ids",
            "entities",
            "code_entities",
        }
        extra_metadata = {k: v for k, v in metadata.items() if k not in reserved_keys}

        return Event(
            id=evt_id,
            type=evt_type,
            timestamp=timestamp,
            summary=summary,
            content=body,
            raw_data_id=raw_data_id,
            entities=entities,
            code_entities=code_entities,
            tags=tags,
            related_files=related_files,
            related_event_ids=related_event_ids,
            source=source,
            confidence=confidence,
            metadata=extra_metadata,
        )

    def to_jsonld(self) -> Dict[str, Any]:
        """生成 JSON-LD 表示"""
        from dimcause.core.ontology import get_ontology

        # 获取上下文定义
        context = get_ontology().get_jsonld_context().get("@context", {})

        # 基础结构
        data = {
            "@context": context,
            "@type": f"dev:{getattr(self.type, 'value', str(self.type)).capitalize()}",  # e.g., dev:Decision
            "@id": f"dev:event/{self.id}",  # Default URI if not SemanticEvent
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "source": getattr(self.source, "value", str(self.source)),
            "tags": self.tags,
            "content": self.content,
        }
        return data


class SemanticEvent(Event):
    """
    Phase 2: 增强的 SemanticEvent 模型，具备因果推理能力。
    继承自 Event 以确保向后兼容性。
    """

    uri: Optional[str] = Field(default=None, description="URI 标识符")
    causal_links: List[CausalLink] = Field(default_factory=list, description="因果关系链接")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文数据")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not self.uri:
            # 如果未提供 URI，则自动生成: dev://event/<hash>
            # 注意：EventIndex 中通常使用 Event.id，这里统一格式
            self.uri = f"dev://event/{self.id}"

    def to_jsonld(self) -> Dict[str, Any]:
        """生成 SemanticEvent 的 JSON-LD (包含因果关系)"""
        data = super().to_jsonld()

        # 覆盖 @id (如果有明确 URI)
        if self.uri:
            data["@id"] = self.uri

        # 添加因果关系
        # causal_links: List[CausalLink] -> relation: target_uri
        for link in self.causal_links:
            rel_key = link.relation  # e.g., "implements"
            if rel_key not in data:
                data[rel_key] = []

            # JSON-LD 中，关系通常指向 @id
            # 确保 target 是 URI 格式
            target_uri = link.target
            if not target_uri.startswith("dev://") and not target_uri.startswith("http"):
                # 假设是 ID，尝试构造 URI
                target_uri = f"dev:event/{target_uri}"

            data[rel_key].append({"@id": target_uri})

        # 展平单值列表 (可选，但 JSON-LD 推荐 compact)
        # 这里为了简单保持 list，或者根据 Ontology cardinality 处理

        return data


# =============================================================================
# Layer 3: Storage Models
# =============================================================================


class Fact(BaseModel):
    """
    知识点/事实

    从多个 Event 中提炼的持久化知识
    """

    id: str
    statement: str = Field(description="陈述，如 '选择 JWT 是因为移动端需要无状态认证'")
    source_events: List[str] = Field(description="来源 Event IDs")
    created_at: datetime
    updated_at: datetime
    confidence: float = Field(default=1.0)

    # 图谱关系
    related_entities: List[str] = Field(default_factory=list)
    contradicts: Optional[str] = Field(default=None, description="如果与其他 Fact 矛盾")


class SearchResult(BaseModel):
    """搜索结果"""

    event: Event
    score: float = Field(description="相关性分数")
    highlights: List[str] = Field(default_factory=list, description="高亮片段")
    match_type: str = Field(default="semantic", description="匹配类型")


# =============================================================================
# Configuration Models
# =============================================================================


class LLMConfig(BaseModel):
    """LLM 配置"""

    provider: str = Field(
        default="ollama", description="ollama, openai, anthropic, deepseek, gemini"
    )
    model: str = Field(default="qwen2:7b")
    base_url: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    temperature: float = Field(default=0.3)
    max_tokens: int = Field(default=1000)
    timeout: int = Field(default=30)


class WatcherConfig(BaseModel):
    """Watcher 配置"""

    enabled: bool = Field(default=True)
    path: str
    debounce_seconds: float = Field(default=1.0)


class DimcauseConfig(BaseModel):
    """Dimcause 完整配置"""

    # LLM
    llm_primary: LLMConfig = Field(default_factory=LLMConfig)
    llm_fallback: Optional[LLMConfig] = Field(default=None)

    # Watchers
    watcher_claude: WatcherConfig = Field(
        default_factory=lambda: WatcherConfig(path="~/.claude/history.jsonl")
    )
    watcher_cursor: Optional[WatcherConfig] = Field(default=None)
    watcher_continue_dev: Optional[WatcherConfig] = Field(default=None)
    watcher_state: Optional[WatcherConfig] = Field(default=None)
    watcher_windsurf: Optional[WatcherConfig] = Field(default=None)

    # Storage
    data_dir: str = Field(default="~/.dimcause")
    history_days: int = Field(default=30)

    # Privacy
    redact_api_keys: bool = Field(default=True)
    redact_passwords: bool = Field(default=True)
    local_only: bool = Field(default=True)


# =============================================================================
# AI Model Configuration (V5.2)
# See docs/research/RT-000_model_selection_evaluation.md for model choices.
# =============================================================================


class ModelStack(str, Enum):
    """
    模型栈选择 (Model Stack Selection)

    定义三种预配置模式，具体模型组合见 RT-000 模型选型评估。
    See docs/research/RT-000_model_selection_evaluation.md for details.
    """

    PERFORMANCE = "performance"  # 模式 A：高性能模式 (Jina v3 + BGE-M3 Rerank)
    TRUST = "trust"  # 模式 B：信创/安全模式 (BGE-M3 Full Stack)
    GEEK = "geek"  # 模式 C：极客/SOTA模式 (GTE-Qwen2 + BGE-M3)


DEFAULT_MODEL_STACK = (
    ModelStack.TRUST
)  # 默认模式：BGE-M3 全栈，本地离线可用；PERFORMANCE 模式需联网下载 Jina
DEFAULT_MODEL_CACHE_DIR = "~/.cache/dimcause/models"

# 模式 → 模型映射表 (与 docs/research/RT-000_model_selection_evaluation.md §9 保持一致)
_MODEL_STACK_MAP = {
    ModelStack.PERFORMANCE: {
        "embed_model": "jinaai/jina-embeddings-v3",
        "embed_dimension": 1024,
        "rerank_model": "BAAI/bge-reranker-v2-m3",
    },
    ModelStack.TRUST: {
        "embed_model": "BAAI/bge-m3",
        "embed_dimension": 1024,
        "rerank_model": "BAAI/bge-reranker-v2-m3",
    },
    ModelStack.GEEK: {
        "embed_model": "Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        "embed_dimension": 1536,
        "rerank_model": "BAAI/bge-reranker-v2-m3",
    },
}


class ModelConfig(BaseModel):
    """
    AI 模型配置数据结构 (V5.2)

    集中管理 Embedding / Reranker / Query Expansion 模型配置。
    具体模型名称和路径由 docs/research/RT-000_model_selection_evaluation.md 定义。

    规则约束 (from MODEL_SELECTION_RULES.md):
    - 业务代码禁止硬编码模型路径，必须通过 get_model_config() 获取。
    - 模式切换通过 stack 参数实现，不允许 if/else 散落在业务逻辑中。
    """

    stack: ModelStack = Field(default=DEFAULT_MODEL_STACK, description="模型栈模式")
    cache_dir: str = Field(default=DEFAULT_MODEL_CACHE_DIR, description="模型缓存目录")

    # Embedding 模型配置 (用于向量检索)
    embed_model: Optional[str] = Field(default=None, description="Embedding 模型名称/路径")
    embed_dimension: Optional[int] = Field(default=None, description="向量维度")

    # Reranker 模型配置 (用于结果重排序)
    # 约束: 只用于 Top-K 重排，禁止单独决定审计结论
    rerank_model: Optional[str] = Field(default=None, description="Reranker 模型名称/路径")

    # Query Expansion 模型配置 (用于查询扩展)
    # 约束: 仅限 dimc query 等检索命令，禁止在 dimc audit 中使用
    expansion_model: Optional[str] = Field(
        default=None, description="Query Expansion 模型名称/路径"
    )


def get_model_config(stack: Optional[ModelStack] = None) -> ModelConfig:
    """
    返回当前环境下的模型配置，根据 stack 自动填充模型字段。

    规则 (from MODEL_SELECTION_RULES.md):
    - 代码默认使用 PERFORMANCE 模式。
    - 16GB 机器用户建议通过环境变量切换到 TRUST 模式。
    - 具体模型组合与 docs/research/RT-000_model_selection_evaluation.md 保持一致。
    """
    import os

    # 环境变量覆盖
    env_stack = os.environ.get("DIMCAUSE_MODEL_STACK")
    if env_stack and stack is None:
        try:
            stack = ModelStack(env_stack.lower())
        except ValueError:
            pass  # 无效值则忽略

    if stack is None:
        stack = DEFAULT_MODEL_STACK

    # 从映射表填充模型配置
    stack_config = _MODEL_STACK_MAP.get(stack, _MODEL_STACK_MAP[DEFAULT_MODEL_STACK])

    return ModelConfig(
        stack=stack,
        embed_model=stack_config["embed_model"],
        embed_dimension=stack_config["embed_dimension"],
        rerank_model=stack_config["rerank_model"],
    )
