# DIMCAUSE - Global Backlog & Tech Debt

> 依据 `fix-all-bugs.md` 规则 3 创建。  
> 统一登记所有超出当前分支 Scope 的全局 Bug、历史技术债、以及因"妥协"而遗留的未实现设计。  
> **最后更新**: 2026-03-17（Why 对象证据显示 / 解释层接线对齐）

---

## 🔴 P0 — 阻断级（正确性/安全）

### ~~P0-1: EventIndex 未接入 SchemaValidator（数据质量防线缺失）~~ (FIXED)
- **修复事实**: `event_index.py:add()` 与 `add_if_not_exists()` 已调用 `get_schema_validator().validate(event)`，运行时卡口已接入。
- **后续遗留**: 白名单治理问题保留在 `P1-2`，不再以“零接入”计为 P0。

### ~~P0-2: wal.py / auth.py 路径硬编码为 `~/.mal`（品牌残留幽灵）~~ (FIXED)
- **修复事实**:
  - `wal.py` 默认路径已对齐 `~/.dimcause/wal.log`，并支持 legacy `~/.mal/wal.log` 自动迁移（Task 020）。
  - `auth.py` 默认路径已对齐 `~/.dimcause/agents.json`，并支持 legacy `~/.mal/agents.json` 自动迁移（Task 021）。
  - `repair_queue.py` 默认路径已对齐 `~/.dimcause/repair_queue.jsonl`，并支持 legacy 迁移（Task 023）。
- **后续说明**: 仍有部分 `.mal` 文案/测试夹具残留，但不再是运行时默认路径风险。

### ~~P0-3: wal.py 未与 EventIndex/Orchestrator 集成~~ (RECLASSIFIED)
- **纠偏事实**: `WriteAheadLog` 已在 `services/pipeline.py`（`append_pending`/`mark_completed`）和 `daemon/manager.py`（`recover_pending`）被调用。
- **重分类**: 原“零调用”结论失真，降级为 `P1-8`（覆盖范围不完整）。

### ~~P1-8: `dimc why` 已接入因果链，但解释策略仍偏 V5 风格~~ (FIXED)
- **修复事实**:
  - `core/history.py` 已保留 `from_causal_chain` provenance，不再在 `Event -> GitCommit` 适配时丢失
  - `cli.py:why()` 现将因果链事件独立渲染为“因果链证据”一等输出段落
  - `cli.py:why()` 现已在 `metadata.object_projection` 存在时输出“对象证据区”，至少显示 `Material` 与首条 `Claim.statement`
  - `DecisionAnalyzer` prompt 已显式提高 Causal Evidence 权重，并会消费 `object_projection` 中的 Material/Claim，而非退回纯时间线叙事
- **回归测试**:
  - `tests/test_cli_history.py`
  - `tests/test_history_causal.py`
  - `tests/test_brain_decision.py`
- **后续说明**: 若继续打磨，剩余已是排序/压缩层面的体验优化，不再属于 P1 级功能缺失。

---

## 🟠 P1 — 架构欠债

### ~~P1-1: `api_contracts.yaml` 中 `search_engine_search` 合约名不匹配~~ (FIXED)
- **修复**: Task 016 Audit Remediation (`63135280`) — `verify_contracts.py` 支持 `actual_name` 字段，`api_contracts.yaml` 补充 `actual_name` 和 `use_reranker` 参数。

### ~~P1-2: SchemaValidator 的 LEGACY_WHITELIST 白名单治理缺失~~ (FIXED)
- **修复事实**:
  - `SchemaValidator` 已将裸 `LEGACY_WHITELIST` 收敛为显式 `LegacyTypePolicy` registry
  - `validate()` / `validate_type()` 现返回结构化 `ValidationResult`，可区分 ontology / legacy
  - `EventIndex.add()` / `add_if_not_exists()` 会为 legacy 写入注入 `_schema_legacy` provenance
  - `EventIndex.get_legacy_type_counts()` 可直接统计当前索引中的 legacy 存量
- **回归测试**:
  - `tests/core/test_schema_validator.py`
- **后续说明**: 下一阶段不再是“白名单完全无治理”，而是持续收缩 legacy 生产链路，并在可行处将类型迁回 ontology 主类。

### P1-3: 全量测试红线清理（Task 3.1）
- **现状**: 103 个测试文件用 `@pytest.mark.legacy_debt` 隔离，盲区 Bug 状态完全未知。

### P1-9: 全量 skipped 测试债清理（30 项）
- **审计事实**: `pytest -q -rs` 当前为 `1103 passed, 30 skipped`。
- **分类结果**:
  1. 过时测试：`3`
  2. 手工 / 完整环境测试：`2`
  3. 真实数据 / 真实代码库保护性阻断：`4`
  4. 环境依赖缺失：`1`
  5. 真正未实现的测试：`20`
- **当前入口**: [`SKIPPED_TESTS_REMEDIATION_PLAN.md`](./SKIPPED_TESTS_REMEDIATION_PLAN.md)
- **处理顺序**:
  1. 先清零过时测试
  2. 再把受保护测试迁出默认套件
  3. 明确依赖门槛
  4. 最后按产品路线补齐未实现测试

