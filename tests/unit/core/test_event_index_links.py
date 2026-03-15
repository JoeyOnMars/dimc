import json
from datetime import datetime

import pytest

from dimcause.reasoning.causal import CausalLink
from dimcause.core.event_index import EventIndex
from dimcause.core.models import EventType, SemanticEvent


@pytest.fixture
def index(tmp_path):
    # 使用临时数据库进行测试
    db_path = tmp_path / "test_index.db"
    return EventIndex(str(db_path))


def test_ensure_schema_creates_links_table(index):
    """测试 EventIndex 初始化时是否创建 causal_links 表。"""
    conn = index._get_conn()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='causal_links'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_add_semantic_event_with_links(index):
    """测试添加带有 CausalLinks 的 SemanticEvent 是否能持久化链接。"""

    # 创建一个简单的 SemanticEvent
    event = SemanticEvent(
        id="evt_001",
        type=EventType.DECISION,
        timestamp=datetime.now(),
        summary="Test Decision",
        content="Testing causal links",
        uri="dev://decision/test",
        causal_links=[
            CausalLink(
                source="dev://decision/test",
                target="dev://requirement/req_001",
                relation="implements",
                weight=1.0,
                metadata={"reason": "direct implementation"},
            ),
            CausalLink(
                source="dev://decision/test",
                target="dev://decision/old_one",
                relation="overrides",
                weight=0.8,
            ),
        ],
    )

    # 添加到索引 (需要一个占位路径)
    index.add(event, "/tmp/dummy.md")

    # 验证数据库中存在链接
    conn = index._get_conn()
    links = conn.execute(
        "SELECT * FROM causal_links WHERE source = 'dev://decision/test'"
    ).fetchall()
    conn.close()

    assert len(links) == 2

    # 检查第一个链接
    link1 = next(link for link in links if link["target"] == "dev://requirement/req_001")
    assert link1["relation"] == "implements"
    assert link1["weight"] == 1.0
    assert json.loads(link1["metadata"]) == {"reason": "direct implementation"}


def test_get_links(index):
    """测试通过 get_links 方法获取链接。"""
    event = SemanticEvent(
        id="evt_002",
        type=EventType.TASK,
        timestamp=datetime.now(),
        summary="Task 2",
        content="Content",
        uri="dev://task/002",
        causal_links=[
            CausalLink(source="dev://task/002", target="dev://epic/1", relation="part_of")
        ],
    )
    index.add(event, "/tmp/dummy2.md")

    """
    假设 get_links 通过 event_id 或 uri 获取。
    架构文档中提到：get_links(event_id)
    但 CausalLinks 使用 URI。index.get_links 可能类似于 get_events 但针对链接。
    让我们假设我们实现 get_links(event_id) 来查找事件的 URI 或 ID？
    实际上，SemanticEvent 有 URI。理想情况下按源 URI 查找。
    但 EventIndex 的主键是 id。
    让我们决定：get_links(event_id) -> 查找事件，找到其 URI？或者仅按 event_id 查询？
    等一下，causal_links 表使用 source (URI) 和 target (URI)。
    如果 EventIndex 管理 SemanticEvent，它知道 id -> uri 的映射吗？
    是的，SemanticEvent.uri 存储在 json_cache 中。
    但是，causal_links 表可能需要 event_id 列以便轻松链接回 events 表进行级联删除？
    实现计划说：“source (TEXT, FK -> events.id)”。
    等一下，计划说“source (TEXT, FK -> events.id)”。
    但是 CausalLink 模型有 source: str # URI。
    如果 source 是 events.id，那么 CausalLink.source 必须兼容或我们进行映射。
    SemanticEvent 使用 URI。
    冲突：计划说 FK -> events.id，但模型使用 URI。
    解决方案：CausalLink 逻辑严格使用 URI。数据库表 causal_links 可能应该存储 URI。
    或者我们在 causal_links 中添加 event_id 列以跟踪所有权。
    让我们假设 event_id 列是 FK，而 source / target 是 URI。
    """

    links = index.get_links("evt_002")
    assert len(links) == 1
    assert links[0].target == "dev://epic/1"
    assert isinstance(links[0], CausalLink)


def test_remove_event_removes_links(index):
    """测试删除事件也会清理其因果链接。"""
    event = SemanticEvent(
        id="evt_003",
        type=EventType.RESEARCH,
        timestamp=datetime.now(),
        summary="Note",
        content="Note",
        uri="dev://note/3",
        causal_links=[
            CausalLink(source="dev://note/3", target="dev://doc/1", relation="references")
        ],
    )
    index.add(event, "/tmp/dummy3.md")

    # 验证已添加
    assert len(index.get_links("evt_003")) == 1

    # 删除
    index.remove("evt_003")

    # 验证已删除
    conn = index._get_conn()
    count = conn.execute("SELECT COUNT(*) FROM causal_links").fetchone()[0]
    conn.close()
    assert count == 0
