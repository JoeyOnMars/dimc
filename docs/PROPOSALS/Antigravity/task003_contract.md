# Task 003 契约：EventIndex source_layer + COALESCE 路由（定稿）

**Status**: 待执行
**Key References**:
- `docs/PROPOSALS/V6.3_extraction_pipeline_design.md` 4.2 节 + 5.1 节
- `src/dimcause/core/event_index.py`（917 行，events 表现有 14 列）

---

## Pre-conditions

```bash
grep -n "source_layer\|source_chunk_id" src/dimcause/core/event_index.py  # → 空
grep -n "class ChunkRecord" src/dimcause/core/schema.py                   # → 有输出（Task 002）
```

---

## 1. DDL 迁移（ALTER TABLE，非重建）

在 `_ensure_schema()` 末尾增加迁移守卫。用 `PRAGMA table_info(events)` 检查列是否已存在，不存在才执行 ALTER：

```sql
ALTER TABLE events ADD COLUMN source_chunk_id TEXT DEFAULT NULL;
ALTER TABLE events ADD COLUMN source_layer TEXT DEFAULT NULL
    CHECK(source_layer IS NULL OR source_layer IN ('l1', 'l2'));
ALTER TABLE events ADD COLUMN updated_at REAL DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_chunk_layer
    ON events(source_chunk_id, source_layer, updated_at DESC);
```

迁移守卫伪代码：
```python
existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
if "source_chunk_id" not in existing_cols:
    conn.execute("ALTER TABLE events ADD COLUMN source_chunk_id TEXT DEFAULT NULL")
if "source_layer" not in existing_cols:
    conn.execute("ALTER TABLE events ADD COLUMN source_layer TEXT DEFAULT NULL CHECK(source_layer IS NULL OR source_layer IN ('l1','l2'))")
if "updated_at" not in existing_cols:
    conn.execute("ALTER TABLE events ADD COLUMN updated_at REAL DEFAULT NULL")
conn.execute("CREATE INDEX IF NOT EXISTS idx_chunk_layer ON events(source_chunk_id, source_layer, updated_at DESC)")
```

新增列后 events 表从 14 列变为 17 列。

---

## 2. `EventIndex.add()` 签名扩展

现有签名：
```python
def add(self, event: Event, markdown_path: str) -> bool:
```

修改为（向后兼容，两个新参数可选默认 None）：
```python
def add(self, event: Event, markdown_path: str,
        source_chunk_id: Optional[str] = None,
        source_layer: Optional[str] = None) -> bool:
```

INSERT 语句从 14 列扩展为 17 列：
```sql
INSERT OR REPLACE INTO events (
    id, type, source, timestamp, date, summary, tags,
    markdown_path, mtime, job_id, status,
    schema_version, json_cache, cache_updated_at,
    source_chunk_id, source_layer, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

最后三个参数值：`source_chunk_id, source_layer, time.time()`。
`updated_at` 每次写入时总是取 `time.time()`，不作为参数暴露。

---

## 3. COALESCE 查询方法（设计文档 5.1 节）

新增方法（不修改现有 `query()`，向后兼容）：

```python
def query_coalesced(
    self,
    type: Optional[Union[str, EventType]] = None,
    source: Optional[Union[str, SourceType]] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
```

SQL 逻辑（来自设计文档，逐字）：
```sql
-- 路径 A：流水线事件，L2 优先于 L1
SELECT e.* FROM events e
WHERE e.source_chunk_id IS NOT NULL
  AND (
    (e.source_layer = 'l2')
    OR
    (e.source_layer = 'l1' AND NOT EXISTS (
        SELECT 1 FROM events e2
        WHERE e2.source_chunk_id = e.source_chunk_id
          AND e2.source_layer = 'l2'))
  )
UNION ALL
-- 路径 B：历史事件（无 chunk 来源），全量返回
SELECT e.* FROM events e
WHERE e.source_chunk_id IS NULL
```

注意：设计文档 5.1 节的路径 A 第一个条件有冗余的 EXISTS 子查询（L2 本身 EXISTS L2 恒真）。上面已简化为直接 `e.source_layer = 'l2'`，语义等价。

然后在此 UNION ALL 结果上应用 type/date/limit 等过滤条件（用 CTE 包裹或子查询）。

---

## 4. per-chunk per-type 代表事件查询（设计文档 5.2 节）

```python
def get_representative_events(
    self,
    chunk_ids: List[str],
) -> List[Dict]:
```

SQL 逻辑（type 维度也参与去重）：
```sql
SELECT e.* FROM events e
WHERE e.source_chunk_id IN (/* 参数化占位符 */)
  AND (
    (e.source_layer = 'l2')
    OR
    (e.source_layer = 'l1' AND NOT EXISTS (
        SELECT 1 FROM events e2
        WHERE e2.source_chunk_id = e.source_chunk_id
          AND e2.type = e.type
          AND e2.source_layer = 'l2'))
  )
```

---

## 5. Acceptance Criteria

```bash
source .venv/bin/activate && pytest tests/test_event_index_coalesce.py -v --timeout=15
```

测试必须覆盖（至少 8 项）：

| # | 测试 | 断言 |
|---|------|------|
| 1 | DDL 迁移后列数 | `PRAGMA table_info(events)` 返回 17 列 |
| 2 | idx_chunk_layer 索引存在 | `sqlite_master` 查询命中 |
| 3 | 迁移幂等性 | 多次调用 `_ensure_schema()` 不报错 |
| 4 | add() 写入新列 | 写入后 SELECT 返回 source_chunk_id/source_layer 非 NULL |
| 5 | add() 向后兼容 | 不传新参数时 source_chunk_id/source_layer 为 NULL |
| 6 | COALESCE L1+L2 | 同 chunk 有 L1+L2 时 query_coalesced 只返回 L2 |
| 7 | COALESCE 仅 L1 | 只有 L1 时正常返回 |
| 8 | COALESCE 历史事件 | source_chunk_id=NULL 的全量返回 |
| 9 | per-chunk per-type | 同 chunk 同 type 有 L1+L2 时只返回 L2 |
| 10 | 现有 query() 不变 | 向后兼容回归测试 |
