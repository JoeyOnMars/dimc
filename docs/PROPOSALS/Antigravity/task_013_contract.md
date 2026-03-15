# Task 013 Contract: Auto-Embedding 数据写入链路（P + G 联合审定版）

**risk_level: high**

> ⚠️ **身份指令 (ROLE ANCHOR)**
> 阅读并执行本契约时，你现在的身份是 **M 专家（Claude Code / 落地工人）**。
> 你必须绝对服从第 6 节《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

---

## 1. 目标与背景 (Goal & Context)

**前置依赖：** Task 012 已修复并验收 `VectorStore.search()` 读链路，本任务只负责"写入链路接通"。

**现状：** 会话结束（`dimc down`）时未自动进行向量化，导致新产生的 Event 写入 `events` 表后无法被向量检索命中（"存入了但搜不到"）。

**目标：** 在 `dimc down` 收尾阶段引入 Auto-Embedding 兜底机制：自动找出"尚未嵌入"的事件，批量嵌入并写入 `event_vectors` / VectorStore，形成闭环。

---

## 2. 详细设计 (Detailed Design)

### 2.1 挂载点（必须实现）

- **文件：** `src/dimcause/services/session_end.py`
- **挂载点：** `SessionEndService.execute()` 中 `_run_extraction_pipeline(session_id)` 之后
- **新增方法：** `_auto_embed_recent_events(self) -> None`
  - 不接收 `session_id` 参数，覆盖所有孤儿事件，避免断电/崩溃遗留的历史孤儿永久丢失

### 2.2 High-Water Mark（差集 + 安全上限）

**核心原则：** 兜底清理必须覆盖"所有尚未嵌入的事件"，不得绑定当前 `session_id` 过滤。

**强制 SQL（G 代码审计时逐字比对）：**

```sql
SELECT id, json_cache
FROM events
WHERE id NOT IN (SELECT DISTINCT event_id FROM event_vectors)
ORDER BY id ASC
LIMIT :limit
```

- `ORDER BY id ASC`：从最老的孤儿开始补，防止旧孤儿被新数据淹没
- `LIMIT`：默认 30，可配置，不得超过 100

**🔴 G 博士风险 1：`event_vectors` 表可能不存在**

在从未执行过向量化的环境中，`event_vectors` 表由 `VectorStore._init_vector_db()` 按需创建，但若未调用过 `VectorStore` 进行写入，该表不存在。直接执行上述 SQL 会抛 `sqlite3.OperationalError: no such table: event_vectors`，导致 `dimc down` 崩溃。

**M 专家必须实现的防护方案（二选一，优先选方案 A）：**

方案 A（推荐）：查询前先建表，调用 `VectorStore._init_vector_db(conn)` 确保表存在。
方案 B（可接受）：用 `try/except sqlite3.OperationalError` 捕获"no such table"错误，静默 `return`（附 `logger.info` 说明）。

### 2.3 写入实现（批量推理，解决 N+1 雪崩）

**背景：** 现有 `VectorStore.add(event)` 是单条写入，内部调用 `embed_chunks([single_chunk])`，batch_size=1。若有 30 条孤儿，循环调用 30 次 = 30 次模型 forward pass（雪崩）。

**授权：** 本任务允许在 `src/dimcause/storage/vector_store.py` 新增 `add_batch` 方法（不改 search，不改模型加载框架）。

**新增公开方法：**

```python
def add_batch(self, events: List[Event]) -> None:
    """批量添加 Events 到向量库，一次 forward pass 完成所有 embedding"""
```

行为约束：
- 内部构造所有 events 的 Chunk，**一次性**传入 `embed_chunks(chunks)`，利用 Sentence-Transformers 的批量推理
- 数据落库调用 `store_vectors(chunks, embeddings)`，已有 `INSERT OR REPLACE`，天然幂等
- 禁止改动 `VectorStore.search` 的任何逻辑

**🔴 G 博士风险 2：模型未释放，驻留内存**

现有 `VectorStore.search()` 的 finally 块中调用 `self.release_model()`，但 `add()` 和新增的 `add_batch()` 均无此调用。在 `dimc down` 场景下，embedding 完成后模型继续驻留 MPS/GPU 内存，影响后续操作。

**M 专家必须实现：** `add_batch()` 执行完毕后（成功或失败均需），在 `_auto_embed_recent_events` 的 `finally` 块中调用 `vector_store.release_model()`。

### 2.4 调用顺序（`_auto_embed_recent_events` 内部逻辑）

