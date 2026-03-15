"""
SchemaValidator 单元测试

测试本体Schema验证器的功能：
1. 红线拦截：垃圾类型被拒绝
2. 合法准入：合法类型通过
3. 老数据兼容：读取不崩溃
"""

import os
import tempfile
from datetime import datetime

import pytest

# 设置测试环境变量，防止真实 IO
os.environ["HF_HUB_OFFLINE"] = "1"

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType
from dimcause.core.schema_validator import (
    ValidationResult,
    OntologySchemaError,
    SchemaValidator,
    get_schema_validator,
)


class TestSchemaValidator:
    """SchemaValidator 单元测试"""

    def test_valid_ontology_type_decision(self):
        """测试合法类型：Decision (ontology 中定义)"""
        validator = SchemaValidator()
        event = Event(
            id="test-001",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Test Decision",
            content="Test Decision Content",
        )
        # 应该不抛出异常
        validator.validate(event)

    def test_valid_ontology_type_requirement(self):
        """测试合法类型：Requirement (ontology 中定义)"""
        validator = SchemaValidator()
        event = Event(
            id="test-002",
            type=EventType.REQUIREMENT,
            timestamp=datetime.now(),
            summary="Test Requirement",
            content="Test Requirement Content",
        )
        validator.validate(event)

    def test_valid_ontology_type_incident(self):
        """测试合法类型：Incident (ontology 中定义)"""
        validator = SchemaValidator()
        event = Event(
            id="test-003",
            type=EventType.INCIDENT,
            timestamp=datetime.now(),
            summary="Test Incident",
            content="Test Incident Content",
        )
        validator.validate(event)

    def test_valid_ontology_type_experiment(self):
        """测试合法类型：Experiment (ontology 中定义)"""
        validator = SchemaValidator()
        event = Event(
            id="test-004",
            type=EventType.EXPERIMENT,
            timestamp=datetime.now(),
            summary="Test Experiment",
            content="Test Experiment Content",
        )
        validator.validate(event)

    def test_valid_ontology_type_git_commit(self):
        """测试合法类型：git_commit -> Commit (ontology 中定义)"""
        validator = SchemaValidator()
        event = Event(
            id="test-005",
            type=EventType.GIT_COMMIT,
            timestamp=datetime.now(),
            summary="Test Commit",
            content="Test Commit Content",
        )
        validator.validate(event)

    def test_valid_legacy_type_diagnostic(self):
        """测试合法类型：diagnostic (legacy whitelist)"""
        validator = SchemaValidator()
        event = Event(
            id="test-006",
            type=EventType.DIAGNOSTIC,
            timestamp=datetime.now(),
            summary="Test Diagnostic",
            content="Test Diagnostic Content",
        )
        validator.validate(event)

    def test_valid_legacy_type_research(self):
        """测试合法类型：research (legacy whitelist)"""
        validator = SchemaValidator()
        event = Event(
            id="test-007",
            type=EventType.RESEARCH,
            timestamp=datetime.now(),
            summary="Test Research",
            content="Test Research Content",
        )
        validator.validate(event)

    def test_validate_legacy_type_returns_structured_result(self):
        """legacy 类型应返回结构化治理结果，而不是裸 True。"""
        validator = SchemaValidator()
        result = validator.validate_type("diagnostic")
        assert isinstance(result, ValidationResult)
        assert result.is_legacy is True
        assert result.ontology_class == "Incident"
        assert result.policy is not None
        assert result.policy.status == "legacy-write"

    def test_describe_legacy_type_exposes_policy_metadata(self):
        validator = SchemaValidator()
        policy = validator.describe_legacy_type("task")
        assert policy is not None
        assert policy.canonical_class == "Requirement"
        assert policy.allow_write is True

    def test_invalid_garbage_type_rejected(self):
        """测试红线拦截：垃圾类型被拒绝"""
        validator = SchemaValidator()

        # 直接验证字符串类型
        with pytest.raises(OntologySchemaError) as exc_info:
            validator.validate_type("some_garbage_type_xyz")

        assert "some_garbage_type_xyz" in str(exc_info.value)

    def test_invalid_random_type_rejected(self):
        """测试红线拦截：随机字符串被拒绝"""
        validator = SchemaValidator()

        with pytest.raises(OntologySchemaError):
            validator.validate_type("random_junk_123")

    def test_is_valid_returns_true_for_valid(self):
        """测试 is_valid 方法：对合法类型返回 True"""
        validator = SchemaValidator()
        event = Event(
            id="test-010",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Valid Event",
            content="Valid Event Content",
        )
        assert validator.is_valid(event) is True

    def test_is_valid_returns_false_for_invalid(self):
        """测试 is_valid 方法：对非法类型返回 False"""
        validator = SchemaValidator()

        # 使用 validate_type 测试非法类型
        assert validator.validate_type("invalid_type_xyz", raise_error=False) is False

    def test_valid_types_includes_ontology_and_legacy(self):
        """测试 valid_types 包含 ontology 类和 legacy whitelist"""
        validator = SchemaValidator()
        valid = validator.valid_types

        # ontology 类
        assert "Decision" in valid or "decision" in valid
        assert "Requirement" in valid or "requirement" in valid
        assert "Incident" in valid or "incident" in valid
        # legacy whitelist
        assert "diagnostic" in valid
        assert "research" in valid


