# Task 004 契约：ExtractionPipeline.run() 批次编排（定稿 v4）

**Status**: 待执行  
**Key References**:
- `docs/PROPOSALS/V6.3_extraction_pipeline_design.md` §一 + §八
- `src/dimcause/extractors/extraction_pipeline.py`（143 行，骨架，含 `_link_causal_edges`）
- `src/dimcause/storage/chunk_store.py`（206 行，Task 002 完成）
- `src/dimcause/core/event_index.py`（1018 行，Task 003 完成）

---

## Pre-conditions

```bash
grep -n "class ChunkStore" src/dimcause/storage/chunk_store.py            # → 有输出（Task 002）
grep -n "def query_coalesced" src/dimcause/core/event_index.py            # → 有输出（Task 003）
grep -n "class ExtractionPipeline" src/dimcause/extractors/extraction_pipeline.py  # → 有输出（骨架）
grep -n "_link_causal_edges" src/dimcause/extractors/extraction_pipeline.py        # → 有输出
```

---

## 已有资产（禁止重写，只可扩展）

| 文件 | 已存在内容 | 约束 |
|------|-----------|------|
| `extraction_pipeline.py` | `__init__`、`_link_causal_edges`、`_infer_directed_relation` | 只追加方法 |
| `chunk_store.py` | `ChunkStore` 全部（Task 002） | 不动 |
| `event_index.py` | `add()`、`query_coalesced()` 等（Task 003） | 只追加 `add_if_not_exists()` + `delete_by_chunk_layer()` |
| `models.py` | `Event.related_event_ids`（L166） | 不动 |
| `graph_store.py` | `add_relation()` RMW | 不动 |

---

## P 博士裁定 + G 审计补充（全部封闭）

### R1. 幂等语义（软约束）
- 重复调用 `run()` 不产出重复 events（按 `event_id` 去重）和重复边（GraphStore RMW 保证）。
- 不追求「精确一次」级别的事务恢复，V6.4 计划增加 checkpoint。

### R2. L1 行为：只补不删
- L1 使用 **`add_if_not_exists()`**（新增方法）写入 EventIndex。
- `source_chunk_id = chunk.chunk_id`，`source_layer = 'l1'`。
- **L1 和 L2 都带 source_chunk_id**，NULL 路径仅保留给无 chunk 来源的历史事件。
- 不会删除或更新已有的 L1 事件记录。

### R3. L2 重跑语义：先删后插
- 每次运行前，通过 `delete_by_chunk_layer(chunk_id, 'l2')` 删除该 chunk 下所有 L2 事件。
- 然后用 `add()` 插入新 L2 事件。`source_chunk_id = chunk.chunk_id`，`source_layer = 'l2'`。
- 因果边不做级联删除，只为新 L2 事件补齐边关系。

### R4. `_persist_events()` 职责边界
- 统一写 EventIndex + 调 CausalLinker，出错抛异常。
- 不直接改 ChunkStore，由上层 `run()` 驱动 ChunkStore 状态更新。
- **不得访问 EventIndex 的私有方法**，所有操作通过公开 API 完成（G 审计补充）。

### R5. FSM 强制完整路径
- `raw → embedded`（L1 完成后推进）
- `embedded → extracted`（L2 完成后推进）
- 无 LLM Key 时，chunk 停在 `embedded`，`needs_extraction` 仍为 1。下次 `run()` 时跳过 L1，仅尝试 L2。

### R6. L1 提取器选择（G 审计补充）
- M 专家自行选择最高效的 L1 提取方式。
- **优先从 `extract_session_events()` 的内部逻辑中直接获取结构化数据**（Event 或等价中间表示），避免 markdown → Event 的逆解析。
- 如果内部无法拆分，可退而使用 `Event.from_markdown()` 解析，但须在代码中注释标明此为临时方案。