```
1. open db_path → 确保 event_vectors 表存在（防护风险 1）
2. 执行差集 SQL，获取孤儿事件列表
3. 解析 json_cache → List[Event]（解析失败的条目 warning 跳过）
4. try: add_batch(events)
   except Exception:
     降级逐条 add(event)，每条 try/except，失败只 warning 不抛出
5. finally: vector_store.release_model()（防护风险 2）
6. 打印 "Auto-embedded N events" 或 "Auto-embedded N events (with K failures)"
```

无论步骤 4 发生何种异常，`dimc down` 的其余清理步骤不得被中断。

---

## 3. 物理边界与授权范围 (Scope Exclusivity)

**🟢 允许修改的文件：**
- `src/dimcause/services/session_end.py`（新增 `_auto_embed_recent_events`，在 `execute()` 内调用）
- `src/dimcause/storage/vector_store.py`（仅新增 `add_batch`，禁止改动其他方法）
- `tests/services/test_session_end.py`（新增，若目录不存在则创建）

**🔴 严禁触碰：**
- 禁止修改 `VectorStore.search`（Task 012 读链路已闭环）
- 禁止直接修改 `VectorStore.add`（只新增 `add_batch`）
- 禁止任何形式的全表盲扫 SQL（`SELECT * FROM events` 无 WHERE 无 LIMIT）
- 禁止修改核心架构文档

---

## 4. 测试与验证期望 (Acceptance Criteria)

### 4.1 自动测试（必须）

仅跑局部测试：

```bash
source .venv/bin/activate && pytest tests/services/test_session_end.py -v
```

**必须覆盖的测试用例（M 专家负责编写）：**

1. `test_auto_embed_batch_success`：mock 2 条孤儿事件，断言 `add_batch` 被调用一次，`add` 未被调用
2. `test_auto_embed_partial_failure`：`add_batch` 抛异常，断言降级调用 `add` 共 2 次，`dimc down` 不中断
3. `test_auto_embed_no_event_vectors_table`：mock `sqlite3.OperationalError`，断言方法静默返回，不抛出
4. `test_auto_embed_release_model_called`：断言无论成功/失败，`release_model()` 都被调用

### 4.2 手动验证（由 G 出具审计报告前完成）

1. `dimc up`
2. 产生 ≥5 条带特征词的事件（含 1 条极长内容模拟异常）
3. `dimc down`，观察输出必须包含 `Auto-embedded N events` 日志
4. `dimc search "特征词" --mode vector --top-k 5` 必须命中 ≥1 条

通过标准：
- `dimc down` 不得因 embedding 失败而崩溃
- 失败事件有明确 warning 日志
- 成功事件可被向量检索命中

---

## 5. 🛡️ G 专家审计门禁 (AUDIT HANDOVER GATE)

当收到 M 专家的 `[PR_READY]` 后，G 在出具 `task_013_audit.md` 前**必须逐项完成**：

1. `.venv` 中运行 `scripts/check.zsh`，0 error，否则打回
2. 审查 SQL：必须是"差集 + LIMIT"，无 `session_id = ?` 过滤
3. 审查风险 1 防护：确认存在 `event_vectors` 表不存在时的安全降级逻辑
4. 审查风险 2 防护：确认 `finally` 块调用了 `release_model()`
5. 审查批量写入：确认存在 `add_batch` 且内部一次 forward pass（不是 for-loop 调 add）
6. 审查局部失败隔离：确认 `add_batch` 失败降级到逐条，单条失败只 warning 不中断

---

## 6. 🎯 M 专家强制开工协议 (MANDATORY STARTUP PROTOCOL)

一旦看到本契约获得 User 盖章的 `Approved / 已确认`，立刻按顺序执行：

1. 新开分支：
   ```bash
   git switch main && git pull
   git switch -c feat/task-013-auto-embedding
   ```

2. 仅在授权范围（第 3 节）内修改代码

3. 提交与推送：
   ```bash
   git commit -m "feat(task-013): auto-embedding write path with batching, orphan sweep, release_model"
   git push -u origin HEAD
   ```

4. 仅跑局部测试（禁止全量）：
   ```bash
   source .venv/bin/activate && pytest tests/services/test_session_end.py -v
   ```

5. 输出 `[PR_READY]`，附带：
   - pytest 输出截图
   - `dimc up / down / search` 终端日志
   - 证明"差集 SQL + event_vectors 防护 + 批量 + release_model + 局部失败隔离"的关键代码片段

---

*本契约由 G 博士（Antigravity）基于 P 博士草稿审定，整合 2 条额外风险防护，于 2026-03-02 定稿。*
