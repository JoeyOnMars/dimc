# DIMCAUSE V6.2 架构与代码深度对齐证明 (Alignment Proof)

> **审计日期**: 2026-02-24  
> **审查对象**: `docs/PROJECT_ARCHITECTURE.md` (v6.2) 与 `src/dimcause/` (124 物理文件)  
> **审计级别**: 零容忍纪律 (Zero Tolerance - Honest & Structure)  
> **结论**: **[FATAL] 存在大规模架构漂移与结构坍塌。当前属于“虚假对齐”状态。**

---

## 摘要 (Executive Summary)

依据项目红线纪律，我通过对比物理文件的存在性与 `PROJECT_ARCHITECTURE.md` 的声明，发现了 **36 个文件 (约占总数 29%)** 在架构文档中查无此项、位置倒挂，或严重违反层级设计（Layering）。特别是作为基石的 `core/` 目录已经全面坍塌成为“上帝包”（God Package），包含了从 L0 到 L5 的所有逻辑越权。

---

## 1. 结构与声明对照表 (Alignment Mapping Table)

以下为 `tree src/dimcause` 各目录与架构层级的逐一比对，任何未在架构设计中标注、或功能越权的将被标记为 `[UNMAPPED_VIOLATION]`。

| 包/目录 (物理路径) | 架构声明归属 | 当前对齐状态审查详情 |
|:---|:---|:---|
| `daemon/` | L0 Infrastructure | ✅ 对齐。包含 `manager.py`, `entrypoint.py` |
| `migrations/` | L0 Infrastructure | ✅ 对齐。包含 `001_initial.py`, `002_add_chunk.py` |
| `scheduler/` | L0 Infrastructure | ✅ 对齐。包含 `orchestrator.py`, `runner.py`, `loop.py`, `lint.py` |
| `utils/` | L0 Infrastructure | ⚠️ 部分对齐。声明了 `Config` 在此包下，但实际代码为 `core/config.py`！🚨 **[UNMAPPED_VIOLATION: Position Mismatch]** |
| `extractors/` | L1 Data Ingestion | ⚠️ 部分对齐。增加了 V6.3 的 `session_extractor.py`, `extraction_pipeline.py` 等，但架构图未更新。🚨 **[UNMAPPED_VIOLATION: Missing Doc]** |
| `watchers/` | L1 Data Ingestion | ✅ 对齐。包含 `file_watcher.py` 等监控组件。 |
| `importers/` | L1 Data Ingestion | ✅ 对齐。`dir_importer.py`, `git_importer.py`。 |
| `capture/` | L1 Data Ingestion | 🚨 **[UNMAPPED_VIOLATION: Duplicated Scope]** 仅包含 `export_watcher.py`，它本质是一个 watcher，不该单独成包并游离在外。 |
| `storage/` | L2 Information | ⚠️ 部分对齐。增加了 `chunk_store.py` (V6.3)，且不在架构图内。🚨 **[UNMAPPED_VIOLATION: Missing Doc]** |
| `search/` | L2 Information | ✅ 对齐。包含 `engine.py`, `reranker.py`。 |
| `audit/` | L4 Wisdom | ✅ 对齐。包含 `engine.py`, `runner.py` 及 `checks/`。 |
| `brain/` | L4 Wisdom | ✅ 对齐。 |
| `reasoning/` | L4 Wisdom | ✅ 对齐。包含 `engine.py`, `semantic_linker.py` 等。 |
| `tui/`, `ui/`, `analytics/` | L5 Presentation | ✅ 对齐。 |
| `cli*.py` | L5 Presentation | ✅ 对齐。 |
| `scripts/` | (无) | 🚨 **[UNMAPPED_VIOLATION: Undeclared]** 包含 `verify_iter2.py`。脚本不应在 src 树中被打包。 |
| `analyzers/` | (无) | 🚨 **[UNMAPPED_VIOLATION: Phantom Package]** 包含 `arch_validator.py`, `circular_dep.py`。未在此前的六层模型中声明。 |
| `protocols/` | (无) | 🚨 **[UNMAPPED_VIOLATION: Phantom Package]** 包含 `mcp_server.py`。不仅未登记，还与架构完全解耦。 |
| **`core/`** | **L2, L3** | 🚨 **[FATAL_UNMAPPED_VIOLATION: God Package]** 详见下方专栏。 |

---

## 2. 核心违规深挖：上帝包 (The God Package `core/`)

架构明文规定 `core/` 的职责为：**L2 元数据索引 (`event_index.py`, `timeline.py`)** 与 **L3 本体论 (`ontology.py`, `schema.py`)**。

但现在，`core/` 中堆积了 **26 个** 杂乱无章的文件。以下模块是对分层原则的公然破坏：

### 越权至 L0 (基础设施) 的文件
- `core/config.py`: （本应在 `utils/`）
- `core/state.py`
- `core/protocols.py`

### 越权至 L1 (数据接入) 的文件
- `core/data_collector.py`
- `core/git_importer.py`: （与 `importers/git_importer.py` 出现了双重实现逻辑，灾难性重叠！）
- `core/chunking.py`: （应当属于 `extractors/` 的工具）

### 越权至 L4 (业务/推理流) 的文件
- `core/session_end.py`: （编排提取与提交流水线，应为 scheduler 或顶层领域逻辑）
- `core/workflow.py`
- `core/pipeline.py`
- `core/causal.py`
- `core/correlator.py`

---

## 3. 修复计划与 Blueprint (The Alignment Polish)

以上证据足以证明当前的架构设计文档是“粉饰太平”的（Fake Alignment），必须执行严厉的矫正重构（Alignment Polish）。

### Step 1: 驱逐幽灵与重叠 (Ghost & Duplication Eviction)
- `importers/` 统一接管所有导入。删除 `core/git_importer.py` 中重复的逻辑。
- 将 `capture/export_watcher.py` 降维并入 `watchers/export_watcher.py`，消除 `capture` 顶级冗余目录。
- 确认 `scripts/` 目录是否转移至根级仓库（而非 `src/dimcause/scripts`）。
- 给 `analyzers/` 与 `protocols/` (MCP Server) 在 `PROJECT_ARCHITECTURE.md` 进行 L4/L5 维度的收编声明。

### Step 2: 拆解上帝包 (Dismantling God Package)
- 把 `core/config.py` 和 `core/state.py` 移入 `utils/`（L0）。
- 把 `core/chunking.py`, `core/data_collector.py` 移入 `extractors/`（L1）。
- 把 `core/causal.py`, `core/correlator.py` 整合或迁移入 `reasoning/`（L4）。
- 把 `core/session_end.py`, `core/workflow.py`, `core/pipeline.py` 归流至顶层或独立的 `services/` 并更新架构图。

### Step 3: 更新架构图 (Doc Sync)
- 将 V6.3 中新写的 `storage/chunk_store.py` 和提取流水线完整补充进 `PROJECT_ARCHITECTURE.md` 的 L1/L2 说明中。
- 生成基于最新树状映射的对齐表。

只有在上述三步执行完毕且通过全量 `pytest` 与 `dimc audit` 之后，本项目才能被称为【真实对齐 V6.2 架构】。