### ~~P1-4: LLMLinker 模型名硬编码（`deepseek-chat`）~~ (FIXED)
- **修复事实**:
  - `dimc config set KEY VALUE` 已落地，可写入 `llm_primary.model` / `llm_primary.provider` 等嵌套配置
  - `cli.py` 中 `get_analyst()` / `why()` 已优先读取项目 `llm_primary` 配置，不再把模型名硬编码在命令层
  - `reasoning/llm_linker.py` 现已按 `self.model` 解析 provider/model，不再在 `_analyze_pair()` 中回退成固定 `deepseek-chat`
- **回归测试**:
  - `tests/test_config.py`
  - `tests/test_cli_detect.py`
  - `tests/test_llm_linker.py`
  - `tests/test_deepseek_client.py`

### ~~P1-5: 专用 `events_cache` 表 / 查询缓存层仍未落地~~ (FIXED)
- **修复事实**:
  - `core/event_index.py` 现已创建并维护独立 `events_cache` 与 `event_file_refs` 表
  - `add()` / `add_if_not_exists()` / `update_cache()` 会写穿缓存；初始化会对历史 `json_cache` 做回填
  - `load_event()` 可在主表 `json_cache` 缺失时回退到 `events_cache`
  - `get_by_file()` 已优先使用 `event_file_refs` 精确/后缀匹配，再回退到 legacy LIKE
- **回归测试**:
  - `tests/test_event_index.py`
  - `tests/test_event_index_query_cache.py`
- **后续说明**: LRU 淘汰、查询统计与更细粒度检索优化仍可继续做，但不再属于“查询缓存层缺席”。

### ~~P1-7: WAL 未覆盖 EventIndex 主写入链路（部分集成）~~ (FIXED)
- **修复事实**: `EventIndex.add()` / `add_if_not_exists()` 已接入独立 sidecar WAL（`index.wal.log`），写入前记录 pending、提交后 mark completed、异常时 mark failed，并在初始化时自动重放待完成写入。
- **物理核查**:
  - `core/event_index.py` 新增 EventIndex 专属 WAL payload / replay 逻辑
  - `tests/test_event_index_wal_bridge.py` 覆盖成功、幂等、失败、恢复四条路径
- **后续说明**: daemon/pipeline 仍使用各自的 `active.log` 链路；两种 WAL 现已按职责分层，而非共享混合 payload。

### ~~P1-6: 全量测试环境敏感与性能测试“名实不符”~~ (FIXED)
- **修复**: Task 016 Audit Remediation (`63135280`) —
  1. `test_1k_baseline` 阈值 0.1s → 0.5s，`test_10k_stress` 阈值 0.5s → 3.0s。
  2. 造假 `test_50k_extreme_scale` 废除，重写为诚实 `test_5k_batch_stress`（真实 5k 节点 + 真实断言）。
  3. `test_auth.py` 便捷函数用 monkeypatch 将全局 `_registry_instance` 隔离到 `tmp_path`。
  4. `test_base_watcher.py` 为 watchdog Observer 用例添加 `DIMCAUSE_SKIP_WATCHER` skipif 标记。

---

## 🟡 P2 — 体验与质量


### P2-1: Context 权重污染（向量搜索无 Reranker 衰减）
- `VectorStore.search` 返回 50 条结果直接灌给 LLM，无 Anti-Forgetting 权重衰减。

### P2-2: Pyre2 静态分析配置（Task 3.2）
- `search_path` 未配置，IDE 里遍地虚假 `Could not find import` 报错。

### P2-3: Timeline 仍缺少会话衰减视图
- **修复事实**: `dimc timeline` 现已具备 `session_id/job_id` 边界追踪与展示，不再只是裸时间排序。
- **剩余缺口**: Session 级衰减、跨 session 聚合压缩等更高阶时间线分析仍未实现。

### P2-4: MCP Server 配置修复（任务 1.7）
- 外部 AI 链路（MCP 客户端兼容性）待修复。

### P2-5: README 和发布文档对齐（任务 1.9）
- 面向开源社区的 README 未同步最新架构和使用方式。

---

## ❌ 旧 BACKLOG 已被错误登记、实际已修复的条目

| 旧描述 | 实际物理状态 | 修复任务 |
|:---|:---|:---|
| "EventIndex 并发写入锁缺失 (P0)" | `event_index.py:651, 1022` 已有 `BEGIN IMMEDIATE` | 已修（Task 014 前后） |
| "VectorStore 缺少 BEGIN IMMEDIATE 写锁" | `vector_store.py:225, 454` 已有写锁 | Task 014 ✅ |
| "TUI 越权直写图谱" | `app.py` 越权代码已铲除 | Task 014 ✅ |
| "Ruff 48 个历史报错" | Ruff 全绿，0 errors | Task 015 ✅ |
| "DRY 违规：`_local_naive_to_utc` 重复" | grep 无结果，已消除 | 已修 |
| "EventIndex 未接入 SchemaValidator" | `add()/add_if_not_exists()` 已调用 `validate(event)` | Task 008/后续整合 ✅ |
| "wal/auth 路径硬编码 `~/.mal`" | 默认路径已切到 `~/.dimcause`，并支持 legacy 自动迁移 | Task 020/021/023 ✅ |
