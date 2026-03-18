# DIMCAUSE 项目状态总表

**最后更新**: 2026-03-18（3.1 第二阶段首刀：extractors 去 skip）
**维护者**: 人工审核 + 代码验证

---

## 🚨 真实系统欠债与架构断层警报 (Reality Check)
> **2026-03-02 强制纠偏**: 过去 V6.1 进度的纯「✅ 完成」列表制造了 95% 竣工的严重虚假幻觉。根据 Honesty 规则，特此在首页直白置顶系统级断层。

| 隐患领域 | 纸面设计 (文档画饼) | 物理现实 (代码残缺) | 严重程度 |
|:---|:---|:---|:---|
| **L0 Orchestrator 现代化欠债** | `Orchestrator` 常驻调度，真实后台任务循环 | `scheduler/orchestrator.py`、`loop.py`、`runner.py` 已有可运行实现，V6 状态文件主干已统一；剩余主要是生产化策略收口。 | 🟡 中 |
| **契约监管不完整** | `api_contracts.yaml` 统管所有核心 API 签名 | 核心 7 条合约已核查通过（含 `search_engine_search`）；但 MCP/Timeline 等接口仍无合约覆盖。 | 🟡 中 |
| **存储 L2.5 查询缓存层已初步落地** | `events_cache` 表 Layer 2.5 缓存，`wal.log` 崩溃恢复 | `EventIndex` 现已具备独立 `events_cache` + `event_file_refs` 写穿缓存与回填逻辑，`load_event/get_by_file` 已消费该层；剩余主要是 LRU 淘汰与更细粒度查询优化。 | 🟡 中 |
| **L4 解释器剩余精修** | `dimc why` 穿透因果迷雾给出完美链路追踪 | `dimc why` 已通过 `get_file_history(..., use_causal_chain=True)` 接入 GraphStore 因果链，并将因果链证据与最小对象证据提升为一等输出对象；`DecisionAnalyzer` 也已显式消费 `object_projection` 中的 Material/Claim。当前剩余主要是更细粒度的排序、压缩和展示 polish。 | 🟡 中 |
| **L3 SchemaValidator 治理收口中** | `SchemaValidator` 上帝防线拦截一切非法时空关系 | 运行时卡口已接入写入链路，且 legacy 类型已从裸 `LEGACY_WHITELIST` 收敛为显式 policy registry，并写入 provenance/统计库存；剩余主要是持续压缩 legacy 生产面。 | 🟡 中 |

*详细处置清单及历史遗留测试债已转移至 [BACKLOG.md](dev/BACKLOG.md)，必须逐一清算。*

---

## 1. 版本状态

| 版本 | 阶段 | 状态 | 核心目标 |
|:---|:---|:---|:---|
| V5.0 | Init | ✅ 归档 | 基础架构搭建 |
| V5.1 | Experience | ✅ 完成 | Timeline + 审计 |
| V5.2 | Deep Insight | ✅ 完成 | Trace + History + Why |
| V6.0 | Ontology Engine | ✅ 完成 | 本体定义 + 因果推理 + 最终验证 |
| V6.1 | Production Polish | 🔄 进行中 | 审计修复 + 模型内存管理 |

> **说明**: V5.3 Core Polish 已并入 V6.0 Phase 1。品牌迁移（MAL → DIMCAUSE）已完成。

---

## 2. V6.0 进度

| Phase | 内容 | 状态 |
|:---|:---|:---|
| Phase 1 | 本体定义 | ✅ 完成（`ontology.py` + `ontology.yaml` + 测试） |
| Phase 2 | 因果推理引擎 | ✅ 完成 (Engine + Validator + Viz) |
| Phase 3 | 存储与交互 | ✅ 完成 (Pickle 已移除, SQLite Registry 已上线, MCP 6 端点已接入) |
| Phase 4 | 存储升级与互通 | ✅ 完成 | JSON-LD 导出 + Vector Store (SQLite-Vec) |

详见 [V6.0 路线图](dev/V6.0_ROADMAP.md)

---

## 3. V6.1 进度 (审计修复与 Production Polish)

