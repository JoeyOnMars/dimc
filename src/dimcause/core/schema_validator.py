"""
SchemaValidator - 本体验证器 (Layer 3)

在 EventIndex 写入层面部署硬核前导卡口，验证 Event.type 是否符合 ontology.yaml 定义。
"""

from dataclasses import dataclass
from typing import Optional, Set

from dimcause.core.models import Event
from dimcause.core.ontology import Ontology, get_ontology


class OntologySchemaError(Exception):
    """本体Schema验证异常 - 阻止非法Event类型入库"""

    def __init__(self, event_type: str, valid_types: Set[str]):
        self.event_type = event_type
        self.valid_types = valid_types
        super().__init__(
            f"Event type '{event_type}' 不符合本体定义。有效类型: {sorted(valid_types)}"
        )


@dataclass(frozen=True)
class LegacyTypePolicy:
    """受治理的 legacy 类型策略。"""

    canonical_class: Optional[str]
    status: str
    note: str
    allow_write: bool = True


@dataclass(frozen=True)
class ValidationResult:
    """Schema 验证结果，供上层写入 provenance。"""

    input_type: str
    ontology_class: Optional[str]
    is_legacy: bool
    policy: Optional[LegacyTypePolicy] = None


class LegacyTypeGovernanceError(OntologySchemaError):
    """Legacy 类型已登记但不再允许写入。"""

    def __init__(self, event_type: str, policy: LegacyTypePolicy, valid_types: Set[str]):
        self.policy = policy
        super().__init__(event_type, valid_types)
        self.args = (
            f"Legacy event type '{event_type}' 已进入治理阶段，不允许继续写入。"
            f" status={policy.status}, note={policy.note}",
        )