### Known Issues（允许进入 V6.3）
- `add_if_not_exists()` 存在 TOCTOU 竞态窗口（check-then-act 非原子），在 local-first 单用户场景下风险极低。须在代码注释中标注此限制，V6.4 可改为数据库级 `INSERT ... WHERE NOT EXISTS` 原子操作。
- 若对同一 chunk 多次运行 L2，历史 graph_nodes/graph_edges 可能保留为孤儿；V6.4 计划增加「事件删除 → 边 GC」机制。

---

## 1. EventIndex 新增 2 个公开方法

### 1.1 `add_if_not_exists()`

```python
def add_if_not_exists(
    self, event: Event, markdown_path: str,
    source_chunk_id: Optional[str] = None,
    source_layer: Optional[str] = None,
) -> bool:
    """
    仅当 event_id 不存在时写入（L1 幂等语义）。
    已存在则跳过，返回 False。

    注意：check-then-act 非原子操作（TOCTOU），
    在 local-first 单用户场景下可接受。
    """
    existing = self.get_by_id(event.id)
    if existing is not None:
        return False
    return self.add(event, markdown_path,
                    source_chunk_id=source_chunk_id,
                    source_layer=source_layer)
```

### 1.2 `delete_by_chunk_layer()`

```python
def delete_by_chunk_layer(self, chunk_id: str, layer: str) -> int:
    """
    删除指定 chunk 的指定 layer 全部事件。

    用于 L2 重跑前清理旧 L2 事件（R3）。
    注意：不会级联删除 graph_nodes/graph_edges（Known Issue）。

    Returns:
        int: 删除的行数
    """
    conn = self._get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM events WHERE source_chunk_id = ? AND source_layer = ?",
            (chunk_id, layer),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
```

---

## 2. `__init__` 扩展

在现有 `__init__` 基础上追加 `chunk_store` 参数：

```python
def __init__(
    self,
    event_index: EventIndex,
    graph_store: GraphStore,
    chunk_store: ChunkStore,           # ← 新增
) -> None:
    self.event_index = event_index
    self.graph_store = graph_store
    self.chunk_store = chunk_store     # ← 新增
    self.ontology = get_ontology()
```

---

## 3. `run()` — 批次编排入口

```python
def run(self, session_id: str) -> dict:
    """
    执行 L1→(L2)→Persist→Link 全流程。

    Returns:
        dict: {"l1_count": int, "l2_count": int, "link_count": int, "errors": int}
    """
```

逻辑伪代码（按 chunk 状态分流）：

```
MAX_RETRIES = 3
stats = {"l1_count": 0, "l2_count": 0, "link_count": 0, "errors": 0}

1. pending = self.chunk_store.get_pending_extraction(session_id=session_id)
2. 如果 pending 为空，返回 stats

3. has_llm = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))

4. 对每个 chunk in pending:
   l1_done = False

   # ── L1 阶段（仅 raw 状态的 chunk）──
   if chunk.status == 'raw':
       try:
           events = _run_l1(chunk)
           count = _persist_events(events, chunk, 'l1')
           stats["l1_count"] += count
           self.chunk_store.update_status(chunk.chunk_id, 'embedded')
           l1_done = True
       except Exception as e:
           logger.error(f"L1 failed for {chunk.chunk_id}: {e}")
           stats["errors"] += 1
           continue  # 跳过该 chunk 的 L2

   # ── L2 阶段（已 embedded + 有 LLM Key）──
   if has_llm and (l1_done or chunk.status == 'embedded'):
       try:
           events = _run_l2(chunk)
           count = _persist_events(events, chunk, 'l2')
           stats["l2_count"] += count
           self.chunk_store.update_status(chunk.chunk_id, 'extracted')
       except Exception as e:
           logger.warning(f"L2 failed for {chunk.chunk_id}: {e}")
           stats["errors"] += 1
           # 重试计数由外部任务管理或手动重跑

5. 返回 stats
```

---

## 4. `_run_l1()` — L1 本地提取