| 任务 | 内容 | 状态 |
|:---|:---|:---|
| 任务 1.1 | 消除僵尸 ChromaDB 依赖 | ✅ 完成 (SQLite-vec 迁移) |
| 任务 1.1.1 | Reranker 模型缓存修复 | ✅ 完成 (China Mirror + Robust Loading) |
| 任务 1.1.2 | 模型内存管理 (用完即释放) | ✅ 完成 (RT-000 §4.2) |
| 任务 1.2 | 废弃 GraphStore.save() | ✅ 完成 (已添加 @deprecated) |
| 任务 1.6 | Session 日志聚合 | ✅ 完成 (Job Scanner + Auto-Detect) |
| P0-Safety | 移除 ChromaDB 依赖 | ✅ 完成 (Pyproject cleaned) |
| 任务 1.3 | BFS 逻辑 Bug 修复 | ✅ 基本修复 (SearchEngine._graph_search BFS+早停) |
| 任务 2.0 | Smart Scan (Session 对话扫描) | ✅ 完成 (mtime+内容双重过滤) |
| CLI Help | 双语帮助标准化 | ✅ 完成 (30+ 命令) |
| EventIndex | type Enum/str 兼容 Hotfix | ✅ 完成 (_build_query_sql) |
| RFC-001 | 两阶段 dimc down 设计 | ✅ 已实现 (§6-§7) |
| RFC-003 | Multi-Agent 架构 | 📝 已创建 |
| 任务 3.0 | 遗留测试修复 (test_config/state/cli) | ✅ 完成 (56/56 passed) |
| 任务 3.1 Prep | 隔离历史遗留测试 | ✅ 完成 (Marker 全局硬隔离 118 个断代用例) |
| 任务 3.1 | 全量测试红线清理 (The Big Cleanup) | 🔄 进行中（已清零 3 条过时 skipped + 1 条依赖缺失 skipped；当前全量基线为 `1113 passed, 22 skipped, 4 deselected`） |
| 任务 3.2 | 静态分析配置基线修复 | ✅ 配置已落地（`.pyre_configuration` + `mypy_path` 均指向 `src`；live 类型检查器为 `mypy`，剩余是类型错误本身） |
| Doc Align | 系统文档对齐 (Flow/Arch/Repo) | ✅ 完成 |
| Log Fix | 02-19 日志补录 | ✅ 完成 |
| Task 007-01 | Causal Core 时空硬锁与拓扑孤岛拦截 | ✅ 完成 (严格双防线构建) |
| Task 007-02 | ExtractionPipeline 适配防线 | ✅ 完成 (session_id 元数据注入) |
| CI 契约校验 | 契约签名自动化验证 + L1 不可变性检查 | ✅ 完成 (verify_contracts.py + check.zsh) |
| Git Hook | Pre-commit 物理闸门（禁止在 main 上直接提交） | ✅ 完成 (scripts/hooks/pre-commit) |
| Anti-Forgetting | 三层对话遗忘防御规则 | ✅ 完成 (.agent/rules/anti-forgetting.md) |
| Task 012 | VectorStore.search 读链路修复 | ✅ 完成 (L1/L2 全路径) |
| Task 013 | Auto-Embedding 写入链路（dimc down 兜底向量化） | ✅ 完成 (add_batch + release_model) |
| Task 014 | 核心双P0修复（VectorStore 写锁 + TUI 越权拔除） | ✅ 完成 (BEGIN IMMEDIATE + 强写铲除) |
| Task 015 | CI净化（Ruff 48错清零 + check.zsh 环境加固） | ✅ 完成 (Exit Code 0，24 passed) |
| Task 016 | 解释器因果引擎接入加深与纯化 | ✅ 完成 (SQL因果严丝剔透 + 跨库安全降级查询) |
| Task 017 | SearchEngine 混合检索接入 UNIX 通道 | ✅ 完成 (`semantic + graph + unix + text` 四通道候选融合) |
| 任务 1.7 | MCP Server 配置修复 | ✅ 完成 (`dimc mcp serve` stdio/http + transport 校验 + MCP CLI smoke test 16/16 通过) |
| 任务 1.9 | 发布前文档对齐 (README等) | ✅ 完成（README 已按 live 发布事实改为源码安装；PyPI 发布继续由 Release 准备跟踪） |
| 流程设施 | 信任梯度 (Risk Level) 分级落地 | ✅ 完成 (Task Packet + scheduler risk gate + closeout policy) |
| L3 防波堤 | SchemaValidator 运行时卡口 | 🔄 部分完成（EventIndex 写入链路已接入） |
| L0 调度 | Orchestrator 核心调度器 | 🔄 部分完成（基础调度循环 + active job awareness + runtime completion writeback + STATUS 合成任务上下文 + branch/worktree provisioning + session bundle + launch entrypoint + optional auto-launch + loop launch forwarding + stop/resume/cleanup/prune/reconcile 生命周期回收 + run/loop auto-reconcile 自愈 + inspect 可视化检查已实现 + V6 STATUS 主干解耦已实现，仍缺更深生产化收口） |
| L1 自动化 | dimc detect IDE 探测 | ✅ 完成（`dimc detect` + `dimc config enable` 已可用） |

---

## 4. 核心模块状态（代码验证）

