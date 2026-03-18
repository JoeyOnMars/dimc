# DIMCAUSE - Global Backlog & Tech Debt

> 依据 `fix-all-bugs.md` 规则 3 创建。  
> 统一登记所有超出当前分支 Scope 的全局 Bug、历史技术债、以及因"妥协"而遗留的未实现设计。  
> **最后更新**: 2026-03-18（3.1 第二阶段第二刀：data_pipeline 首条用例落地）

---

## 🔴 P0 — 阻断级（正确性/安全）

### ~~P0-1: EventIndex 未接入 SchemaValidator（数据质量防线缺失）~~ (FIXED)
- **修复事实**: `event_index.py:add()` 与 `add_if_not_exists()` 已调用 `get_schema_validator().validate(event)`，运行时卡口已接入。
- **后续遗留**: 白名单治理问题保留在 `P1-2`，不再以“零接入”计为 P0。

### ~~P0-2: wal.py / auth.py 路径历史命名残留（品牌残留幽灵）~~ (FIXED)
- **修复事实**:
  - `wal.py` 默认路径已统一为 `~/.dimcause/wal.log`，并移除旧命名目录的自动迁移逻辑。
  - `auth.py` 默认路径已统一为 `~/.dimcause/agents.json`，并移除旧命名目录的自动迁移逻辑。
  - `repair_queue.py` 默认路径已统一为 `~/.dimcause/repair_queue.jsonl`，并移除旧命名目录的自动迁移逻辑。
- **后续说明**: 运行时已无旧品牌路径逻辑，剩余工作主要是历史日志资产的分层治理。

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
- **现状**: `legacy_debt` 隔离标记已清零；当前主战场是剩余 `21 skipped + 4 deselected protected` 的测试债分批收口。

### P1-9: 全量 skipped / protected 测试债清理（当前 21 skipped + 4 deselected）
- **审计事实**: `source .venv/bin/activate && pytest -q -rs` 当前为 `1114 passed, 21 skipped, 4 deselected`。
- **分类结果（skipped=21）**:
  1. 过时测试：`0`（已清零）
  2. 手工 / 完整环境测试：`2`
  3. 环境依赖缺失：`0`（已清零）
  4. 真正未实现的测试：`19`
- **受保护测试（deselected=4）**: 默认不进主套件，仅在 `--run-protected` 下执行。
- **当前入口**: [`SKIPPED_TESTS_REMEDIATION_PLAN.md`](./SKIPPED_TESTS_REMEDIATION_PLAN.md)
- **处理顺序**:
  1. 保持受保护测试留在默认套件外（仅 `--run-protected` 执行）
  2. 明确依赖门槛
  3. 最后按产品路线补齐未实现测试
- **本轮进展**:
  - 已移除 2 条不再属于 live 产品面的过时 skipped
  - 已把 1 条旧 history skipped 改写为当前 `history --no-interactive` CLI 测试
  - 已将 `tests/test_extractors.py::test_litellm_client_with_mock` 从无条件 skip 改为可执行 mock 测试
  - 已将 `tests/integration/test_data_pipeline.py::test_ingest_to_markdown_write` 从 TODO skip 改为可执行集成断言
  - 默认套件基线已从 `1103/30` 收敛到 `1114 passed, 21 skipped, 4 deselected`

### ~~P1-10: 信任梯度 risk_level 未落地~~ (FIXED)
- **修复事实**:
  - `docs/coordination/task_packet.template.md` 已将 `risk_level: low | medium | high` 收为正式字段
  - `scheduler intake` / `kickoff` 生成的任务卡 frontmatter 已默认写入 `risk_level`
  - `load_task_card()`、`session bundle` 与 `scheduler summary/closeout` 已统一读取并使用 `risk_level`
  - 自动收口现在以 `risk_level` 为准：`low` 默认自动候选，`medium` 进入人工 review，`high` 进入人工 approval
- **回归测试**:
  - `tests/scheduler/test_cli_scheduler.py`
  - `tests/scheduler/test_orchestrator_closeout.py`
  - `tests/scheduler/test_runner.py`
  - `tests/test_pr_ready.py`
  - `tests/test_preflight_guard.py`
- **后续说明**: 当前已形成个人本地半自动的风险分级底座；更细的团队审批流属于后续 P3/P4 档位扩展，不再属于“未落地”。

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

### ~~P2-2: 静态分析配置基线（Task 3.2）~~ (FIXED)
- **修复事实**:
  - 仓库根目录已新增 `.pyre_configuration`
  - `source_directories` 与 `search_path` 已统一指向 `src`
  - `pyproject.toml` 的 `[tool.mypy]` 已显式声明 `mypy_path = "$MYPY_CONFIG_FILE_DIR/src"`
- **后续说明**:
  - 当前 live 类型检查器是 `mypy`，不是 Pyre2；CI 与审计入口也都跑 `mypy`
  - `mypy src/dimcause --ignore-missing-imports` 目前仍有大量真实类型错误；这属于后续类型债，不再归为“缺少搜索路径配置”
  - 当前仓库仍未内置 `pyre/pyre2/pyrefly` 可执行；运行级验证依赖开发机自行安装对应工具

### P2-3: Timeline 仍缺少会话衰减视图
- **修复事实**: `dimc timeline` 现已具备 `session_id/job_id` 边界追踪与展示，不再只是裸时间排序。
- **剩余缺口**: Session 级衰减、跨 session 聚合压缩等更高阶时间线分析仍未实现。

### ~~P2-4: MCP Server 配置修复（任务 1.7）~~ (FIXED)
- **修复事实**:
  - `dimc mcp serve` 已支持 `stdio` / `http` 两种传输模式
  - `--transport` 非法值现在会直接报错，不再静默回退到 `stdio`
  - `docs/guides/MCP_SETUP.md`、`docs/USER_GUIDE.md` 与 `docs/IDE_INTEGRATION.md` 已按 live 代码口径纠偏
  - `tests/test_mcp.py`、`tests/test_mcp_server.py` 与 `tests/test_cli_mcp.py` 当前为 `16/16` 通过，已覆盖 CLI 启动层 smoke test
- **后续说明**: 后续若继续扩展，只剩特定外部客户端接入验证；这不再属于“配置修复未完成”。

### P2-5: README 和发布文档对齐（任务 1.9）
- **修复事实**:
  - `README.md` / `README_zh-CN.md` 已同步当前架构入口与仓库角色。
  - README 安装说明已按 live 发布事实改为源码安装，不再提前宣称 `pip install dimcause` 可用。
  - `docs/dev/V6.0_ROADMAP.md` 与 `docs/STATUS.md` 已拆开“文档对齐完成”和“PyPI 尚未发布”两个状态。
- **后续说明**: 剩余未完成项只属于 `Release 准备`，不再属于“任务 1.9 文档对齐”。

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
| "wal/auth 路径历史命名残留" | 默认路径已切到 `~/.dimcause`，且已移除旧目录自动迁移逻辑 | Task 020/021/023 ✅ |
