# 🚑 Dimcause Rehabilitation Plan (P0)

**状态**: 历史分析快照；属于当时的修复方案，不作为当前正式计划。

**现状**: 项目处于 "脑死亡" 状态 —— 也就是有脑子 (Ontology/Graph) 但是没神经连接 (Wiring)。文档承诺的功能大多是空头支票。

**目标**: 拒绝重写，就地连接。用最小的代码改动，让系统 "活" 过来。

## 🛠️ P0 修复清单 (The "Make it Real" List)

### 1. 🩸 激活本体 (Activate Ontology)
**问题**: `Ontology.validate_relation` 是死代码。写入数据时没有任何检查。
**方案**:
- 在 `EventIndex.add()` (或 `MarkdownStore.save`) 中，**强制**调用 `Ontology.validate`。
- 如果违反本体定义（例如 `Commit` 没有 `realizes` 关系），根据 Strict Mode 抛出错误或警告。

### 2. 🕵️ 真实的审计 (Real Audit)
**问题**: `dimc audit` 只跑 Linter，不跑因果审计。
**方案**:
- 修改 `src/dimcause/audit/runner.py`。
- 引入 `dimcause.reasoning.validator.AxiomValidator`。
- 在 `run_audit` 流程中加入 `validator.validate(graph)` 步骤。
- 让 `dimc audit` 的输出真正包含 "Circular Dependency" 或 "Orphan Commit" 的警告。

### 3. 🕸️ 真正的图谱搜索 (Real Graph Search)
**问题**: `manual trace` 和 `search` 完全忽略图谱。
**方案**:
- 修改 `src/dimcause/search/engine.py`。
- 在 `trace` 方法中，使用 `NetworkX` 的 `shortest_path` 或 `bfs_tree` 寻找当前文件与 `Decision` 或 `Architecture` 的关联。
- 不再只是 grep 文本，而是回答 "Why did this change?" (通过图谱路径)。

### 4. 🧹 性能止血 (Git Import Fix)
**问题**: `GitImporter` 会撑爆内存。
**方案**:
- 将 `commit` 处理改为 Python Generator (流式)。
- 批量写入 VectorStore (Batch Insert) 而不是逐条写入。

## 📋 执行顺序

1.  **Fix Audit** (`src/dimcause/audit/`) - 最容易，且能立即暴露系统逻辑错误。
2.  **Fix Ontology Wiring** (`src/dimcause/core/`) - 保证新写入的数据是脏的。
3.  **Fix Search** (`src/dimcause/search/`) - 提升开发者体验。

*(此计划旨在将 "狗屎" 转化为 "肥料" —— 基础组件还是可用的，只是没组装好)*