```python
def _run_l1(self, chunk: ChunkRecord) -> List[Event]:
    """
    对单个 chunk 执行 L1 本地提取（无 LLM 依赖）。

    优先从 extract_session_events 内部获取结构化数据，
    避免 markdown → Event 逆解析（R6）。
    event_id 命名空间（定案5）：'evt_' + sha256(chunk_id:l1:index)[:16]
    提取失败返回空列表，不抛异常。
    """
```

---

## 5. `_run_l2()` — L2 LLM 提取（可选）

```python
def _run_l2(self, chunk: ChunkRecord) -> List[Event]:
    """
    对单个 chunk 执行 L2 云端 LLM 提取。

    复用 brain/extractor.py 中的 EventExtractor.extract_from_text()。
    event_id 命名空间（定案5）：'evt_' + sha256(chunk_id:l2:index)[:16]
    失败时抛异常，由 run() 层捕获。
    """
```

---

## 6. `_persist_events()` — 事件入库 + 建边

```python
def _persist_events(
    self,
    events: List[Event],
    chunk: ChunkRecord,
    layer: str,  # 'l1' or 'l2'
) -> int:
    """
    将事件写入 EventIndex，同步调用 _link_causal_edges 建边。

    L1 策略：add_if_not_exists()（只补不覆盖）
    L2 策略：先 delete_by_chunk_layer()，再逐条 add()

    不直接修改 ChunkStore（R4），出错时抛异常由上层处理。

    Returns:
        int: 成功写入的事件数量
    """
```

逻辑：
```
1. if layer == 'l2':
       self.event_index.delete_by_chunk_layer(chunk.chunk_id, 'l2')

2. count = 0
   for event in events:
       if layer == 'l1':
           ok = self.event_index.add_if_not_exists(
               event, fake_path,
               source_chunk_id=chunk.chunk_id, source_layer='l1')
       else:
           ok = self.event_index.add(
               event, fake_path,
               source_chunk_id=chunk.chunk_id, source_layer='l2')
       if ok:
           count += 1
           try:
               self._link_causal_edges(event)
           except Exception as e:
               logger.warning(f"CausalLinker failed for {event.id}: {e}")
3. return count
```

---

## 7. Acceptance Criteria

```bash
source .venv/bin/activate && pytest tests/test_extraction_pipeline.py -v --timeout=30
```

测试必须覆盖（12 项）：

| # | 测试 | 断言 |
|---|------|------|
| 1 | `__init__` 三参数 | `ExtractionPipeline(event_index, graph_store, chunk_store)` 不报错 |
| 2 | `run()` 空 session | pending=0 时返回全零统计 dict |
| 3 | `run()` L1 路径 | raw chunk → 产出 L1 事件，EventIndex 中 `source_layer='l1'`、`source_chunk_id` 非 NULL |
| 4 | L1 event_id 命名空间 | 符合 `sha256(chunk_id:l1:index)` 格式 |
| 5 | `add_if_not_exists()` 幂等 | 同一 event_id 调用两次，第二次返回 False，EventIndex 只有一条记录 |
| 6 | `delete_by_chunk_layer()` | 删除指定 chunk 的 L2 事件，L1 不受影响 |
| 7 | `_persist_events()` L2 先删后插 | 同 chunk 重跑 L2，旧 L2 事件被删除，只留最新 L2 |
| 8 | `_link_causal_edges()` 被触发 | 写入带 `related_event_ids` 的事件后 `graph_edges` 有新边 |
| 9 | FSM 推进：L1 | L1 完成后 `chunk.status='embedded'` |
| 10 | FSM 推进：L2 | L2 完成后 `chunk.status='extracted'` |
| 11 | 无 LLM Key 纯 L1 | 无 API Key 也能完成，`l2_count=0`，chunk 停在 'embedded' |
| 12 | 幂等：重复 run() | 两次 `run()` 不产出重复 event_id |
