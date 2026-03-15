# Task 004 交付报告：ExtractionPipeline.run() 批次编排

**交付时间**：2026-02-24
**执行人**：M专家（Claude Code）
**契约版本**：G博士 task004_contract.md（定稿 v4）

---

## 落盘文件清单

| 文件 | 操作 | 状态 |
|------|------|------|
| `src/dimcause/core/event_index.py` | 修改（+2 方法） | ✅ |
| `src/dimcause/extractors/extraction_pipeline.py` | 修改（+5 方法） | ✅ |
| `tests/test_extraction_pipeline.py` | 新建 | ✅ |

---

## event_index.py 变更

### 新增 2 个方法

| 方法 | 功能 |
|------|------|
| `add_if_not_exists()` | 仅当 event_id 不存在时写入（L1 幂等语义） |
| `delete_by_chunk_layer(chunk_id, layer)` | 删除指定 chunk 的指定 layer 事件 |

---

## extraction_pipeline.py 变更

### 1. `__init__` 扩展

```python
def __init__(
    self,
    event_index: EventIndex,
    graph_store: GraphStore,
    chunk_store: ChunkStore,   # ← 新增
) -> None:
```

### 2. `run()` — 批次编排入口

```python
def run(self, session_id: str) -> dict:
    """执行 L1→(L2)→Persist→Link 全流程"""
    # - pending = chunk_store.get_pending_extraction(session_id)
    # - has_llm = 检查 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY
    # - L1: raw → embedded（SessionExtractor）
    # - L2: embedded → extracted（EventExtractor，需 LLM）
    # - FSM 推进：update_status()
```

### 3. `_run_l1()` — L1 本地提取

- 使用 `SessionExtractor(use_embedding=False)`
- 包装 chunk.content 为 Claude Code markdown 格式（### USER / ### ASSISTANT）
- 关键词匹配：CATEGORY_KEYWORDS（completed_task/problem/decision/pending/code_change）
- event_id 命名空间：`evt_` + sha256(chunk_id:l1:index)[:16]

### 4. `_run_l2()` — L2 LLM 提取

- 使用 `EventExtractor.extract_from_text()`
- 需要 LLM API Key
- event_id 命名空间：`evt_` + sha256(chunk_id:l2:index)[:16]

### 5. `_persist_events()` — 事件入库 + 建边

- L1：`add_if_not_exists()`（只补不覆盖）
- L2：先 `delete_by_chunk_layer()` 再 `add()`
- 同步调用 `_link_causal_edges()`

### 6. `_link_causal_edges()` — 已修复

- `get_by_id()` 返回 dict → 构造临时对象避免 `.type` 访问报错
- `source_chunk_id` 从 Event 对象获取（兼容 dict 返回）

---

## 测试结果

```
pytest tests/test_extraction_pipeline.py -v --timeout=30
12 passed in 2.19s
```

| # | 测试 | 验证内容 |
|---|------|---------|
| 1 | test_init_three_params | `__init__` 三参数正确注入 |
| 2 | test_run_empty_session | 空 session 返回全零统计 |
| 3 | test_run_l1_path | raw → L1 事件，source_layer='l1' |
| 4 | test_l1_event_id_namespace | event_id 符合 sha256 格式 |
| 5 | test_add_if_not_exists_idempotent | 幂等：第二次返回 False |
| 6 | test_delete_by_chunk_layer | 删除指定 layer，L1 不受影响 |
| 7 | test_persist_l2_delete_then_insert | L2 重跑先删后插 |
| 8 | test_link_causal_edges_triggered | `_link_causal_edges()` 执行不报错 |
| 9 | test_fsm_advance_l1 | L1 完成后 status='embedded' |
| 10 | test_fsm_advance_l2 | L2 完成后 status='extracted' |
| 11 | test_no_llm_key_l1_only | 无 LLM Key 时 L1 正常完成 |
| 12 | test_idempotent_repeated_run | 重复 run() 不产出重复 event |

---

## G博士物理审计命令

```bash
# 代码存在性
grep -n "def add_if_not_exists\|def delete_by_chunk_layer" src/dimcause/core/event_index.py
grep -n "def run\|def _run_l1\|def _run_l2\|def _persist_events" src/dimcause/extractors/extraction_pipeline.py

# 关键约束
grep -n "source_layer.*l1\|source_layer.*l2" src/dimcause/extractors/extraction_pipeline.py
grep -n "update_status" src/dimcause/extractors/extraction_pipeline.py

# 测试
python -m pytest tests/test_extraction_pipeline.py -v --timeout=30
```

---

## 技术说明

- **L1 关键词匹配**：`SessionExtractor` 需要 Claude Code markdown 格式（### USER/### ASSISTANT 带时间戳），否则无法解析轮次。
- **L1 提取内容**：需包含 CATEGORY_KEYWORDS 中的英文/中文关键词（如 "fixed", "merged", "completed"）才能触发提取。
- **L2 需要 LLM**：无 API Key 时 L2 直接跳过，chunk 停在 embedded。
- **get_by_id 兼容**：`EventIndex.get_by_id()` 返回 dict，`_link_causal_edges()` 已修复为构造临时对象。
