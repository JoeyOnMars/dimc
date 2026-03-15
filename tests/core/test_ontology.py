"""
Trax 本体引擎单元测试

测试本体加载、验证和查询功能
"""

import pytest

from dimcause.core.ontology import (
    Ontology,
    get_ontology,
    reload_ontology,
)


class TestOntologyLoading:
    """测试本体加载功能"""

    def test_load_from_default_path(self):
        """测试从默认路径加载本体"""
        onto = Ontology()

        # 验证基础结构
        assert len(onto.classes) == 7, "应包含7个类定义"
        assert len(onto.relations) == 7, "应包含7个关系定义"
        assert len(onto.axioms) == 3, "应包含3个公理定义"
        assert onto.namespace == "https://schema.dimcause.dev/v1#", "Namespace 应为 Dimcause"

    def test_class_definitions(self):
        """测试类定义加载"""
        onto = Ontology()

        # 验证Requirement类
        req_class = onto.get_class("Requirement")
        assert req_class is not None
        assert req_class.name == "Requirement"
        assert req_class.uri_prefix == "dev://requirement/"
        assert "summary" in req_class.properties

        # 验证Decision类
        dec_class = onto.get_class("Decision")
        assert dec_class is not None
        assert dec_class.name == "Decision"

        # 验证Commit类
        commit_class = onto.get_class("Commit")
        assert commit_class is not None
        assert "hash" in commit_class.properties

    def test_relation_definitions(self):
        """测试关系定义加载"""
        onto = Ontology()

        # 验证implements关系
        impl_rel = onto.get_relation("implements")
        assert impl_rel is not None
        assert impl_rel.domain == "Decision"
        assert impl_rel.range == "Requirement"
        assert impl_rel.inverse == "implemented_by"

        # 验证realizes关系
        real_rel = onto.get_relation("realizes")
        assert real_rel is not None
        assert real_rel.domain == "Commit"
        assert real_rel.range == "Decision"

    def test_axiom_definitions(self):
        """测试公理定义加载"""
        onto = Ontology()

        # 验证commit_must_have_cause公理
        axiom = onto.get_axiom("commit_must_have_cause")
        assert axiom is not None
        assert axiom.severity == "warning"
        assert axiom.check_type == "existence"

        # 验证no_decision_cycle公理
        cycle_axiom = onto.get_axiom("no_decision_cycle")
        assert cycle_axiom is not None
        assert cycle_axiom.severity == "error"


class TestOntologyValidation:
    """测试本体验证功能"""

    def test_valid_relation(self):
        """测试有效关系验证"""
        onto = Ontology()

        # Commit realizes Decision 是有效的
        valid, msg = onto.validate_relation("realizes", "Commit", "Decision")
        assert valid, f"应通过验证: {msg}"

    def test_invalid_relation_name(self):
        """测试未定义的关系"""
        onto = Ontology()

        valid, msg = onto.validate_relation("nonexistent", "Commit", "Decision")
        assert not valid
        assert "未定义的关系" in msg

    def test_invalid_domain(self):
        """测试错误的域"""
        onto = Ontology()

        # realizes的域应该是Commit，不是Decision
        valid, msg = onto.validate_relation(
            "realizes",
            "Decision",  # 错误的域
            "Decision",
        )
        assert not valid
        assert "域应为" in msg

    def test_invalid_range(self):
        """测试错误的值域"""
        onto = Ontology()

        # realizes的值域应该是Decision，不是Requirement
        valid, msg = onto.validate_relation(
            "realizes",
            "Commit",
            "Requirement",  # 错误的值域
        )
        assert not valid
        assert "值域应为" in msg


