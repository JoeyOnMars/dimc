"""
Architecture Validator - 架构约束验证

对标 BCC 的架构约束验证机制
支持:
- layer_compliance: 分层合规
- dependency_direction: 依赖方向
- forbidden: 禁止依赖
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class RuleType(Enum):
    """规则类型"""

    LAYER_COMPLIANCE = "layer_compliance"
    DEPENDENCY_DIRECTION = "dependency_direction"
    FORBIDDEN = "forbidden"


@dataclass
class ArchRule:
    """架构规则"""

    type: str  # "layer_compliance" | "dependency_direction" | "forbidden"
    source: str  # 源模块（支持通配符 *）
    target: str  # 目标模块
    description: str
    layer_order: Optional[Dict[str, int]] = None  # 层叠顺序，用于 layer_compliance

    def matches(self, source: str, target: str) -> bool:
        """检查是否匹配"""
        # 支持通配符 *（source 和 target 端都支持）
        source_match = self.source == "*" or self.source == source
        target_match = self.target == "*" or self.target == target
        return source_match and target_match

    def validate_layer_compliance(self, source: str, target: str) -> Optional[str]:
        """
        验证层级合规性
        返回违规消息，无违规返回 None
        """
        if self.type != RuleType.LAYER_COMPLIANCE.value:
            return None
        if not self.layer_order:
            return None

        source_layer = self.layer_order.get(source)
        target_layer = self.layer_order.get(target)

        if source_layer is None or target_layer is None:
            return None

        # layers: [api, service, dao] -> api=0, service=1, dao=2
        # 越靠前数字越小（外层），越靠后数字越大（内层）
        # 只能外层依赖内层：api(0) -> service(1) -> dao(2) 是合法的
        # 内层不能依赖外层：dao(2) -> service(1) -> api(0) 是非法的
        # 所以 source_layer > target_layer 是违规
        if source_layer > target_layer:
            return f"Layer violation: {source} (layer {source_layer}) cannot depend on {target} (layer {target_layer}) - can only depend on same or outer layers"

        return None


@dataclass
class ArchViolation:
    """架构违规"""

    rule: ArchRule
    source: str
    target: str
    message: str


@dataclass
class LayerConfig:
    """层叠架构配置"""

    layers: List[Dict[str, Any]]
    layer_order: Dict[str, int]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerConfig":
        layers = data.get("layers", [])
        # 越靠前数字越小（外层），越靠后数字越大（内层）
        # 例如 layers: [api, service, dao] -> api=0, service=1, dao=2
        layer_order = {layer["name"]: i for i, layer in enumerate(layers)}
        return cls(layers=layers, layer_order=layer_order)


def load_rules_from_yaml(path: str) -> List[ArchRule]:
    """从 YAML 文件加载架构规则"""
    rules = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return rules

        # 支持两种格式：
        # 1. rules: [{type, source, target, description}, ...]
        # 2. layers: [{name, allowed: [deps]}]

        if "rules" in data:
            for rule_data in data["rules"]:
                rules.append(
                    ArchRule(
                        type=rule_data.get("type", "forbidden"),
                        source=rule_data.get("source", "*"),
                        target=rule_data.get("target", "*"),
                        description=rule_data.get("description", ""),
                    )
                )

        elif "layers" in data:
            # 层叠架构格式
            layer_config = LayerConfig.from_dict(data)

            for layer in layer_config.layers:
                layer_name = layer["name"]
                allowed = layer.get("allowed", [])

                for allowed_target in allowed:
                    rules.append(
                        ArchRule(
                            type=RuleType.LAYER_COMPLIANCE.value,
                            source=layer_name,
                            target=allowed_target,
                            description=f"{layer_name} can depend on {allowed_target}",
                            layer_order=layer_config.layer_order,
                        )
                    )

    except FileNotFoundError:
        logger.warning(f"Architecture rules file not found: {path}")
    except Exception as e:
        logger.warning(f"Failed to load architecture rules: {e}")

    return rules


def validate_architecture(
    actual_deps: Dict[str, set], rules: List[ArchRule]
) -> List[ArchViolation]:
    """
    验证架构合规性

    Args:
        actual_deps: {module: {dependencies}} - 实际依赖关系
        rules: 架构规则列表

    Returns:
        List[ArchViolation] - 违规列表
    """
    violations = []

    for source, targets in actual_deps.items():
        for target in targets:
            for rule in rules:
                if rule.matches(source, target):
                    if rule.type == RuleType.FORBIDDEN.value:
                        violations.append(
                            ArchViolation(
                                rule=rule,
                                source=source,
                                target=target,
                                message=f"Forbidden: {source} -> {target}: {rule.description}",
                            )
                        )
                    elif rule.type == RuleType.LAYER_COMPLIANCE.value:
                        # 验证层级方向
                        violation_msg = rule.validate_layer_compliance(source, target)
                        if violation_msg:
                            violations.append(
                                ArchViolation(
                                    rule=rule, source=source, target=target, message=violation_msg
                                )
                            )

    return violations


def build_dependency_graph(dependencies: List[tuple]) -> Dict[str, set]:
    """
    从依赖列表构建依赖图

    Args:
        dependencies: [(source, target, type), ...]

    Returns:
        {source: {targets}}
    """
    graph: Dict[str, set] = {}

    for source, target, dep_type in dependencies:
        if dep_type == "imports":
            # 提取模块名
            source_module = _normalize_module(source)
            target_module = _normalize_module(target)

            if source_module and target_module:
                if source_module not in graph:
                    graph[source_module] = set()
                graph[source_module].add(target_module)

    return graph


def _normalize_module(entity_id: str) -> Optional[str]:
    """标准化模块名"""
    if not entity_id:
        return None

    # 文件路径
    if entity_id.endswith(".py"):
        return entity_id.replace("\\", "/").split("/")[-1].replace(".py", "")

    return entity_id


# 便捷函数
class ArchitectureValidator:
    """架构验证器"""

    def __init__(self, rules_path: Optional[str] = None):
        self.rules: List[ArchRule] = []
        if rules_path:
            self.load_rules(rules_path)

    def load_rules(self, path: str) -> None:
        """加载规则"""
        self.rules = load_rules_from_yaml(path)

    def validate(self, dependencies: List[tuple]) -> List[ArchViolation]:
        """验证依赖"""
        graph = build_dependency_graph(dependencies)
        return validate_architecture(graph, self.rules)

    def add_rule(self, rule: ArchRule) -> None:
        """添加规则"""
        self.rules.append(rule)