| 模块 | 代码位置 | 状态 |
|:---|:---|:---|
| EventIndex (SQLite) | `core/event_index.py` | ✅ 已验证 (Schema v4, CRUD) |
| WAL | `utils/wal.py` | ✅ 已验证（daemon/pipeline + EventIndex sidecar recovery） |
| GraphStore (SQLite) | `storage/graph_store.py` | ✅ 已验证 (NetworkX Pathfinding, 结构边白名单 Task 007-01) |
| VectorStore | `storage/vector_store.py` | ✅ 已验证 (SQLite-vec, BGE-M3, 用完即释放) |
| Reranker | `search/reranker.py` | ✅ 已验证 (BGE-Reranker-V2-M3, 用完即释放) |
| SearchEngine | `search/engine.py` | ✅ 已验证 (四通道混合检索 + 内存生命周期管理) |
| DirectoryImporter | `importers/dir_importer.py` | ✅ 已实现 |
| GitImporter | `importers/git_importer.py` | ✅ 已验证 (Generator + Batch) |
| EventExtractor | `brain/extractor.py` | ✅ 已实现 |
| Ontology 加载器 | `core/ontology.py` | ✅ 已实现 |
| SemanticEvent | `core/models.py` | ✅ 已实现 |
| CausalLink | `core/models.py` | ✅ 已实现 |
| 因果推理引擎 | `reasoning/engine.py` | ✅ 已实现 (Hybrid: Time+Semantic) |
| CausalEngine | `reasoning/causal_engine.py` | ✅ 已实现 (时空双锁 + Global Broadcast Override, Task 007-01) |
| SchemaValidator | `core/schema_validator.py` | ✅ 已接入 EventIndex 写入链路（白名单治理待完善） |
| 公理验证器 | `reasoning/validator.py` | ✅ 已验证 (Audit Runner Integrated) |
| 图谱可视化 | `cli_graph.py` | ✅ 已实现 (ASCII/Mermaid) |
| MCP Server | `protocols/mcp_server.py` | ✅ 已实现 (6 端点, stdio/http 双模式) |