class TestOntologyQueries:
    """测试本体查询功能"""

    def test_list_valid_relations(self):
        """测试列出有效关系"""
        onto = Ontology()

        # Commit可以有的关系
        commit_relations = onto.list_valid_relations("Commit")
        assert "realizes" in commit_relations
        assert "modifies" in commit_relations
        assert "fixes" in commit_relations

        # Decision可以有的关系
        decision_relations = onto.list_valid_relations("Decision")
        assert "implements" in decision_relations
        assert "overrides" in decision_relations

    def test_list_all_classes(self):
        """测试列出所有类"""
        onto = Ontology()

        class_names = onto.list_class_names()
        assert "Requirement" in class_names
        assert "Decision" in class_names
        assert "Commit" in class_names
        assert "Function" in class_names
        assert "Incident" in class_names
        assert "Experiment" in class_names

    def test_list_all_relations(self):
        """测试列出所有关系"""
        onto = Ontology()

        relation_names = onto.list_relation_names()
        assert "implements" in relation_names
        assert "realizes" in relation_names
        assert "modifies" in relation_names
        assert "triggers" in relation_names
        assert "validates" in relation_names
        assert "overrides" in relation_names
        assert "fixes" in relation_names


class TestJSONLDContext:
    """测试JSON-LD上下文"""

    def test_jsonld_context_exists(self):
        """测试JSON-LD上下文是否存在"""
        onto = Ontology()

        context = onto.get_jsonld_context()
        assert "@context" in context
        assert "dev" in context["@context"]
        assert "prov" in context["@context"]

    def test_jsonld_class_mappings(self):
        """测试JSON-LD类映射"""
        onto = Ontology()

        context = onto.get_jsonld_context()["@context"]
        assert context["Requirement"] == "dev:Requirement"
        assert context["Decision"] == "dev:Decision"
        assert context["Commit"] == "dev:Commit"

    def test_jsonld_relation_mappings(self):
        """测试JSON-LD关系映射"""
        onto = Ontology()

        context = onto.get_jsonld_context()["@context"]
        assert "implements" in context
        assert context["implements"]["@id"] == "dev:implements"
        assert context["realizes"]["@id"] == "dev:realizes"


class TestSingletonPattern:
    """测试单例模式"""

    def test_get_ontology_returns_singleton(self):
        """测试get_ontology返回单例"""
        onto1 = get_ontology()
        onto2 = get_ontology()

        # 应该是同一个对象
        assert onto1 is onto2

    def test_reload_ontology(self):
        """测试重新加载本体"""
        # 第一次获取
        onto1 = get_ontology()
        initial_classes = len(onto1.classes)

        # 重新加载
        reload_ontology()
        onto2 = get_ontology()

        # 应该是新的实例
        assert onto1 is not onto2
        # 但内容应该相同
        assert len(onto2.classes) == initial_classes


class TestOntologyRepr:
    """测试字符串表示"""

    def test_repr(self):
        """测试__repr__方法"""
        onto = Ontology()
        repr_str = repr(onto)

        assert "7 classes" in repr_str
        assert "7 relations" in repr_str
        assert "3 axioms" in repr_str


@pytest.mark.integration
class TestRealWorldScenarios:
    """测试真实世界场景"""

    def test_commit_realizes_decision_workflow(self):
        """测试Commit实现Decision的工作流"""
        onto = Ontology()

        # 1. 验证Decision可以implements Requirement
        valid, _ = onto.validate_relation("implements", "Decision", "Requirement")
        assert valid

        # 2. 验证Commit可以realizes Decision
        valid, _ = onto.validate_relation("realizes", "Commit", "Decision")
        assert valid

        # 3. 验证Commit可以modifies Function
        valid, _ = onto.validate_relation("modifies", "Commit", "Function")
        assert valid

    def test_incident_triggers_decision_workflow(self):
        """测试Incident触发Decision的工作流"""
        onto = Ontology()

        # 1. Incident triggers Decision
        valid, _ = onto.validate_relation("triggers", "Incident", "Decision")
        assert valid

        # 2. Decision可能overrides之前的Decision
        valid, _ = onto.validate_relation("overrides", "Decision", "Decision")
        assert valid

        # 3. 新的Commit fixes Incident
        valid, _ = onto.validate_relation("fixes", "Commit", "Incident")
        assert valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
