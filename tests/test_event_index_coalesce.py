"""
tests/test_event_index_coalesce.py — EventIndex V6.3 COALESCE 路由测试

验收标准（10项）：
1. DDL 迁移后列数 = 17
2. idx_chunk_layer 索引存在
3. _ensure_schema 幂等性
4. add() 写入 source_chunk_id / source_layer
5. add() 向后兼容（不传新参数时值为 NULL）
6. COALESCE：同 chunk 有 L1+L2 时只返回 L2
7. COALESCE：只有 L1 时正常返回
8. COALESCE：历史事件（source_chunk_id IS NULL）全量返回
9. per-chunk per-type：同 chunk 同 type 有 L1+L2 时只返回 L2
10. 现有 query() 向后兼容回归测试

全部使用 tmp_path fixture，与真实数据完全隔离。
注意：测试只请求 `idx` fixture（不直接请求 `tmp_path`），
路径用 f"/fake/{event_id}.md" 格式，避免 pytest fixture 双重解析引发锁超时。
"""

from datetime import datetime

import pytest

from dimcause.core.event_index import EventIndex
from dimcause.core.models import Event, EventType, SourceType


@pytest.fixture
def idx(tmp_path):
    return EventIndex(db_path=str(tmp_path / "test.db"))


def _make_event(
    event_id: str,
    event_type: EventType = EventType.DECISION,
    summary: str = "test event",
) -> Event:
    return Event(
        id=event_id,
        type=event_type,
        source=SourceType.MANUAL,
        timestamp=datetime(2024, 1, 1, 0, 0, 0),
        summary=summary,
        content=f"content for {event_id}",
    )


def _fp(name: str) -> str:
    """返回不存在的假路径（add() 用 time.time() 作为 mtime，不要求文件真实存在）。"""
    return f"/fake/test/{name}.md"


# ── 1. DDL 迁移后列数 ─────────────────────────────────────

def test_schema_has_17_columns(idx):
    conn = idx._get_conn()
    cols = [row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()]
    conn.close()
    assert len(cols) == 17, f"期望 17 列，实际 {len(cols)}：{cols}"


# ── 2. idx_chunk_layer 索引存在 ──────────────────────────

def test_schema_index_chunk_layer_exists(idx):
    conn = idx._get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_chunk_layer'"
    ).fetchone()
    conn.close()
    assert row is not None, "idx_chunk_layer 索引不存在"


# ── 3. 迁移幂等性 ─────────────────────────────────────────

def test_schema_idempotent(tmp_path):
    db = str(tmp_path / "idem.db")
    EventIndex(db_path=db)   # 第一次创建
    EventIndex(db_path=db)   # 第二次不报错


# ── 4. add() 写入新列 ─────────────────────────────────────

def test_add_writes_source_columns(idx):
    event = _make_event("evt_001")
    idx.add(event, _fp("evt_001"), source_chunk_id="chk_abc", source_layer="l1")
    conn = idx._get_conn()
    row = conn.execute(
        "SELECT source_chunk_id, source_layer FROM events WHERE id=?", ("evt_001",)
    ).fetchone()
    conn.close()
    assert row["source_chunk_id"] == "chk_abc"
    assert row["source_layer"] == "l1"


# ── 5. add() 向后兼容 ─────────────────────────────────────

def test_add_backward_compatible(idx):
    event = _make_event("evt_legacy")
    idx.add(event, _fp("evt_legacy"))   # 不传新参数
    conn = idx._get_conn()
    row = conn.execute(
        "SELECT source_chunk_id, source_layer FROM events WHERE id=?", ("evt_legacy",)
    ).fetchone()
    conn.close()
    assert row["source_chunk_id"] is None
    assert row["source_layer"] is None


# ── 6. COALESCE：同 chunk 有 L1+L2 → 只返回 L2 ───────────

def test_query_coalesced_l2_wins_over_l1(idx):
    e_l1 = _make_event("evt_l1", summary="l1 version")
    e_l2 = _make_event("evt_l2", summary="l2 version")
    idx.add(e_l1, _fp("evt_l1"), source_chunk_id="chk_x", source_layer="l1")
    idx.add(e_l2, _fp("evt_l2"), source_chunk_id="chk_x", source_layer="l2")

    results = idx.query_coalesced()
    ids = {r["id"] for r in results}
    assert "evt_l2" in ids, "L2 事件应出现在结果中"
    assert "evt_l1" not in ids, "L1 事件被 L2 覆盖，不应出现"


# ── 7. COALESCE：只有 L1 → 正常返回 ──────────────────────

def test_query_coalesced_only_l1_returned(idx):
    event = _make_event("evt_only_l1")
    idx.add(event, _fp("evt_only_l1"), source_chunk_id="chk_y", source_layer="l1")

    results = idx.query_coalesced()
    ids = {r["id"] for r in results}
    assert "evt_only_l1" in ids


# ── 8. COALESCE：历史事件（无 chunk 来源）全量返回 ────────

def test_query_coalesced_legacy_events_returned(idx):
    legacy = _make_event("evt_legacy_hist")
    idx.add(legacy, _fp("evt_legacy_hist"))   # source_chunk_id=None

    results = idx.query_coalesced()
    ids = {r["id"] for r in results}
    assert "evt_legacy_hist" in ids


# ── 9. per-chunk per-type：L1+L2 → 只返回 L2 ─────────────

def test_get_representative_events_l2_wins(idx):
    e_l1 = _make_event("rep_l1", event_type=EventType.DECISION)
    e_l2 = _make_event("rep_l2", event_type=EventType.DECISION)  # 同 type
    idx.add(e_l1, _fp("rep_l1"), source_chunk_id="chk_z", source_layer="l1")
    idx.add(e_l2, _fp("rep_l2"), source_chunk_id="chk_z", source_layer="l2")

    results = idx.get_representative_events(["chk_z"])
    ids = {r["id"] for r in results}
    assert "rep_l2" in ids
    assert "rep_l1" not in ids


def test_get_representative_events_empty_input(idx):
    assert idx.get_representative_events([]) == []


# ── 10. 现有 query() 向后兼容 ────────────────────────────

def test_query_backward_compatible(idx):
    event = _make_event("evt_compat", event_type=EventType.CODE_CHANGE)
    idx.add(event, _fp("evt_compat"))
    results = idx.query(type=EventType.CODE_CHANGE)
    assert len(results) == 1
    assert results[0]["id"] == "evt_compat"