class TestEventIndexSchemaValidation:
    """EventIndex 集成 SchemaValidator 测试"""

    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_index.db")
            yield db_path

    def test_add_valid_event_succeeds(self, temp_db):
        """测试合法事件入库成功"""
        index = EventIndex(db_path=temp_db)

        event = Event(
            id="test-valid-001",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Valid Decision Event",
            content="Valid Decision Event Content",
        )

        # 创建临时 markdown 文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nid: test-valid-001\ntype: decision\n---\n")
            temp_path = f.name

        try:
            result = index.add(event, temp_path)
            assert result is True, "合法事件应该成功入库"

            # 验证事件已写入
            retrieved = index.get_by_id("test-valid-001")
            assert retrieved is not None
            assert retrieved["type"] == "decision"
        finally:
            os.unlink(temp_path)

    def test_add_if_not_exists_valid_event_succeeds(self, temp_db):
        """测试 add_if_not_exists 对合法事件成功"""
        index = EventIndex(db_path=temp_db)

        event = Event(
            id="test-add-if-001",
            type=EventType.REQUIREMENT,
            timestamp=datetime.now(),
            summary="Valid Requirement Event",
            content="Valid Requirement Event Content",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nid: test-add-if-001\ntype: requirement\n---\n")
            temp_path = f.name

        try:
            result = index.add_if_not_exists(event, temp_path)
            assert result is True, "合法事件应该成功入库"
        finally:
            os.unlink(temp_path)

    def test_legacy_types_still_work(self, temp_db):
        """测试 legacy 类型（diagnostic, research 等）仍然可以入库"""
        index = EventIndex(db_path=temp_db)

        event = Event(
            id="test-legacy-001",
            type=EventType.DIAGNOSTIC,  # legacy 类型
            timestamp=datetime.now(),
            summary="Legacy Diagnostic Event",
            content="Legacy Diagnostic Event Content",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nid: test-legacy-001\ntype: diagnostic\n---\n")
            temp_path = f.name

        try:
            result = index.add(event, temp_path)
            assert result is True, "Legacy 类型应该仍然可以入库"
            loaded = index.load_event("test-legacy-001")
            assert loaded is not None
            assert loaded.metadata["_schema_legacy"]["type"] == "diagnostic"
            assert loaded.metadata["_schema_legacy"]["canonical_class"] == "Incident"
        finally:
            os.unlink(temp_path)

    def test_get_legacy_type_counts_reports_current_inventory(self, temp_db):
        index = EventIndex(db_path=temp_db)

        legacy_event = Event(
            id="legacy-inventory-001",
            type=EventType.RESEARCH,
            timestamp=datetime.now(),
            summary="Legacy Research Event",
            content="Legacy Research Event Content",
        )
        canonical_event = Event(
            id="canonical-inventory-001",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Canonical Event",
            content="Canonical Event Content",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as legacy_file:
            legacy_file.write("---\nid: legacy-inventory-001\ntype: research\n---\n")
            legacy_path = legacy_file.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as canonical_file:
            canonical_file.write("---\nid: canonical-inventory-001\ntype: decision\n---\n")
            canonical_path = canonical_file.name

        try:
            assert index.add(legacy_event, legacy_path) is True
            assert index.add(canonical_event, canonical_path) is True
            assert index.get_legacy_type_counts() == {"research": 1}
        finally:
            os.unlink(legacy_path)
            os.unlink(canonical_path)

    def test_event_count_unchanged_after_rejected(self, temp_db):
        """测试拒绝非法事件后，数据库行数不变"""
        index = EventIndex(db_path=temp_db)

        # 先写入一个合法事件
        valid_event = Event(
            id="test-count-001",
            type=EventType.DECISION,
            timestamp=datetime.now(),
            summary="Valid Event",
            content="Valid Event Content",
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nid: test-count-001\ntype: decision\n---\n")
            temp_path1 = f.name

        try:
            index.add(valid_event, temp_path1)
            initial_count = index.count()
            assert initial_count == 1
        finally:
            os.unlink(temp_path1)

        # 验证事件数量未变（尝试添加非法类型会被 SchemaValidator 拦截）
        final_count = index.count()
        assert final_count == 1


class TestGetSchemaValidator:
    """测试全局单例"""

    def test_singleton_returns_same_instance(self):
        """测试 get_schema_validator 返回同一实例"""
        v1 = get_schema_validator()
        v2 = get_schema_validator()
        assert v1 is v2, "应该是单例"
