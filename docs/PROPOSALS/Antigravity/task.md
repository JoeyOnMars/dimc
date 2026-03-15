# DIMCAUSE Task Tracker

- [x] 恢复工作状态 (/dimc up)
  - [x] 激活虚拟环境并执行 `dimc up` 和 `dimc context`
  - [x] 阅读并检查全部系统规则 (.agent/rules)
  - [x] 分析最新的 `01-end.md` 以获取 RFC-001 的上下文
# Task Checklist

## V6.3 流式提取重构 (Streaming Extraction Refactor)

### Phase 1: 基础设施与 L0 落盘 (chunks.db 独立库)
- [ ] 创建 `chunks.db` 独立库及 `chunks` 状态机表 (包含 `chunk_id`, `status`, `confidence`, `needs_extraction`, `retry_count`, `last_error`, `extraction_failed`, `event_ids` 等)
- [ ] 实现 `chunks` 表采用 `Payload Nullification` 的定期 GC 策略
- [ ] 创建 `src/dimcause/extractors/event_watcher.py` (Watcher + 轮询兜底，实现 `offset` 游标防丢，完成 L0 原生落盘)

### Phase 2: L1 本地底座与严格的 Schema 校验网关
- [ ] 创建 `src/dimcause/extractors/chunking_manager.py` (Session 切分 + QMD Smart Chunk)
- [ ] 接入 `BGE-M3` 向量化，并实装正则提取 (确保 L1 提取永不跳过)
- [x] 实现基于 `api_contracts.yaml` 的 Schema 校验器 (所有落盘 Event 必须经此校验，拦截幻觉 JSON)
- [x] 更新 `models.py` 并完成 `migrations/002_add_chunk_columns.py`，新增 `related_event_ids`。 

### Phase 3: L2 云端提纯与隔离重写
- [ ] 创建 `src/dimcause/extractors/extraction_worker.py` (处理 `needs_extraction=True`，生成节点与局部属性)
- [ ] 补充有限重试与熔断机制 (网络错误退避重试，Schema 错误记录 `last_error` 降级保留)

### Phase 4: 因果图谱重组与平滑替换 (ADR-CL-001 v3.0 外键校验)
- [x] 设计 `extraction_pipeline.py`，添加 `_link_causal_edges` 的同步执行流，通过双向本体 O(1) 推理代替繁重的 N×M 时窗构建。
- [x] **高优先级**: 升级 `graph_store.add_relation()` 到 RMW (Read-Modify-Write) 模式并配合 `BEGIN IMMEDIATE` 以支持 `metadata` 去重合并。这是定案 25 的最后拼图。
- [ ] 替换旧版 `dimc down`，移除长文本全量收集旧逻辑
- [ ] 运行流式/降级/离线演习测试`test_forced_corruption_recovery` (1 个)
  - [ ] 修复残余的 indexer、trace、e2e 等失败用例 (~21 个)
