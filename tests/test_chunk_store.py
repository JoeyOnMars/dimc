"""
tests/test_chunk_store.py — ChunkStore 单元测试

覆盖：make_chunk_id、add_chunk/get_chunk、update_status FSM（含 needs_extraction 同步）、
      get_pending_extraction（含 session_id/limit 过滤）、event_ids 序列化、时间戳保留。
全部使用 tmp_path fixture，与真实数据完全隔离。
"""

import time

import pytest

from dimcause.core.schema import ChunkRecord
from dimcause.storage.chunk_store import ChunkStore


@pytest.fixture
def store(tmp_path):
    s = ChunkStore(tmp_path / "chunks.db")
    yield s
    s.close()


def _make_chunk(
    source_event_id="evt_001",
    content="test content",
    session_id="sess_001",
    **kwargs,
):
    chunk_id = ChunkStore.make_chunk_id(source_event_id, content)
    return ChunkRecord(
        chunk_id=chunk_id,
        source_event_id=source_event_id,
        session_id=session_id,
        content=content,
        **kwargs,
    )


# ── 1. make_chunk_id ──────────────────────────────────────

def test_make_chunk_id_deterministic():
    id1 = ChunkStore.make_chunk_id("evt_001", "hello world")
    id2 = ChunkStore.make_chunk_id("evt_001", "hello world")
    assert id1 == id2
    assert id1.startswith("chk_")
    assert len(id1) == 20   # "chk_"(4) + sha256[:16](16)


def test_make_chunk_id_different_inputs():
    id1 = ChunkStore.make_chunk_id("evt_001", "aaa")
    id2 = ChunkStore.make_chunk_id("evt_002", "aaa")
    assert id1 != id2


# ── 2. add_chunk / get_chunk ──────────────────────────────

def test_add_and_get_chunk(store):
    chunk = _make_chunk()
    store.add_chunk(chunk)
    result = store.get_chunk(chunk.chunk_id)
    assert result is not None
    assert result.chunk_id == chunk.chunk_id
    assert result.content == chunk.content
    assert result.session_id == chunk.session_id
    assert isinstance(result.event_ids, list)


def test_add_chunk_idempotent(store):
    chunk = _make_chunk()
    store.add_chunk(chunk)
    store.add_chunk(chunk)   # INSERT OR IGNORE，不报错
    result = store.get_chunk(chunk.chunk_id)
    assert result is not None


def test_get_chunk_not_found(store):
    assert store.get_chunk("nonexistent") is None


# ── 3. update_status FSM ──────────────────────────────────

def test_update_status_raw_to_embedded(store):
    chunk = _make_chunk()
    store.add_chunk(chunk)
    store.update_status(chunk.chunk_id, "embedded")
    result = store.get_chunk(chunk.chunk_id)
    assert result.status == "embedded"


def test_update_status_embedded_to_extracted(store):
    chunk = _make_chunk()
    store.add_chunk(chunk)
    store.update_status(chunk.chunk_id, "embedded")
    store.update_status(chunk.chunk_id, "extracted")
    result = store.get_chunk(chunk.chunk_id)
    assert result.status == "extracted"


def test_update_status_illegal_skip_raises(store):
    """raw → extracted 跳级，必须 raise ValueError"""
    chunk = _make_chunk()
    store.add_chunk(chunk)
    with pytest.raises(ValueError, match="FSM 非法转换"):
        store.update_status(chunk.chunk_id, "extracted")


def test_update_status_not_found_raises(store):
    with pytest.raises(ValueError, match="chunk_id not found"):
        store.update_status("nonexistent", "embedded")


# ── 4. get_pending_extraction ─────────────────────────────

def test_get_pending_extraction(store):
    c1 = _make_chunk("evt_001", "content 1")                               # 默认 needs_extraction=True
    c2 = _make_chunk("evt_002", "content 2", needs_extraction=False)       # 不需要提取
    c3 = _make_chunk("evt_003", "content 3", extraction_failed=True)       # 已失败，跳过
    store.add_chunk(c1)
    store.add_chunk(c2)
    store.add_chunk(c3)
    pending = store.get_pending_extraction()
    assert len(pending) == 1
    assert pending[0].chunk_id == c1.chunk_id


# ── 5. event_ids 序列化 ───────────────────────────────────

def test_event_ids_roundtrip(store):
    chunk = _make_chunk(content="rich chunk")
    chunk_with_ids = chunk.model_copy(update={"event_ids": ["evt_A", "evt_B"]})
    store.add_chunk(chunk_with_ids)
    result = store.get_chunk(chunk_with_ids.chunk_id)
    assert result.event_ids == ["evt_A", "evt_B"]


# ── 6. 时间戳保留（fix 1）────────────────────────────────

def test_add_chunk_preserves_timestamps(store):
    """add_chunk 应保留调用方传入的 created_at，而非用 INSERT 时的 time.time() 覆盖。"""
    t0 = time.time() - 3600   # 模拟 1 小时前创建的 chunk
    chunk = _make_chunk(content="historical chunk")
    chunk = chunk.model_copy(update={"created_at": t0, "updated_at": t0})
    store.add_chunk(chunk)
    result = store.get_chunk(chunk.chunk_id)
    assert abs(result.created_at - t0) < 0.01


# ── 7. update_status 同步 needs_extraction（fix 3）────────

def test_update_status_extracted_clears_needs_extraction(store):
    """到达 extracted 时，needs_extraction 必须同步为 False。"""
    chunk = _make_chunk()
    store.add_chunk(chunk)
    store.update_status(chunk.chunk_id, "embedded")
    store.update_status(chunk.chunk_id, "extracted")
    result = store.get_chunk(chunk.chunk_id)
    assert result.status == "extracted"
    assert result.needs_extraction is False


def test_update_status_embedded_keeps_needs_extraction(store):
    """raw → embedded 时，needs_extraction 保持 True（提取尚未完成）。"""
    chunk = _make_chunk()
    store.add_chunk(chunk)
    store.update_status(chunk.chunk_id, "embedded")
    result = store.get_chunk(chunk.chunk_id)
    assert result.status == "embedded"
    assert result.needs_extraction is True


# ── 8. get_pending_extraction session_id + limit（fix 2）──

def test_get_pending_extraction_session_filter(store):
    """session_id 过滤：只返回指定 session 的待提取 chunk。"""
    c1 = _make_chunk("evt_001", "content 1", session_id="sess_A")
    c2 = _make_chunk("evt_002", "content 2", session_id="sess_B")
    store.add_chunk(c1)
    store.add_chunk(c2)
    pending = store.get_pending_extraction(session_id="sess_A")
    assert len(pending) == 1
    assert pending[0].session_id == "sess_A"


def test_get_pending_extraction_limit(store):
    """limit 参数：最多返回指定条数。"""
    for i in range(5):
        store.add_chunk(_make_chunk(f"evt_{i:03d}", f"content {i}"))
    pending = store.get_pending_extraction(limit=2)
    assert len(pending) == 2
