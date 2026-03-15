# -*- coding: utf-8 -*-
"""
Test JSON-LD Export
"""

import json

from typer.testing import CliRunner

from dimcause.cli import app
from dimcause.storage.graph_store import GraphStore

runner = CliRunner()


def test_export_jsonld(tmp_path):
    """测试 JSON-LD 导出功能"""
    db_path = tmp_path / "test_export.db"
    out_path = tmp_path / "export.jsonld"

    # 1. 准备数据
    store = GraphStore(db_path=str(db_path))

    # 添加几个节点
    store.add_entity("evt_001", "decision", summary="选择 SQLite", timestamp="2026-02-14T10:00:00")
    store.add_entity("req_001", "requirement", summary="本地优先", timestamp="2026-02-14T09:00:00")

    # 添加关系
    # [TEST_FIX_REASON] add_relation 废除，"implements" 非结构边白名单，改用 _internal_add_relation。
    store._internal_add_relation("evt_001", "req_001", "implements")

    # 2. 运行导出命令
    result = runner.invoke(
        app, ["export", "jsonld", "--db-path", str(db_path), "--out", str(out_path)]
    )

    assert result.exit_code == 0
    assert "成功导出 2 个对象" in result.stdout

    # 3. 验证输出内容
    assert out_path.exists()
    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "@context" in data
    assert "@graph" in data

    graph = data["@graph"]
    assert len(graph) == 2

    # 检查节点内容
    decision = next(obj for obj in graph if obj["@id"] == "dev:event/evt_001")
    assert decision["@type"] == "dev:Decision"
    assert decision["summary"] == "选择 SQLite"

    # 验证关系导出
    # 在 ontology.yaml 中 implements 映射为 dev:implements
    # JSON-LD 输出使用 context 定义的 term，即 "implements"
    assert "implements" in decision
    relations = decision["implements"]
    assert isinstance(relations, list)
    assert len(relations) == 1
    assert relations[0]["@id"] == "dev:event/req_001"
