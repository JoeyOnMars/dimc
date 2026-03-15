# Task 004 物理审计与修复报告 (ExtractionPipeline)

## 审计人
Dimcause AI (Antigravity) 

## 审计目标
验证 M 专家（或前阶段）涉及 Pipeline 全生命周期流转的代码。包括：
1. `EventIndex.add_if_not_exists` 和 `delete_by_chunk_layer`
2. `ExtractionPipeline.run` 及内部 L1/L2/persist 等支持功能
3. 测试用例运行与边角缺陷审查

## 审计结果: ✅ PASS WITH CRITICAL FIXES

### 发现与修复的问题

1. **TOCTOU 竞态漏洞 (已修复)**  
   - 现象：`event_index.py` 中 `add_if_not_exists` 的原实现分为“读判定是否存在”和“执行写入”两步。
   - 风险：在并发 L1/L2 流水线下，如果两个进程同时检查到一个事件不存在，它们都会去插入，从而覆盖或重复计数。
   - 修复方案：利用 `sqlite3` 的排他锁 `BEGIN IMMEDIATE` 将“读是否存在 + 写数据”整合成一个原子事务。外层 `add()` 和 `add_if_not_exists()` 分别管理自己的锁，再调用同一个无事务包含锁内部写入实现的私有方法 `_add_to_conn`。  
   - *（测试 `tests/test_add_if_not_exists.py` 100% 通过）*

2. **L2提取事件数据库覆盖问题 (已修复)**
   - 现象：`ExtractionPipeline._persist_events` 中的原设计会将提取出的所有 L2 事件使用写死的 `fake_path = "/fake/chunks/{chunk.chunk_id}.md"` 发送到 `event_index.add` 里面持久化。
   - 风险：这会直接突破 SQLite 建表中强制要求 `UNIQUE markdown_path` 的约束。如果有复数个 L2/L1 events 针对同一个 trunk 产生，它们会相互覆盖只剩一个（最新的一个）。  
   - 修复方案：已在 `_persist_events` 的循环内使用 `f"/fake/chunks/{chunk.chunk_id}/{event.id}.md"` 的格式给予每个 Event 唯一的 markdown_path 来规避 `UNIQUE` 冲刷。

3. **端到端集成测试缺失 (已追加)**
   - 现象：原单元测试仅验证各个独立分支，而欠缺结合 Extraction、EventIndex_add 以及最终 `query_coalesced()` 联合合并的流转校验测试。
   - 补充方案：新增 `tests/integration/test_pipeline_e2e.py`，模拟真实 L2 模型返回值，运行完整流转并确保最终获取到的 Coalesced events 数据长度及层级一致。

## Regression 全量扫描
`pytest tests/` (基于 `eeda362` ) 共 860 项 —— 全部通过。

## 结论
Task 004 的逻辑已稳固、并发安全。准备可以继续启动 Task 005 `dimc extract` 子命令挂接 Watcher 集成。
