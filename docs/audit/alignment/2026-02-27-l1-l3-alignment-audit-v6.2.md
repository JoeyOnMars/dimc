# L1-L3 架构与规范一致性审计报告

**状态**: 历史对齐审计；部分结论已被后续代码和文档吸收；引用前必须复核 live 代码。

**出具时间**: 2026-02-27
**审计依据**: 
- `.agent/rules/Honesty-And-Structure.md` （基于文件与代码的诚实声明）
- `.agent/rules/Code-Audit.md` （零容忍虚假对齐）
- `.agent/rules/Agent-Behavior-And-Professionalism.md` （摒弃预设认同，务实至上）

以下审计结果均基于对 `src/dimcause` 的物理 `grep_search` 与文件节点探测。

### 已知事实

1. `api_contracts.yaml` 与核心逻辑的对齐: `link_causal` 实际定义在 `src/dimcause/reasoning/causal_engine.py` 第 81 行；`add_structural_relation` 实际定义在 `src/dimcause/storage/graph_store.py` 第 299 行。与契约及 `DEV_ONTOLOGY.md` 的时空/结构隔离规范一致。[src/dimcause/reasoning/causal_engine.py], [src/dimcause/storage/graph_store.py]
2. `STORAGE_ARCHITECTURE.md` 的真实地址: 代码 `src/dimcause/utils/wal.py` 第 46 行定义 WAL 路径为 `~/.dimcause/wal.log`。此前文档中登记为 `~/.mal/wal.log`。该差异已在本轮审计中修正。[src/dimcause/utils/wal.py]
3. 原 `DIMC_DOWN_FLOW.md` 类路径指向: 文档原声称 `SessionEndService` 在 `core/` 目录，实际基于 grep (Step Id 2340) 在 `src/dimcause/services/session_end.py`。`DataCollector` 实际在 `src/dimcause/extractors/data_collector.py`。相关文档错位已修正，原流程说明文档已从 live 当前面移除。[src/dimcause/services/session_end.py], [src/dimcause/extractors/data_collector.py]
4. `IDE_INTEGRATION.md` 代码落地情况: 文档展示的 `WatchersConfig` 模型与 `src/dimcause/watchers/detector.py` 经全库 `grep_search` (Step Id: 2293, 2294) 返回结果为 0。文档存在超前于代码库的未落地设计声明。[grep_search src/]
5. `USER_GUIDE.md` 操作命令: 指南中介绍的 `dimc data-import` 工具链在 `src/dimcause/cli.py` 中确有实际挂载点。[src/dimcause/cli.py]
6. `GUIDE.md` 与 `USER_GUIDE.md` 命令交叉校验: 当时审计确认 `GUIDE.md` 内存在大量过期 V5.x 命令（如 `daily-start`、`daily-end`）；后续清理已保留并精修 `USER_GUIDE.md`，同时将 `GUIDE.md` 移出当前共享文档面。
7. `STORAGE_ARCHITECTURE.md` 的废弃目录结构: 依据对 `src/dimcause/utils/state.py` 的研读，系统通过扫描 `docs/logs/` 中的 `XX-start.md` 和 `XX-end.md` 动态推断活跃会话。文档中曾声明的 `~/.dimcause/sessions/active.json` 与 `history/git_commits.jsonl` 完全属虚假或被废弃的设计，已从架构树中摘除。[src/dimcause/utils/state.py]

### 推测与假设

1. `[推测]` `IDE_INTEGRATION.md` 中出现的 `WatchersConfig` 等类名，旨在勾勒 V6.x 远期多 IDE 无缝监听的设计方案，而非现有 API。原因：代码库确实不存在这些文件，且该文档发布早于多 Agent 开发期的完全重构。
2. `[推测]` `events_cache` 表结构的缓存方案尚未实装。原因：在 `src/dimcause/` 对 `events_cache` 搜索结果为空。这一状态匹配了 `STORAGE_ARCHITECTURE.md` 中标注"（未实现）"的旁注。

### 结论与建议

1. L1 (宏观本体/存储/契约) 与 L3 (进度与测试) 目前具有较高的物理保真度。依据：事实 #1, 事实 #2, 事实 #5。
2. L2 (策略文档如工作流与集成指南) 容易出现目录漂移与超前设计声明。已针对事实 #3 修正了相关目录路径，并针对事实 #4 在 `IDE_INTEGRATION.md` 中添加 `[WARNING]` 将相关伪代码标记为 WIP 设计，阻断后续 Agent 误用 API。依据：事实 #3, 事实 #4, 推测 #1。
3. 建议：后续 Agent 在依据 L2/L3 文档进行拓展前，必须主动查验引用类/模块的真实物理挂载点，不得跨过 `list_dir` 和 `grep_search` 做设计盲从。依据：事实 #3，事实 #4。