## 5. 最近修复
- **Scheduler Resume** (2026-03-08): 新增 `dimc scheduler resume <task>`，可基于已有 runtime 记录、session bundle 与 `launch.sh` 重新拉起已失败或已停止的任务执行链。恢复操作会校验任务未完成、当前 PID 未存活、launch script/worktree 仍存在，并把 `resume_count / resumed_at / launch_command / launch_pid / launch_log` 回写到 runtime state、session manifest 与 durable evidence。这样 scheduler 生命周期不再只有 run/stop，而是具备了最基本的恢复能力。
- **Scheduler Inspect** (2026-03-08): 新增 `dimc scheduler inspect <task>`，可以针对任意 runtime 任务直接查看当前状态、branch/worktree、launch command/PID/running 状态，以及 task packet、session bundle、launch log 等 artifact 的路径与存在性。`status` 继续适合看总览，`inspect` 则补上了“单个任务证据链到底落到了哪里”的定位能力，避免继续手翻 `scheduler_state.json` 和会话目录。
- **Indexer Job Path Inference** (2026-03-08): `core/indexer.py` 现在在 `parse_frontmatter()` 失败时，不会再把标准 job log 路径 `docs/logs/YYYY/MM-DD/jobs/<job_id>/end.md` 一律当作错误跳过。对于这种结构化 `end.md`，索引器会保守地从路径推断 `job_id/date/type`，并写入最小记录，补上了“无 frontmatter job end log 无法进索引”的检索断层。同时增加了反向保护测试，确保非标准路径不会被误推断索引。
- **Task 078 Scheduler Loop Auto Launch** (2026-03-08): `scheduler loop` 现在也支持 `--launch "..."`，并会把该命令转发给每一轮调度到的 `TaskRunner.run_task(..., launch=...)`。这意味着 auto-launch 不再只停留在单次 `scheduler run` 上，循环模式也能直接拉起实际执行命令，终于补上了“主循环仍然只会发任务、不真正启动执行链”的基层缺口。
- **Task 077 Scheduler Auto Reconcile** (2026-03-08): `scheduler reconcile` 不再只是一个需要手工敲的救火命令；`TaskRunner` 与 `SchedulerLoop` 现在会在判定 active job 之前自动调用 runtime reconcile，优先收口那些 `launch_pid` 已退出但 runtime 仍残留为 `running` 的 stale launched task。这样 `scheduler run` 不会再被已经死掉的旧 launch 误拦，`scheduler loop` 在等待 active job 时也能自愈，而不是永远卡在过期执行态上。
- **Task 076 Scheduler Runtime Reconcile** (2026-03-08): 新增 `dimc scheduler reconcile` 与 `Orchestrator.reconcile_running_tasks()`，对 runtime 中残留为 `running`、但其 `launch_pid` 已经退出的任务做保守收口：默认仅处理有明确 `launch_pid` 且进程已死亡的条目，并把任务自动回写为 `failed`；没有 `launch_pid` 的人工任务仍保留为 `running`，避免误判。reconcile 过程会把 `session_reconciled_at / session_reconcile_reason` 写回 runtime state、session manifest、durable evidence 和 launch log，从而补齐 “启动后异常退出但 scheduler 未显式 complete/fail” 的生命周期闭环。
- **Task 075 Scheduler Stop Running Launch** (2026-03-08): 新增 `dimc scheduler stop <task>`，可对 `scheduler run --launch ...` 拉起的运行中任务发送 `SIGTERM`（`--force` 时为 `SIGKILL`），并把任务安全回写为 `failed`。停止动作会把 `stop_signal / stop_requested_at / stop_reason` 写入 session manifest、durable evidence 与 runtime state，同时在 launch log 追加审计记录。这样 scheduler 生命周期首次具备了“启动之后还能被 scheduler 自己终止”的闭环，而不是只能靠外部手工 `kill`。
- **Task 074 Scheduler Runtime Prune** (2026-03-08): 新增 `dimc scheduler prune-runtime` 与 `Orchestrator.prune_runtime_tasks()`，可按保留期（`--retain-days`）裁剪 cleanup 后的过期 runtime 任务条目，默认仅处理 `done`，`failed` 需显式 `--include-failed`。该流程会跳过 active job、跳过 launch PID 存活任务、跳过尚未 cleanup 的工作区条目（避免误删仍有执行空间的任务），从而在不触碰 durable evidence 的前提下抑制 `.agent/scheduler_state.json` 无限膨胀。
- **Task 073 Scheduler V6 Status Decouple** (2026-03-08): `scheduler` 与 `docs/V5.2/STATUS-5.2-001.md` 的 legacy fallback 已切断，`Orchestrator` 与 `scheduler lint` 仅消费 `docs/STATUS.md`（V6 主干）作为调度真理源；相关测试也同步改为“无 modern STATUS 时报错而非回退 legacy”。L0 调度链路从状态源层面完成了 V6 解耦，不再被 V5.2 路径牵制。
- **Task 072 Scheduler Cleanup Lifecycle** (2026-03-08): 新增 `dimc scheduler cleanup`，可按安全策略回收 scheduler 任务空间：默认仅处理 `done` 任务（`failed` 默认保留审查），跳过 active job、跳过 launch PID 仍存活任务、仅允许回收 `/tmp/dimc-worktrees/` 下的 scheduler worktree。回收时不会触碰 `docs/logs/...` durable evidence，且会在 runtime state 写入 cleanup 结果（cleaned/skipped、原因、时间、分支/工作区回收标记）；若任务分支已合并到基线，还会清理本地分支。
- **Task 071 Scheduler Auto Launch** (2026-03-08): `scheduler run` 现在支持 `--launch "..."`，会通过 session bundle 的 `launch.sh` 在 provisioned worktree 中启动实际命令，并把 `launch_command / launch_pid / launch_log` 回写到 runtime state、session manifests 与 durable evidence。`scheduler status` 也会同步显示这些字段。L0 调度器不再只是“把启动入口准备好”，而是已经能按显式命令真正拉起一条执行链。
- **Task 070 Scheduler Launch Entrypoint** (2026-03-08): `scheduler` 生成的 session bundle 现在不只是静态文件夹；每个 worktree session 都会写出通用 `launch.sh`，可直接在 provisioned worktree 中执行任意 agent/terminal command。`scheduler status` 也会在存在 active runtime task 时直接显示 branch、worktree、session 目录和 launch script。L0 调度器从“留下证据文件”进一步迈到了“提供明确启动入口”。
- **Task 069 Scheduler Session Bundle** (2026-03-08): `scheduler run` 现在会在 provisioned worktree 内生成 `.agent/sessions/<job_id>/` 会话目录，并写入 `context.md`、`task-packet.md`、`session.json`、`README.md`。同一份 session manifest 也会被持久化到 `docs/logs/.../jobs/<job_id>/session.json`，并进入 runtime state / evidence metadata。这样每个接收任务的 agent 不再只拿到一个 worktree 路径，而是拿到一组稳定、可交接、可审计的执行文件。
- **Task 068 Scheduler Worktree Provisioning** (2026-03-08): `scheduler run` 现在不再把任务默认绑定到当前工作目录。`TaskRunner` 会先为任务 provision 独立的 `codex/...` 分支和 `/tmp/dimc-worktrees/...` worktree，再把这些信息写入 task packet、runtime state、task board 与 durable evidence。`scheduler complete/fail` 也会保留运行时记录的 branch/worktree，而不是在收尾时被当前 shell 分支覆盖。L0 调度器首次具备了“为任务分配独立执行空间”的真实能力，而不只是把当前仓库路径写进日志。
- **Task 067 Scheduler Task Events** (2026-03-08): `scheduler` 生成的任务证据不再只是文件痕迹。`task-packet.md` 现在会被写成合法的 `task` 事件 Markdown，并立刻同步进 `EventIndex` 与 `VectorStore`；`job-end.md` 也会作为 task result 事件同步入库，并通过 `leads_to` 把 `task-start -> task-result` 连起来。这样即使没有手写 `agent-task` 卡，scheduler 生成的任务包和结果也已经进入主检索/记忆链路，而不再只是停留在 `docs/logs` 目录里。
- **Task 066 Scheduler Evidence Artifacts** (2026-03-08): `scheduler run` 现在不只在 `tmp/coordination/` 里生成运行资产；它会同步把 `meta.json` 与 `task-packet.md` 落到 `docs/logs/.../jobs/<job_id>/`，把任务意图提升成可持久化证据。`scheduler complete/fail` 也会继续在同一 job 目录写入 `pr-ready.md`、`check-report.json`、`job-end.md` 并更新 `meta.json`，同时清理活跃 job marker。这样没有手写 `agent-task` 卡时，任务仍会留下可检索、可审计、可追结果的正式痕迹，而不只是停留在 `tmp/` 运行面。
- **Task 065 Scheduler Complete Task Packet Default** (2026-03-07): `scheduler complete` 现在会优先复用 `.agent/scheduler_state.json` 里记录的 `task_packet_file`；也就是说，`scheduler run` 生成出来的 task packet 不再只是一个摆设，完成验证会默认拿它来做白名单和检查约束，而不是要求用户再手动把同一路径传一遍。
- **Task 064 Scheduler Runtime Materialization** (2026-03-07): `scheduler run` 不再只生成 prompt 并等待手工复制；现在会同步产出 `tmp/coordination/task_packets/<task>.md`、维护 `tmp/coordination/task_board.md`，并把这些运行资产路径写入 `.agent/scheduler_state.json`。`scheduler complete/fail` 也会同步更新 task board 状态。L0 调度器首次拥有了可追踪的本地运行面，而不是只剩 stdout 上的一段上下文。
- **Task 063 EventIndex Link Roundtrip** (2026-03-07): `EventIndex` 不再把 `causal_links` 当成“只在表里躺着、load 时看不见”的半残能力。新增 `upsert_links()` 后，主链路与 `ExtractionPipeline` 写入的推理关系会同步回 `causal_links` 表；`load_event()` 现在会在存在 links 时返回 `SemanticEvent`，把 links 一并 roundtrip 回来。同时补了 `code_change -> Commit` 的 ontology 映射，避免合法的 `realizes/fixes` 在写回时被错误拦截。
- **Task 062 Pipeline Reasoning Bridge** (2026-03-07): `services/pipeline.py` 主链路不再只做“提取后存储”；现已保留 `RawData.metadata/files_mentioned` 到 `Event.metadata/related_files`，并在入库后对共享 `session_id/job_id/module_path/related_files` 的近期事件执行最小推理桥接。显式 `related_event_ids` 现在会按 ontology 落真实关系，`HybridInferenceEngine` 产出的合法关系也会写入 `graph_edges`。同时补上 `GraphStore.add_semantic_relation()`，避免 `implements/realizes/fixes/...` 被误塞进结构边接口，`SemanticLinker` 也不再生成本体中不存在的 `related_to`。
- **Task 061 Pipeline EventIndex 主写链路** (2026-03-07): `services/pipeline.py` 不再只写 Markdown/Vector/Graph；daemon/watcher 主链路现在会把事件同步写入 `EventIndex`，并统一使用 `data_dir/index.db` 与 `data_dir/graph.db`。这补上了 L1→L2 的真实元数据索引链路，也让 `Pipeline` 在 `EventIndex` 写入失败时停止 ACK，而不是悄悄留下“文件落盘了但查询面看不到”的断裂状态。
- **Task 060 Trace File Match Context** (2026-03-07): `TraceService` 的文件侧检索不再只返回“有哪些文件命中过”这种粗结果；现在 `git grep` 会以 fixed-string 模式返回首个命中位置，`trace` 输出会带上 `path:line` 和匹配片段。文件追踪从“弱文件列表”提升成了“最小可读证据”，更适合作为代码调查入口。
- **Task 059 Scheduler Priority Inference** (2026-03-07): 现代 `docs/STATUS.md` 调度表里的 `P0/P1/P2/P3` 前缀不再被忽略；`Orchestrator` 现会从状态表任务名中推断优先级，并在存在 `agent-task` frontmatter 的场景下用显式 `priority:` 覆盖默认值。调度排序不再把 `P0-Safety` 这类高优条目误当成普通 `P2`。
- **Task 058 Scheduler Prompt Fallback** (2026-03-07): `scheduler` 不再硬依赖 `.agent/agent-tasks/` 才能运行。当前仓库若只在 `docs/STATUS.md` 中登记任务、却没有独立任务卡，`Orchestrator.load_task_card()` 现会基于调度表合成最小任务卡与 prompt，并为 `scheduler` / `search` / `why` / `detect` 等任务推断相关文件。这样 `scheduler run <task>` 至少能稳定生成执行上下文，而不是在主流程上直接报“任务卡不存在”。
- **Task 057 StateWatcher Diff Context** (2026-03-07): `CodeStateDriver` 生成的状态事件不再只包含“发生了变化”的粗粒度提示；提交变化现会附带 `previous_commit`、`files_changed` 和截断后的 `diff_excerpt`，working tree 变化也会同步附带 `git diff HEAD` 的最小证据片段。这样进入 pipeline 的 `RawData` 不再只是状态脉冲，而是带有可追踪代码上下文的事实事件。
- **Task 056 Scheduler 完成验证与状态回写** (2026-03-07): 新增 `.agent/scheduler_state.json` 运行时状态登记，`TaskRunner` 启动任务时会写入 `running` 状态；`dimc scheduler complete` 现已复用 `scripts/pr_ready.py` 做真实完成验证，并把 `[PR_READY]` 报告与 check report 路径回写为 `done` 状态；`dimc scheduler fail --reason ...` 可显式登记失败原因。`Orchestrator.load_state()` 会将这些 runtime 状态覆盖到调度视图中，使 `plan/status/next task` 不再只依赖静态 `docs/STATUS.md`。
- **Task 055 StateWatcher Working Tree 感知** (2026-03-07): `CodeStateDriver` 不再只盯 `HEAD` 提交变化；现已同步追踪 `git status --short` 的 working tree 变化，并把变更文件列表写入 `RawData.files_mentioned/metadata`。这让 `watcher_state` 能覆盖“未提交代码状态变化”而不是只能看到 commit 后的结果。
- **Task 054 StateWatcher Runtime 接入** (2026-03-07): `StateWatcher` 已从失配的异步原型重写为可运行的 polling watcher，并正式接入 `DaemonManager` 与 `DimcauseConfig`。现在 daemon 可以按配置启动 `watcher_state`，轮询 Git HEAD 变化并把代码状态变化转成 `RawData` 送入现有 pipeline，不再只是仓库里一份没人调用的孤立草稿。
- **Task 053 Code Call Trace 索引化** (2026-03-07): `CodeIndexer` 新增 `code_calls` 调用点索引，`trace_symbol()` 不再只靠定义和 import 反推引用；函数调用与方法调用现在会以真实 call reference 进入 trace 结果，`TraceService` 也会把这类命中标成 `Called by ...`。同时为旧索引链路补了 `calls_indexed` 回填标记，避免升级后老库永远缺调用数据。
- **Task 052 Scheduler 执行态感知补齐** (2026-03-07): `Orchestrator` / `TaskRunner` / `SchedulerLoop` 现已接入 active job marker。调度器会在启动新任务前检查现有活跃 job，`scheduler loop` 在检测到未结束 job 时会等待或停止而不是重复发任务，`scheduler status` 也会显式显示当前活跃 job。顺带修复了 `--max-rounds 0` 原本实际跑 0 轮的实现错误。
- **Task 051 Active Job Marker 显式化** (2026-03-07): `record_job_start()` / `record_job_end()` 不再是空 hook；现已落地 `.agent/active_job.json` 显式活跃任务标记，`get_active_job()` 会优先消费该 marker，并在 marker 陈旧或路径失效时自动清理后回退到 orphan 扫描。CLI 与 workflow 的 job 生命周期不再完全依赖事后目录推断。
- **Task 050 Event Markdown 全量 roundtrip** (2026-03-07): `Event.to_markdown()` / `from_markdown()` 现已完整持久化并恢复 `source`、`confidence`、`raw_data_id`、`related_files`、`related_event_ids`、`entities`、`code_entities` 等关键字段；Markdown 不再只是 `json_cache` 失效时的缩水后备，而是真正可逆的真理源载体。
- **Task 049 代码方法依赖图补齐** (2026-03-07): `ASTAnalyzer` 现可稳定提取类限定方法名（如 `MyClass.method`），`build_code_dependency_graph()` 也已将方法纳入调用边源节点，并能把 `self.other()` 等方法调用正确解析到同类方法目标，不再默认漏掉 OOP 场景的 calls 关系。
- **Task 042 Continue.dev Watcher 落地** (2026-03-07): 新增 `ContinueWatcher`，`SourceType.CONTINUE_DEV` 与 `DimcauseConfig.watcher_continue_dev` 已打通，`DaemonManager` 可根据 `.logger-config` 初始化 Continue.dev 会话监听。`dimc detect` 现已将 Continue.dev 从 detect-only 升级为 ready，`dimc config enable continue_dev` 可直接落 watcher 配置。
- **Task 041 L1 自动化工具探测落地** (2026-03-07): 新增 `dimc detect`，可检测 Cursor / Claude Code / Windsurf / Antigravity 等接入目录，并区分 ready / detect-only；新增 `dimc config enable <tool>`，可将 Cursor / Claude / Windsurf watcher 或 Antigravity `export_dir` 写入项目 `.logger-config`。同时修正 `Config._detect_root_dir()` 的优先级，确保 CLI 在当前项目目录下落配置，而不是误写回 dimc 仓库根。
- **Task 043 EventIndex WAL 主写入桥接** (2026-03-07): `EventIndex.add()` / `add_if_not_exists()` 已接入独立 sidecar WAL，写前 pending、提交后 completed、异常 failed，并在初始化时自动重放待完成写入。至此，daemon/pipeline 与 EventIndex 两条写入链路都具备 WAL 级恢复闭环。
- **Task 045 配置层补齐与 LLM 模型解硬编码** (2026-03-07): 新增 `dimc config set KEY VALUE`，支持 `llm_primary.model` 等嵌套键写入；`why()` / `get_analyst()` 已优先读取项目 `llm_primary` 配置；`LLMLinker` 也已改为按配置的 provider/model 构建 `LiteLLMClient`，不再把 `deepseek-chat` 写死在运行路径里。
- **Task 047 EventIndex 查询缓存层落地** (2026-03-07): 新增独立 `events_cache` 与 `event_file_refs` 两层持久查询缓存，`EventIndex.add()/update_cache()` 现会写穿缓存，初始化时自动回填历史缺口；`load_event()` 可在主表 `json_cache` 缺失时回退到 `events_cache`，`get_by_file()` 也已优先走 `event_file_refs` 精确/后缀匹配，不再只靠 `json_cache LIKE` 暴力扫描。
- **Task 048 SchemaValidator 治理收口** (2026-03-07): `SchemaValidator` 不再依赖裸字符串 `LEGACY_WHITELIST`；现已引入显式 `LegacyTypePolicy` registry、结构化 `ValidationResult`、legacy provenance 注入和 `EventIndex.get_legacy_type_counts()` 存量统计，为后续逐类迁移 legacy 类型建立运行时观测面。
- **Task 046 Timeline 会话/任务边界升格** (2026-03-07): `TimelineService` 现已提取 `session_id/job_id` 上下文，`dimc timeline` 的 recent/range 模式会按 session/job 边界分组展示，daily stats 也新增 active sessions / jobs 聚合，不再只是裸事件列表。
- **Task 044 `dimc why` 因果证据升格** (2026-03-07): `get_file_history()` 现已保留 `from_causal_chain` provenance，`why` 输出新增“因果链证据”独立段落，`DecisionAnalyzer` prompt 也会显式提高因果证据权重，不再退回纯 Git/时间线叙事。
- **Why 最小对象证据落点** (2026-03-17): `cli.py:why()` 现在会在事件 `metadata.object_projection` 存在时输出“对象证据区”，至少显示 `Material` 与首条 `Claim.statement`；对应回归测试已补到 `tests/test_cli_history.py`，锁住有/无对象投影两条路径。
- **Why 解释层对象证据接线** (2026-03-17): `DecisionAnalyzer` 现在会把 `object_projection` 中的 `Material` 与首条 `Claim` 编进解释 prompt，并明确要求叙事显式使用对象证据解释因果来源；`tests/test_brain_decision.py` 与 `tests/test_cli_history.py` 已补充单测和 `why --explain` 集成测试。
- **Task 017 SearchEngine 混合检索接入 UNIX 通道** (2026-03-06): `SearchEngine.search()` 明确支持 `mode="unix"`，`_hybrid_search()` 已从旧的概念性混合检索收敛为 `semantic + graph + unix + text` 四通道候选融合；其中 `unix` 通道使用 `ripgrep` 对 Markdown 事件库做高精度召回，`rg` 缺失时静默降级为空结果，保持接口可用。
- **Task 016 解释器因果引擎接入加深与提纯** (2026-03-04): 铲除导致覆盖的 `nx.DiGraph` 老接口调用，全面使用 `GraphStore` 的内联原生 SQL 发起查询；引入了防波堤式同库降级搜索与精确三重排序锚定，拔除了 `content LIKE` 的模糊隐患。
- **Task 015 CI净化与环境加固** (2026-03-04): 清零 Ruff 历史 48 条错误（全仓 `src/` 全绿），加固 `scripts/check.zsh` 环境自动隔离（自动 `source .venv`），删除 `.pyc` 污染产物，修复重复测试行。`check.zsh` 物理实测 Exit Code 0，24 passed，Ruff 0 errors。
- **Task 014 核心双P0修复** (2026-03-03): `VectorStore` 写事务补齐 `BEGIN IMMEDIATE` 排他锁（消灭并发裸奔）；`TUI` 绕过 CausalEngine 直写图谱的越权链路（`_rebuild_graph_task`/`RebuildRequested`/重建按钮）物理铲除。`test_graph_store.py` GraphStore 导入断代修复。
- **Task 013 Auto-Embedding 写入链路** (2026-03-02): 实现 `SessionEndService._auto_embed_recent_events`，在 `dimc down` 收工时自动批量向量化孤儿事件。新增 `VectorStore.add_batch`（真批量 forward pass），差集 SQL + LIMIT 防雪崩，finally 保证 `release_model`，局部失败隔离不中断收工流程。新增 `Config.data_dir` 属性（修复 pre-existing bug）。
- **Task 011 决战 10k 节点 BFS 重构** (2026-03-02): 全面重构 `SearchEngine._graph_search` 的广度优先搜索底层，引入 Capped BFS (最大单层扇出 500，总探索截断 2000)，解决大节点查询性能瓶颈与卡顿危机。
- **Task 010 L1 数据防线自动化** (2026-03-01): 成功将 `DirectoryImporter` 无缝挂载注入 Orchestrator 心跳调度队列，初步打通了自动化后台常驻搜刮引擎。
- **Task 007-01 Causal Core 时空硬锁** (2026-02-25): 建立双入口架构隔离：`GraphStore` 退化为结构边哑存储（白名单：calls/imports/contains/depends_on），`CausalEngine` 成为因果边唯一入口（防线 A 时间锥 + 防线 B 拓扑孤岛/Global Broadcasting Override）。废除 `add_relation`，新增 `add_structural_relation` + `_internal_add_relation`。867 passed。
- **RFC-001 两阶段下线** (2026-02-20): 增加 `dimc down` 两阶段执行，利用 session.lock 获取精准窗口保障一致性。
- **遗留测试修复** (2026-02-19): test_config(3) + test_state(12) + test_cli(3) 全部修复至 56/56 passed。修复 context.py + cli.py orphan dict 访问 bug。
- **全量测试账单（历史快照）** (2026-02-19): 820 tests → 693 passed, 103 failed, 15 errors。103 failed 当时归为 6 类预存根因（GraphStore 42, state API 12, CLI 语言 19, workflow 12, model_config 3, 其他 15）；该历史账单已不单独保留为 live 报告，后续整改以当前 `BACKLOG`、roadmap 与专项清单为准。
- **Smart Scan** (2026-02-18): 实现 Task 2.0，基于 Session Start Time 自动匹配导出文件，双重过滤 (mtime+内容时间戳)。
- **BFS 图搜索修复** (2026-02-18): 修复 `SearchEngine._graph_search` TypeError/AttributeError，实现 BFS+提前终止优化。
- **CLI Help 标准化** (2026-02-18): 30+ 命令添加中英双语说明和用法示例，修复 ruff 报错。
- **EventIndex Hotfix** (2026-02-18): `_build_query_sql` 安全处理 Enum/String 双类型。
- **RFC-001 扩展** (2026-02-18): 增加两阶段 `dimc down` 设计 (§6-§7)，解决导出文件无时间戳问题。
- **RFC-003 新建** (2026-02-18): Master-Slave 多 Agent 架构方案。
- **模型用完即释放** (2026-02-18): 实现 RT-000 §4.2 设计，峰值从 ~5.87 GB 降至 ~3.6 GB。
- **ChromaDB 迁移** (2026-02-17): VectorStore 完全迁移到 SQLite-vec。
- **Session Log Aggregation** (2026-02-18): 修复 `dimc down`，Job Scanner + Auto-Detect。
- **Deprecation** (2026-02-18): 废弃 `GraphStore.save()`，彻底移除 `chromadb`。
