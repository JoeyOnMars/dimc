# Task 006 契约: 项目架构文档与代码深度对齐重构 (Alignment Polish)

**目标**: 解决 V6.2 架构声明与现有代码物理结构脱节的“虚假对齐”问题。
**执行方式**: 为降低大规模移动文件带来的依赖链断裂风险，我们将该任务原子化解耦为三个独立的子任务。建议由专家 Agent（如 M 专家）逐一在一个个独立分支上完成，逐步并入 `main`。

---

## Task 006-01: 驱逐幽灵与冗余 (Ghost & Duplication Eviction)

**分支名建议**: `feat/task-006-01-ghost-eviction`

**行动项**:
1. **解决双轨并行倒挂**: 
   - 物理删除 `src/dimcause/core/git_importer.py`。
   - 所有引用（如 `cli.py` 或其他地方）必须统一指向合法目录 `src/dimcause/importers/git_importer.py`。
2. **收纳孤立模块**:
   - 将 `src/dimcause/capture/export_watcher.py` 移动到 `src/dimcause/watchers/export_watcher.py`。
   - 彻底删除 `src/dimcause/capture/` 文件夹。
3. **补充遗漏声明**:
   - 对 `src/dimcause/analyzers/`（如 `arch_validator.py`, `circular_dep.py`）在 `PROJECT_ARCHITECTURE.md` 的 `L4 Wisdom` 层进项补充登记，说明其用途。
   - 在 `PROJECT_ARCHITECTURE.md` 的 `L4/L5` 层接口之间，明确登记 `protocols/mcp_server.py`。
4. **验证条件**:
   - `pytest tests/` 必须全量通过。
   - 确认无 Import 报错。

---

## Task 006-02: 拆解上帝包 `core/` (Dismantling the God Package)

**分支名建议**: `feat/task-006-02-dismantle-core`

**行动项**:
`core/` 目录违规跨越了所有层级，需按如下规则遣散包内模块：
1. **下沉至 L0 (基础设施)**
   - 移动 `core/config.py` -> `utils/config.py`
   - 移动 `core/state.py` -> `utils/state.py`
2. **上浮至 L1 (数据接入)**
   - 移动 `core/chunking.py` -> `extractors/chunking.py` (或 `utils/`)
   - 移动 `core/data_collector.py` -> `extractors/data_collector.py`
3. **上浮至 L4 (业务流与推理)**
   - 移动 `core/causal.py`, `core/correlator.py` -> `reasoning/` （或直接废弃）。
   - 创建 `src/dimcause/services/` 顶级模块（L4 与 L5 之间的编排层）。
   - 移动 `core/session_end.py` -> `services/session_end.py`。
   - 移动 `core/pipeline.py` -> `services/pipeline.py`。
   - 移动 `core/workflow.py` -> `services/workflow.py`。
4. **验证条件**:
   - 大量的 import 语句将被破坏，必须使用全局搜索与替换极其耐心地修补！
   - 特别注意测试文件 `tests/` 下对 `dimcause.core.*` 的海量引用。
   - `pytest tests/` 必须全量通过！

---

## Task 006-03: 文档全量同步与回归 (Doc Sync & Full Regression)

**分支名建议**: `feat/task-006-03-doc-sync`

**行动项**:
1. 修改 `docs/PROJECT_ARCHITECTURE.md`，反映 006-01 与 006-02 所做的改动：
   - 登记新增的 `services/` 目录。
   - 补充近期（Task 003~005）新增的组件：将 `storage/chunk_store.py` 登记入 `L2 Information`，将 `extractors/extraction_pipeline.py` 登记入 `L1 Data Ingestion`。
2. 删除 `scripts/` 下的无关代码或声明脚本作用，并确保它们在项目发行时不被误用。
3. 提取最新的 `tree src/dimcause`。
4. **验证条件**:
   - 出具最终的对照表，确保证明表中不再存在任何 `[UNMAPPED_VIOLATION]`。

## Task 006-04: 接续 V6.3 业务主线 (Resume Business)

**前提**: 只有在 006-01~03 完全被合入并平息了所有引用报错之后，才能检出本分支。
**分支名建议**: `feat/task-006-04-resume-business`

**行动项**:
1. **替换旧版采集逻辑**: 
   - 深入 `dimc down` (或对应的 `SessionEndService`)。
   - 彻底废除、删掉原先全量长文本日志的收集和旧的 `run_smart_scan()` 流程。
   - 完整切入 Task 005 中写好的 `ExtractionPipeline` 新流水线。
2. **消灭测试红线**:
   - 运行项目全量的 `pytest tests/`。
   - 针对因为 V6.3 新管道引入而导致失败的测试用例（如 indexer, trace, e2e），进行逐一修复，使其达到 100% Pass。
3. **补充实战演习**:
   - 编写或补充 `test_forced_corruption_recovery`（流式降级断网演习）。
   - 验证 V6.3 管道在无 LLM Key、强行断网或 JSONL 损坏时的本地 L1 提取兜底能力。
4. **验证条件**:
   - `pytest tests/` 100% 通过（不允许任何失败）。
   - 代码中不存在对旧的 `run_smart_scan` 及其引用的遗留。

## Task 006-05: 技能沉淀与提取 (Skill Extraction)

**分支名建议**: `feat/task-006-05-skills-extraction`

**行动项**:
1. **审查当前所有的 `.agent/workflows/`**:
   - 检查已有的工作流定义（如 `job-end.md`, `dimc down.md` 等）的可用性和陈旧度。
   - 移除因架构变迁而完全失效的过时工作流。
2. **提炼与固化 `Claude Skills`**:
   - 提取跨周期的协同、架构审计、日志结案等成熟工作流，将其结构化并保存到 `.agent/skills/` 目录下（如果是为 Claude 设计的全局技能）。
   - 让有用的通用规范形成长期可以被各个 Agent 随时引用的 `[SKILL]`。
3. **验证条件**:
   - `.agent/skills/` 中存放着高度精炼的 Markdown 技能定义文档。
   - 更新 `task.md` 表示整个 Task 006 彻底收官。
