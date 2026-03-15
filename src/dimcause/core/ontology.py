"""
Trax 本体引擎 (Ontology Engine)

加载和验证Dev-Ontology定义，为V6.0因果推理提供理论基础。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class OntologyClass:
    """本体类定义"""

    name: str
    description: str
    uri_prefix: str
    properties: Dict[str, dict] = field(default_factory=dict)


@dataclass
class OntologyRelation:
    """本体关系定义"""

    name: str
    description: str
    domain: str  # 域（主语）
    range: str  # 值域（宾语）
    cardinality: str  # 基数 (one-to-one, one-to-many, many-to-many)
    inverse: Optional[str] = None
    semantics: str = ""


@dataclass
class OntologyAxiom:
    """本体公理定义"""

    id: str
    description: str
    severity: str  # error | warning
    check_type: str  # existence | graph_topology | path_existence
    rule: str
    error_message: str


class Ontology:
    """
    Dimcause 本体引擎 (Ontology Engine)

    用途:
    1. 加载ontology.yaml定义
    2. 验证事件关系是否符合本体约束
    3. 为JSON-LD导出提供@context
    """

    def __init__(self, ontology_file: Optional[Path] = None):
        """
        初始化本体

        Args:
            ontology_file: ontology.yaml文件路径，默认使用内置路径
        """
        if ontology_file is None:
            # 默认路径: src/dimcause/core/ontology.yaml
            ontology_file = Path(__file__).parent / "ontology.yaml"

        self.ontology_file = ontology_file
        self.classes: Dict[str, OntologyClass] = {}
        self.relations: Dict[str, OntologyRelation] = {}
        self.axioms: Dict[str, OntologyAxiom] = {}
        self.jsonld_context: dict = {}
        self.namespace: str = ""

        self._load()

    def _load(self):
        """从YAML文件加载本体定义"""
        if not self.ontology_file.exists():
            raise FileNotFoundError(f"本体定义文件不存在: {self.ontology_file}")

        with open(self.ontology_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.namespace = data.get("namespace", "")

        # 加载类定义
        for cls_data in data.get("classes", []):
            cls = OntologyClass(
                name=cls_data["name"],
                description=cls_data["description"],
                uri_prefix=cls_data["uri_prefix"],
                properties=cls_data.get("properties", {}),
            )
            self.classes[cls.name] = cls

        # 加载关系定义
        for rel_data in data.get("relations", []):
            rel = OntologyRelation(
                name=rel_data["name"],
                description=rel_data["description"],
                domain=rel_data["domain"],
                range=rel_data["range"],
                cardinality=rel_data["cardinality"],
                inverse=rel_data.get("inverse"),
                semantics=rel_data.get("semantics", ""),
            )
            self.relations[rel.name] = rel

        # 加载公理定义
        for axiom_data in data.get("axioms", []):
            axiom = OntologyAxiom(
                id=axiom_data["id"],
                description=axiom_data["description"],
                severity=axiom_data["severity"],
                check_type=axiom_data["check_type"],
                rule=axiom_data["rule"],
                error_message=axiom_data["error_message"],
            )
            self.axioms[axiom.id] = axiom

        # 加载JSON-LD上下文
        self.jsonld_context = data.get("jsonld_context", {})

    def get_class(self, class_name: str) -> Optional[OntologyClass]:
        """获取类定义"""
        return self.classes.get(class_name)

    def get_relation(self, relation_name: str) -> Optional[OntologyRelation]:
        """获取关系定义"""
        return self.relations.get(relation_name)

    def get_axiom(self, axiom_id: str) -> Optional[OntologyAxiom]:
        """获取公理定义"""
        return self.axioms.get(axiom_id)

    def validate_relation(
        self, relation_name: str, source_class: str, target_class: str
    ) -> tuple[bool, str]:
        """
        验证关系是否符合本体定义

        Args:
            relation_name: 关系名称
            source_class: 源节点类名 (域)
            target_class: 目标节点类名 (值域)

        Returns:
            (是否有效, 错误信息)
        """
        relation = self.get_relation(relation_name)
        if not relation:
            return False, f"未定义的关系: {relation_name}"

        if relation.domain != source_class:
            return False, (
                f"关系 {relation_name} 的域应为 {relation.domain}，实际为 {source_class}"
            )

        if relation.range != target_class:
            return False, (
                f"关系 {relation_name} 的值域应为 {relation.range}，实际为 {target_class}"
            )

        return True, ""

    def list_valid_relations(self, source_class: str) -> List[str]:
        """列出从某个类出发的所有有效关系"""
        return [name for name, rel in self.relations.items() if rel.domain == source_class]

    def list_class_names(self) -> List[str]:
        """列出所有类名"""
        return list(self.classes.keys())

    def list_relation_names(self) -> List[str]:
        """列出所有关系名"""
        return list(self.relations.keys())

    def get_jsonld_context(self) -> dict:
        """获取JSON-LD上下文（用于导出）"""
        return self.jsonld_context

    def __repr__(self) -> str:
        return (
            f"<Ontology: {len(self.classes)} classes, "
            f"{len(self.relations)} relations, "
            f"{len(self.axioms)} axioms>"
        )


# 全局单例
_ontology_instance: Optional[Ontology] = None


def get_ontology() -> Ontology:
    """
    获取全局本体实例（单例模式）

    用途: 在整个应用中共享同一份本体定义
    """
    global _ontology_instance
    if _ontology_instance is None:
        _ontology_instance = Ontology()
    return _ontology_instance


def reload_ontology(ontology_file: Optional[Path] = None):
    """
    重新加载本体定义（用于测试或动态更新）

    Args:
        ontology_file: 可选的YAML文件路径
    """
    global _ontology_instance
    _ontology_instance = Ontology(ontology_file)
