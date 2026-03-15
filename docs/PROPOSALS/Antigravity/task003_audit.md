# Task 003 审计报告：EventIndex source_layer + COALESCE 路由

**审计时间**：2026-02-23 23:20  
**审计人**：G博士（Antigravity）  
**交付人**：M专家（Claude Code）  
**契约版本**：[task003_contract.md](file:///Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/Antigravity/task003_contract.md)  
**设计文档**：[V6.3_extraction_pipeline_design.md](file:///Users/mini/projects/GithubRepos/dimc/docs/PROPOSALS/V6.3_extraction_pipeline_design.md) §4.2 + §5.1 + §5.2

---

## 1. 结论概要

**整体评估：✅ 可接受，建议合并。**

M 专家的交付物完整实现了契约全部 4 项变更（DDL 迁移、`add()` 扩展、`query_coalesced()`、`get_representative_events()`），全部 10 项验收测试覆盖，11 项测试全部通过，全量回归 0 失败。代码与契约和设计文档严格对齐，无 P0/P1 级问题。发现若干 P2 级历史遗留代码卫生问题，不阻断合并。

---

## 2. 契约逐项对齐审计

### 2.1 DDL 迁移（契约 §1）

| 契约条目 | 代码实现 ([event_index.py:L140-154](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L140-L154)) | 对齐 |
|----------|------|------|
| `source_chunk_id TEXT DEFAULT NULL` | ✅ L143 | ✅ |
| `source_layer TEXT DEFAULT NULL CHECK(...)` | ✅ L145-148, NULL 安全写法 | ✅ |
| `updated_at REAL DEFAULT NULL` | ✅ L149-150 | ✅ |
| `PRAGMA table_info` 迁移守卫 | ✅ L141 `existing_cols` | ✅ |
| `idx_chunk_layer` 组合索引 | ✅ L151-154, DESC 排序 | ✅ |
| 14→17 列 | ✅ 独立脚本验证 17 列 | ✅ |

**独立物理验证**：
```
列数: 17
列名: ['id', 'type', 'source', 'timestamp', 'date', 'summary', 'tags',
        'markdown_path', 'mtime', 'job_id', 'status', 'schema_version',
        'json_cache', 'cache_updated_at', 'source_chunk_id', 'source_layer', 'updated_at']
idx_chunk_layer SQL: CREATE INDEX idx_chunk_layer ON events(source_chunk_id, source_layer, updated_at DESC)
```

---

### 2.2 `add()` 签名扩展（契约 §2）

| 契约条目 | 代码实现 ([event_index.py:L511-513](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L511-L513)) | 对齐 |
|----------|------|------|
| `source_chunk_id: Optional[str] = None` | ✅ L512 | ✅ |
| `source_layer: Optional[str] = None` | ✅ L513 | ✅ |
| INSERT 17 列 | ✅ L578-606 | ✅ |
| `updated_at = time.time()` 不暴露 | ✅ L604 | ✅ |
| 向后兼容（不传参 → NULL） | ✅ 测试 #5 验证 | ✅ |

---

### 2.3 `query_coalesced()` 方法（契约 §3）

| 契约条目 | 代码实现 ([event_index.py:L944-989](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L944-L989)) | 对齐 |
|----------|------|------|
| 签名 8 参数 | ✅ L944-954 与契约逐字一致 | ✅ |
| 返回 `List[Dict]` | ✅ L987 | ✅ |
| 路径 A：`source_chunk_id IS NOT NULL` | ✅ L966 | ✅ |
| L2 直通 | ✅ L968 | ✅ |
| L1 仅在同 chunk 无 L2 时返回 | ✅ L970-973 NOT EXISTS | ✅ |
| 路径 B：`source_chunk_id IS NULL` 全量 | ✅ L976-977 | ✅ |
| UNION ALL | ✅ L975 | ✅ |
| CTE/子查询包裹后过滤 | ✅ L963-978 子查询 + `_build_query_sql` | ✅ |

> **与设计文档差异说明**：设计文档 §5.1 路径 A 的 L2 条件有冗余 EXISTS 子查询（L2 自身 EXISTS L2 恒真），契约已将其简化为直接 `e.source_layer = 'l2'`。代码忠实实现了契约简化版，语义等价。**此为合法简化，非偏离。**

---

### 2.4 `get_representative_events()` 方法（契约 §4）

| 契约条目 | 代码实现 ([event_index.py:L991-1017](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L991-L1017)) | 对齐 |
|----------|------|------|
| 签名 `chunk_ids: List[str]` | ✅ L991 | ✅ |
| 返回 `List[Dict]` | ✅ L1015 | ✅ |
| IN 参数化占位符 | ✅ L1000-1003 动态占位 | ✅ |
| L2 直通 | ✅ L1005 | ✅ |
| L1 + per-type NOT EXISTS | ✅ L1007-1011 `e2.type = events.type` | ✅ |
| 空列表防护 | ✅ L996-997 | ✅ |

---

### 2.5 验收测试覆盖（契约 §5）

| # | 契约要求 | 测试函数 | 通过 |
|---|---------|---------|------|
| 1 | DDL 迁移后 17 列 | `test_schema_has_17_columns` | ✅ |
| 2 | idx_chunk_layer 索引 | `test_schema_index_chunk_layer_exists` | ✅ |
| 3 | 迁移幂等性 | `test_schema_idempotent` | ✅ |
| 4 | add() 新列写入 | `test_add_writes_source_columns` | ✅ |
| 5 | add() 向后兼容 | `test_add_backward_compatible` | ✅ |
| 6 | COALESCE L1+L2→L2 | `test_query_coalesced_l2_wins_over_l1` | ✅ |
| 7 | COALESCE 仅 L1 | `test_query_coalesced_only_l1_returned` | ✅ |
| 8 | COALESCE 历史事件 | `test_query_coalesced_legacy_events_returned` | ✅ |
| 9 | per-chunk per-type | `test_get_representative_events_l2_wins` | ✅ |
| 10 | query() 向后兼容 | `test_query_backward_compatible` | ✅ |

**额外测试**：`test_get_representative_events_empty_input`（第 11 项，空输入边界）— 契约要求"至少 8 项"，实际交付 11 项，**超额完成**。

---

## 3. 测试执行证据

### 专项测试
```
$ pytest tests/test_event_index_coalesce.py -v --timeout=15
11 passed in 0.17s
```

### 全量回归
```
$ pytest tests/ -v --timeout=30
847 passed, 31 skipped, 0 failed in 267.17s (0:04:27)
```

**结论**：零回归。31 项 skip 均为 LLM 依赖测试（需 API Key），与 Task 003 无关。

---

## 4. 问题清单

### P0 / 阻断级
无。

### P1 / 高优先级
无。

### P2 / 建议优化（不阻断合并）

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| 1 | [event_index.py:L680](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L680) | `add()` 异常路径使用 `print(f"Index add failed: {e}")` 而非 `logger` | 改为 `logger.error()`。注：这是 **历史遗留问题**，非 M 专家引入 |
| 2 | [event_index.py:L504](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L504) | `load_event()` 使用 `print` 输出错误 | 同上，历史遗留 |
| 3 | [event_index.py:L863,869](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/event_index.py#L863) | `_sync_file()` 使用 `print` 输出错误 | 同上，历史遗留 |
| 4 | `add()` docstring | docstring 未更新以反映新增的 `source_chunk_id`/`source_layer` 参数说明 | 补充 Args 描述 |
| 5 | `query_coalesced()` | 缺少参数输入验证（如 `source_layer` 值必须为 `l1`/`l2`） | 数据库 CHECK 约束已兜底，但在 API 层做前置校验更友好 |

> **说明**：P2-1/2/3 均为历史遗留 `print` 语句，不在 M 专家本次修改范围内。按契约规则"不为了清空历史 lint 改旧模块"，此处仅记录，不要求 M 专家修复。

---

## 5. 代码卫生（Rule §16.6）

| 检查项 | 结果 |
|--------|------|
| 废弃代码（Dead Code） | ✅ 无新引入废弃代码 |
| 冗余占位（`pass`/`...`） | ✅ 无 |
| 悬挂 TODO | ✅ 无新增 |
| Import 清理 | ✅ 无未使用 import |
| `except Exception` 吞异常 | ✅ Task 003 新增代码无吞异常 |
| `print` 代替 `logger` | ⚠️ 历史遗留（见 P2），非本次引入 |

---

## 6. 静默降级检查（Rule §20.4）

| 检查项 | 结果 |
|--------|------|
| `except ImportError` 返回假数据 | ✅ 不存在 |
| `try/except...pass` 掩盖核心功能 | ✅ 不存在 |
| `raise XxxError("disabled")` 死代码 | ✅ 不存在 |
| 所有降级路径有 `logger.warning` | N/A（Task 003 无降级路径） |

---

## 7. 设计一致性对齐（与 V6.3 设计文档）

| 设计文档条目 | 代码实现 | 对齐 |
|-------------|---------|------|
| 定案 #9: `source_chunk_id TEXT DEFAULT NULL` | L143 | ✅ |
| 定案 #10: `source_layer ...CHECK` NULL 安全 | L145-148 | ✅ |
| 定案 #21: `idx_chunk_layer` 组合索引 | L151-154 | ✅ |
| 定案 #22: CHECK 约束 NULL 安全写法 | L147 `IS NULL OR` | ✅ |
| 定案 #14: COALESCE UNION ALL 两路 | L963-978 | ✅ |
| 定案 #18: EXISTS/NOT EXISTS 过滤 | L968-973 | ✅ |
| 定案 #19: NULL→路径 B | L976-977 | ✅ |
| §4.2 DDL 逐行对比 | 全部对齐 | ✅ |
| §5.1 SQL 语义等价 | ✅（冗余 EXISTS 已简化） | ✅ |
| §5.2 per-chunk per-type SQL | L1001-1012 | ✅ |

**结论**：代码与设计文档 **100% 对齐**，无偏离。

---

## 8. 最终结论

| 维度 | 评估 |
|------|------|
| 正确性与鲁棒性 | ✅ 全部测试通过，SQL 语义正确 |
| 向后兼容 | ✅ 现有 `add(event, path)` 调用无需修改，`query()` 行为不变 |
| 设计一致性 | ✅ 与契约和 V6.3 设计文档 100% 对齐 |
| 代码卫生 | ✅ 无新引入问题（历史遗留 P2 已记录） |
| 测试覆盖 | ✅ 契约要求 ≥8 项，实际 11 项，超额完成 |
| 全量回归 | ✅ 847 passed / 0 failed |

**审计判定：✅ PASS — Task 003 验收通过。**