class SchemaValidator:
    """
    本体Schema验证器

    职责：
    1. 验证 Event.type 是否存在于 ontology.yaml 声明的 classes 集合中
    2. 处理 EventType 枚举值到 ontology 类名的映射（向下兼容）
    3. 拒绝未在本体中定义的垃圾事件类型
    """

    # EventType 枚举值到 ontology 类名的映射（向下兼容）
    # key: EventType 枚举的 value (小写)
    # value: ontology.yaml 中定义的类名
    TYPE_MAPPING = {
        "decision": "Decision",
        "requirement": "Requirement",
        "incident": "Incident",
        "experiment": "Experiment",
        "git_commit": "Commit",
        "commit": "Commit",
        "function": "Function",
        "code_change": "Function",  # 映射到 Function 类
    }

    # 向下兼容策略：历史类型不再是裸白名单，而是显式治理对象。
    LEGACY_POLICIES = {
        "diagnostic": LegacyTypePolicy(
            canonical_class="Incident",
            status="legacy-write",
            note="问题/报错链路仍在生产 diagnostic，待逐步收敛到 Incident。",
        ),
        "research": LegacyTypePolicy(
            canonical_class="Experiment",
            status="legacy-write",
            note="调研/试验类提取尚未完全切到 Experiment。",
        ),
        "discussion": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="导出/会话类事件仍使用 discussion 表达对话上下文。",
        ),
        "task": LegacyTypePolicy(
            canonical_class="Requirement",
            status="legacy-write",
            note="任务管理链路仍以 task 表示工作项，后续需和 Requirement 对齐。",
        ),
        "resource": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="外部文档/检索命中仍需要 resource 作为非本体事件容器。",
        ),
        "unknown": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="解析失败/未知类型兜底，后续应持续压缩占比。",
        ),
        "failed_attempt": LegacyTypePolicy(
            canonical_class="Experiment",
            status="legacy-write",
            note="失败方案仍作为独立事件类型存在，保留以承载失败记忆。",
        ),
        "abandoned_idea": LegacyTypePolicy(
            canonical_class="Experiment",
            status="legacy-write",
            note="放弃方案仍保留历史兼容，等待本体扩展或迁移策略明确。",
        ),
        "ai_conversation": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="完整对话上下文事件仍需要专门容器。",
        ),
        "reasoning": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="推理链事件尚未进入本体主类。",
        ),
        "convention": LegacyTypePolicy(
            canonical_class=None,
            status="legacy-write",
            note="项目约定类事件仍通过 legacy 类型承载。",
        ),
    }

    def __init__(self, ontology: Optional[Ontology] = None):
        """
        初始化验证器

        Args:
            ontology: Ontology 实例，默认使用全局单例
        """
        self.ontology = ontology or get_ontology()
        self._valid_types: Optional[Set[str]] = None

    @property
    def valid_types(self) -> Set[str]:
        """获取所有有效的事件类型（ontology + governed legacy types）"""
        if self._valid_types is None:
            # 从 ontology 获取类名
            ontology_types = set(self.ontology.list_class_names())
            legacy = set(self.LEGACY_POLICIES.keys())
            self._valid_types = ontology_types | legacy
        return self._valid_types

    @property
    def legacy_types(self) -> Set[str]:
        return set(self.LEGACY_POLICIES.keys())

    def is_legacy_type(self, type_value: str) -> bool:
        return type_value.lower() in self.LEGACY_POLICIES

    def describe_legacy_type(self, type_value: str) -> Optional[LegacyTypePolicy]:
        return self.LEGACY_POLICIES.get(type_value.lower())

    def _map_to_ontology_class(self, event_type: str) -> str:
        """
        将 EventType 枚举值映射到 ontology 类名

        Args:
            event_type: EventType 枚举的 value

        Returns:
            对应的 ontology 类名，如果无映射则返回原始值
        """
        # 尝试直接映射
        mapped = self.TYPE_MAPPING.get(event_type.lower())
        if mapped:
            return mapped

        # 无映射时返回首字母大写（尝试匹配 ontology 类名）
        return event_type.capitalize()

    def validate(self, event: Event) -> ValidationResult:
        """
        验证 Event 的类型是否符合本体定义

        Args:
            event: 待验证的 Event 对象

        Raises:
            OntologySchemaError: 当 Event.type 不在有效集合中时抛出
        """
        # 获取 event type（处理 Enum 和字符串两种情况）
        type_value = event.type.value if hasattr(event.type, "value") else str(event.type)

        return self.validate_type(type_value)

    def validate_type(self, type_value: str, raise_error: bool = True) -> bool | ValidationResult:
        """
        直接验证事件类型字符串是否符合本体定义

        Args:
            type_value: 事件类型字符串
            raise_error: 是否在验证失败时抛出异常，默认 True

        Returns:
            bool: 验证结果（当 raise_error=False 时）

        Raises:
            OntologySchemaError: 当类型不在有效集合中时抛出（当 raise_error=True 时）
        """
        # 映射到 ontology 类名
        ontology_class = self._map_to_ontology_class(type_value)

        # 检查是否在 ontology classes 中
        if self.ontology.get_class(ontology_class):
            return ValidationResult(
                input_type=type_value,
                ontology_class=ontology_class,
                is_legacy=False,
            )

        # 检查是否在 legacy registry 中
        policy = self.describe_legacy_type(type_value)
        if policy:
            if not policy.allow_write:
                if raise_error:
                    raise LegacyTypeGovernanceError(type_value, policy, self.valid_types)
                return False
            return ValidationResult(
                input_type=type_value,
                ontology_class=policy.canonical_class,
                is_legacy=True,
                policy=policy,
            )

        # 拒绝：不在 ontology 中，也不在 legacy whitelist 中
        if raise_error:
            raise OntologySchemaError(type_value, self.valid_types)
        return False

    def is_valid(self, event: Event) -> bool:
        """
        验证 Event 类型是否有效（不抛出异常）

        Args:
            event: 待验证的 Event 对象

        Returns:
            bool: True 表示有效，False 表示无效
        """
        try:
            self.validate(event)
            return True
        except OntologySchemaError:
            return False


# 全局单例
_validator: Optional[SchemaValidator] = None


def get_schema_validator() -> SchemaValidator:
    """获取全局 SchemaValidator 实例（单例模式）"""
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator
