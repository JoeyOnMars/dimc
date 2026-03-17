# `dimc down` 架构合规性审计报告 (V2)

**状态**: 历史分析快照；仅反映当时 `dimc down` 路径的合规性判断，不直接代表当前实现。

> **文档ID**: AUDIT-005-V2
> **日期**: 2026-02-19
> **审计对象**: `src/dimcause/cli.py` → `down()` 函数 (L412-L780, ~370行)
> **审计基准**:
> - `docs/PROJECT_ARCHITECTURE.md` — 六层 DIKW 架构
> - `.agent/rules/SYSTEM_CONTEXT.md` — 数据层级 (L0/L0.5/L1/L2)
> - `docs/V6.0/DEV_ONTOLOGY.md` — 本体定义
> **状态**: 🔴 严重不合规 (Critical Non-Compliance)

---

## 零、规则确认报告

| 文件 | 状态 | 关键约束摘要 |
|:---|:---|:---|
| `chinese.md` | ✅ 已读取 | 全部中文输出 |
| `Code-Audit.md` | ✅ 已读取 | 禁止擅自修改核心逻辑；审计格式输出 |
| `contracts.md` | ✅ 已读取 | 函数契约以 `api_contracts.yaml` 为准 |
| `dimcause-ai-system.md` | ✅ 已读取 | 核心链路改动需标注；默认审计员角色 |
| `DIMCAUSE.SecurityBaseline.ABC.md` | ✅ 已读取 | WAL/Markdown SoT/EventIndex 扫描范围不可缩减 |
| `Environment-Setup.md` | ✅ 已读取 | `.venv` 虚拟环境铁律 |
| `Honesty-And-Structure.md` | ✅ 已读取 | 诚实性/结构化输出/任务完成诚实度约束 |
| `Agent-Planning-Standard.md` | ✅ 已读取 | 设计对齐/代码现实检验/任务原子性 |
| `SYSTEM_CONTEXT.md` | ✅ 已读取 | **数据层级 L0/L0.5/L1/L2 定义；源优先级裁决** |
| `MODEL_SELECTION_RULES.md` | ✅ 已读取 | 模型选择策略 |
| `ruff-check.md` | ✅ 已读取 | 使用 `scripts/check.zsh`，不单独运行 `ruff` |

### 本次任务安全检查

- **涉及 SEC 条目**: SEC-1.x (WAL 与 Markdown SoT)、Behavior Consistency Check
- **允许修改范围**: `cli.py` (L5)、`audit/context_injector.py`、`core/workflow.py`、`core/session_end.py` (新建)
- **禁止修改范围**: `core/ontology.yaml`、`core/ontology.py`、WAL 链路、`docs/PROJECT_ARCHITECTURE.md`、`docs/V6.0/DEV_ONTOLOGY.md`

---

## 一、背景：设计文档早已定义好的数据层级

### 1.1 `SYSTEM_CONTEXT.md` 定义的数据层级 (摘自 `.agent/rules/SYSTEM_CONTEXT.md:90-134`)

DIMCAUSE 的设计文档**已经明确定义**了四级数据层次：

| 层级 | 名称 | 数据源 | 地位 |
|:---|:---|:---|:---|
| **L0** | External Raw Input | `docs/logs/raw/AG_Exports/` (项目内归档) + `~/Documents/AG_Exports/` (外部备份) | **绝对原始数据** |
| **L0.5** | Transient Session State | `~/.gemini/antigravity/brain/<session-id>/` 下的 `task.md`, `walkthrough.md`, `implementation_plan.md` | **Working Memory**，会话结束后由 `dimc down` 固化 |
| **L1** | System Raw Data | Git (.git) + Structured Ledger (`docs/logs/YYYY/MM-DD/**/*.md`) + Raw Stream (`docs/logs/raw/`) + Rules (`.agent/rules/`) + Ontology (`ontology.yaml`) | **真正的 Source of Truth**，可重建一切 |
| **L2** | Derived Data | `EventIndex` (SQLite) + `GraphStore` (SQLite+NetworkX) + `VectorStore` (sqlite-vec) | **衍生缓存**，与 L1 不一致时以 L1 为准 |

### 1.2 设计文档对 `dimc down` 的预期

`SYSTEM_CONTEXT.md:103` 明确写道：

> "在 `dimc down` 时，其 [L0.5] 关键信息被**提取并固化**到 Level 1 Ledger 中。"

这意味着 `dimc down` 的核心职责是：**L0 + L0.5 → L1 的数据固化管道**。

### 1.3 六层 DIKW 架构 (摘自 `PROJECT_ARCHITECTURE.md`)

```
L5: Presentation (CLI/TUI) — 纯 UI，不包含核心业务逻辑
L4: Wisdom (Reasoning/Audit) — 推理引擎、公理验证、审计
L3: Knowledge (Ontology/Schema) — 本体定义、数据契约
L2: Information (Index/Graph) — EventIndex, GraphStore, VectorStore, TimelineService
L1: Data (Extractors/Sources) — 数据捕获、清洗、提取、标准化
L0: Infrastructure (Utils/Daemon) — 通用工具、配置、编排
```

**架构原则**: "分层隔离：上层依赖下层，下层不可依赖上层。L5 不包含核心业务逻辑。"

---

## 二、审计发现：全系统原始数据来源清单

### 2.1 L0 层：数据入口 — 单源硬绑定，不可接受

> [!CAUTION]
> L0 层缺乏多数据源配置能力。当前只硬绑定 AG_Exports 一个来源，不支持 Cursor/Windsurf/手写笔记等其他来源。这与"Local-first"的产品定位严重矛盾。

**L0 (入口) → L1 (落地) 的正确模型**：

```
L0 = 数据入口管道（可配置多源） → "从哪里读"
L1 = 落地存储 (Source of Truth)  → "存到哪里" → docs/logs/raw/
L2 = 衍生索引 (Cache)           → "加速查询" → EventIndex, VectorStore
```

**当前 L0 数据源清单**：

| 数据源 | 当前路径 | L1 落地位置 | `dimc down` 是否处理 |
|:---|:---|:---|:---|
| **AG_Exports (IDE 导出)** | `Config.export_dir` (默认 `~/Documents/AG_Exports`) | `docs/logs/raw/AG_Exports/` (30个文件) | ❌ ContextInjector 不读 |
| **Gemini 对话** | `docs/logs/raw/Gemini/` (已在 L1) | 同左 | ❌ 完全未处理 |
| **Perplexity 研究** | `docs/logs/raw/Perplexity/` (已在 L1) | 同左 | ❌ 完全未处理 |
| **Cursor/Windsurf 导出** | 不存在 | 不存在 | ❌ 无管道 |
| **手写笔记/外部文档** | `dimc data-import <path>` | ⚠️ 直接写 VectorStore (L2)，**跳过 L1** | ❌ 与 `dimc down` 无关 |

**L0 层问题清单**：

| 问题 | 严重性 | 说明 |
|:---|:---|:---|
| **只有一个 `export_dir` 配置** | 🔴 不可接受 | 不支持多源配置，用 Cursor 的用户完全无法使用 |
| **`data-import` 跳过 L1** | 🔴 违反架构 | 导入数据直接写 VectorStore (L2)，不落地到 `docs/logs/raw/` (L1)，无法重建 |
| **无数据源管理 UI** | 🟡 功能缺失 | 无法通过 CLI/TUI 查看、添加、管理数据源目录 |
| **`dimc down` 不读 L1 raw 数据** | 🔴 核心缺陷 | `docs/logs/raw/` 下 40+ 个文件从未被 `end.md` 消费 |

### 2.2 L0.5 层：Brain Session State — 严重不完整

Active Session Brain 目录 (`~/.gemini/antigravity/brain/<session-id>/`) 的完整内容：

| 文件/目录 | 类型 | `dimc down` 是否处理 | 说明 |
|:---|:---|:---|:---|
| `task.md` | 工件 | ✅ ContextInjector 读取 | 提取 `[x]` 和 `[ ]` |
| `implementation_plan.md` | 工件 | ✅ ContextInjector 读取 | 提取 Legacy Issues 和 Next Steps |
| `walkthrough.md` | 工件 | ✅ ContextInjector 读取 | 提取验证摘要 |
| `task.md.resolved.*` (15个版本) | 版本历史 | ❌ | task.md 的每次修改快照 |
| `implementation_plan.md.resolved.*` (9个版本) | 版本历史 | ❌ | 实施计划的演变历史 |
| `walkthrough.md.resolved.*` (11个版本) | 版本历史 | ❌ | 验证记录的演变历史 |
| `*.metadata.json` (3个) | 元数据 | ❌ | 工件的创建时间、类型等 |
| `media__*.png` (6个截图) | 截图 | ❌ | 会话中生成或上传的图片 |
| `.system_generated/steps/` | 执行步骤输出 | ❌ | Agent 执行步骤的输出记录 |
| `.system_generated/click_feedback/` | 用户反馈 | ❌ | 用户对 Agent 输出的点击反馈 |

**ContextInjector 只读了 50+ 文件中的 3 个**。注意：真正的 Raw Conversation (原始对话) 不在 Brain 目录中，而在 **`docs/logs/raw/AG_Exports/`** (L0)——那里有 30 个完整的对话导出文件，**完全未被读取**。

### 2.3 L1 层：System Raw Data — 部分使用

| 数据源 | 路径 | `dimc down` 是否处理 |
|:---|:---|:---|
| **Git History** | `.git/` | ⚠️ 旧系统用 `subprocess.run("git diff")` 在 L5 直接调用 |
| **Structured Ledger** | `docs/logs/YYYY/MM-DD/**/*.md` | ✅ `create_daily_log()` 写入 Ledger |
| **Job Logs** | `docs/logs/YYYY/MM-DD/jobs/*/job-end.md` | ⚠️ 旧系统 `_scan_job_summaries()` 有处理，但被新系统绕开 |
| **STATUS.md** | `docs/STATUS.md` | ✅ ContextInjector 读取 |
| **Rules** | `.agent/rules/` | ❌ 未触及 (不需要) |
| **Ontology** | `core/ontology.yaml` | ❌ 提取的事件未经本体校验 |

### 2.4 L2 层：Derived Data — 几乎未使用

| 组件 | 本应扮演的角色 | `dimc down` 是否调用 |
|:---|:---|:---|
| `EventIndex` | 索引提取的事件 | ⚠️ 直接在 L5 实例化并调用 `add()` |
| `GraphStore` | 存储事件间因果关系 | ❌ 完全未调用 |
| `VectorStore` | 语义 embedding | ❌ 完全未调用 |
| `TimelineService` | 构建时间线 (替代手写 Smart Scan) | ❌ 完全未调用 |
| `SearchEngine` | 检索相关历史 | ❌ 完全未调用 |

---

## 三、`dimc down` 的实现问题详细分析

### 3.1 上帝函数 (God Function)

`down()` 函数 ~370 行，全部在 `cli.py` (L5)，承担了应属 L0-L4 的全部职责：

| 代码段 | 行范围 | 功能 | 应属层级 | 实际层级 |
|:---|:---|:---|:---|:---|
| AI Log 检测 | L444-L463 | 扫描 AG_Exports 目录 | L1 | ❌ L5 |
| 创建 end.md | L467-L472 | 生成日志模板 | L0 | ✅ L0 (调用 `workflow.py`) |
| 上下文注入 | L475-L483 | ContextInjector | L1+L2 | ❌ L5 调用 (ContextInjector 自身放在 L4) |
| LLM 事件提取 | L486-L550 | EventExtractor 实例化+调用 | L1 | ❌ L5 直接实例化 |
| Smart Scan | L555-L612 | 时间窗口过滤日志 | L2 (TimelineService) | ❌ L5 手写 |
| Brain Context | L614-L710 | 读 Brain Artifacts + 正则 | L1 | ❌ L5 手写 (~100行) |
| Job 聚合 | L691-L697 | 读 job-end.md | L2 | ❌ L5 |
| Git 提取 | L717-L766 | subprocess 调用 git diff | L0+L1 | ❌ L5 |
| 索引更新 | L778-L780 | update_index() | L2 | ⚠️ L5 直接调用 |

**合规率**: 1/9 步骤合规 (**11%**)

### 3.2 双重注入系统并存

| 系统 | 位置 | 数据源 | 输出 |
|:---|:---|:---|:---|
| **旧系统** | `cli.py:614-710` | Brain dir + Job Logs + STATUS.md | `## 🧠 Brain Context (Auto-Injected)` |
| **新系统** | `context_injector.py` | Brain dir + STATUS.md + AG_Exports 标题 | 按章节替换 (`## 📅`, `## 📋`, `## 🧱`, `## 🚀`) |

两者**同时向 `end.md` 写入**，数据源部分重叠。新系统丢失了旧系统的 Job 聚合能力。

### 3.3 ContextInjector 的定位问题

| 问题 | 说明 |
|:---|:---|
| **放错层级** | 在 `audit/` (L4) 目录，但做的是 L1 (提取) + L2 (聚合) 的工作 |
| **硬编码路径** | Brain 目录发现使用硬编码 `~/.gemini/antigravity/brain/`，应改为 `Config` 配置项 |
| **数据采集不完整** | 50+ 文件中只读 3 个，忽略 `.system_generated/logs/`、`.resolved` 版本历史、媒体文件 |
| **不感知 Job 层** | 完全不知道 `jobs/*/job-end.md` 的存在 |
| **不读 AG_Exports 原文** | 只提取标题，不提取对话内容 |

### 3.4 MAL 三层记录体系的退化

| MAL 特性 | DIMC 代码状态 | 断连程度 |
|:---|:---|:---|
| L1 Raw 是数据源头 | 代码存在 (`raw/AG_Exports/` 有数据)，但无消费者 | 🔴 完全断连 |
| L2 Job 提供上下文隔离 | 代码完整 (`workflow.py` 有 Job 模板/工作流)，ContextInjector 绕开 | 🟡 部分断连 |
| L3 Daily 聚合所有 Job | 旧系统有 `_scan_job_summaries()`，新系统覆盖 | 🟡 部分断连 |
| EventExtractor 从 Raw 提取 | 退化为从已注入 `end.md` 再提取一次 | 🔴 设计意图完全丢失 |

---

## 四、根因分析

### 4.1 时间线

1. **MAL 时代**: 三层设计清晰 (Session → Job → Daily)
2. **DIMC 迁移**: 代码保留 Job 层 (`workflow.py`, `cli.py:job-start/job-end`)
3. **V6.0 架构升级**: `SYSTEM_CONTEXT.md` 定义了 L0/L0.5/L1/L2 数据层级
4. **V6.1 快速迭代**: Agent 被要求"注入上下文到 `end.md`"，从头写了 `ContextInjector`，**未读旧代码 `_scan_job_summaries()`**，**未读 `SYSTEM_CONTEXT.md` 的数据层级定义**
5. **结果**: 两套系统并存；新系统丢失 Job 聚合和 Raw Log 读取；设计文档与实现严重脱节

### 4.2 反模式清单

| 反模式 | 违反的规则 | 表现 |
|:---|:---|:---|
| **上帝函数** | `Agent-Planning-Standard.md` §4 任务原子性 | 370 行 `down()` 做了 9 件事 |
| **越级调用** | `PROJECT_ARCHITECTURE.md` 分层隔离原则 | L5 直接实例化 L1/L2 组件 |
| **Not Invented Here** | `Agent-Planning-Standard.md` §2 代码现实检验 | 新写 ContextInjector 而不是复用 `_scan_job_summaries()` |
| **无设计对齐** | `Agent-Planning-Standard.md` §1 设计对齐 | ContextInjector 未映射到 `SYSTEM_CONTEXT.md` 的数据层级 |
| **数据源遗漏** | `SYSTEM_CONTEXT.md` L0 定义 | AG_Exports 30 个原始文件未被消费 |

---

## 五、修正计划 (迭代方案)

### 目标架构

```
cli.py:down() (L5)          → 纯 UI (~50行)，输入/输出渲染
core/session_end.py (L0)    → 编排管道，调用以下服务
  ├── DataCollector (L1)    → 收集 active session 的全部数据 (L0 + L0.5)
  │     ├── Brain 工件读取  → task.md, walkthrough.md, impl_plan.md, *.metadata.json
  │     ├── AG_Exports 读取 → docs/logs/raw/AG_Exports/ 匹配当前会话的原始对话文件
  │     ├── Job Logs 读取   → docs/logs/YYYY/MM-DD/jobs/*/job-end.md
  │     └── Git History     → git log/diff since session start
  ├── ContextAggregator (L2)→ 聚合为 end.md 各章节
  │     ├── EventIndex.add()  → 索引
  │     ├── VectorStore.add() → embedding (与 dimc index 共享)
  │     └── 章节生成         → Achievements, Tasks, Jobs, Legacy, Next Steps
  └── OntologyValidator (L3) → 校验事件类型合法性 (可选, 未来)
```

### Iteration 1: 基础搬移 + L0 数据源补全

**目标**: 将 `down()` 拆分为 `SessionEndService`，同时补全 L0 数据源读取

| 交付物 | 说明 |
|:---|:---|
| `core/session_end.py` [NEW] | `SessionEndService` 类，编排完整管道 |
| `core/data_collector.py` [NEW] | `DataCollector` 类 (L1)，读取 Brain 全量 + AG_Exports + Job Logs + Git |
| `cli.py:down()` [MODIFY] | 缩减为 ~50 行薄包装器 |
| `core/config.py` [MODIFY] | 新增 `brain_dir` 配置项 (替代硬编码) |

**数据源补全清单**:

| 数据源 | 当前状态 | Iter 1 目标 |
|:---|:---|:---|
| Brain `task.md` | ✅ 已读 | 保持 |
| Brain `implementation_plan.md` | ✅ 已读 | 保持 |
| Brain `walkthrough.md` | ✅ 已读 | 保持 |
| Brain `*.metadata.json` | ❌ 未读 | ✅ **新增读取** (会话时间范围) |
| `docs/logs/raw/AG_Exports/*.md` (匹配当前会话) | ❌ 未读 | ✅ **新增读取** |
| `docs/logs/YYYY/MM-DD/jobs/*/job-end.md` | ⚠️ 旧系统读 | ✅ **纳入 DataCollector** |
| Git diff (since session start) | ⚠️ L5 手写 | ✅ **纳入 DataCollector** |

### Iteration 2: 统一注入系统 + Job 章节

**目标**: 消灭双重注入，恢复 Job 层

| 交付物 | 说明 |
|:---|:---|
| `audit/context_injector.py` [MODIFY] | 吸收旧系统功能，新增 `## 🧩 今日 Jobs` 章节 |
| `cli.py:614-710` [DELETE] | 删除旧注入系统 |
| `core/workflow.py` DAILY_END_TEMPLATE [MODIFY] | 新增 `## 🧩 今日 Jobs` 占位符 |

### Iteration 3: L2 共享基础设施

**目标**: `dimc down` 和 `dimc index` 共享 L1/L2 服务

| 交付物 | 说明 |
|:---|:---|
| DataCollector 输出经 `EventIndex.add()` 索引 | 与 `dimc index` 共享 |
| DataCollector 输出经 `VectorStore.add()` embedding | 与 `dimc index` 共享 |
| `dimc index --rebuild` 可从 L1 重建 L2 | 保持数据一致性 |

### Iteration 4: L3/L4 接入 (可推迟)

| 交付物 | 说明 |
|:---|:---|
| EventExtractor 输出经 `OntologyEngine.validate()` 校验 | L3 |
| 新事件通过 `HybridEngine` 自动建立因果链接 | L4 |
| `AuditEngine` 对 `end.md` 做质量审计 | L4 |

---

## 六、审计依据

| 文件 | 用途 |
|:---|:---|
| `.agent/rules/SYSTEM_CONTEXT.md:90-134` | **数据层级 L0/L0.5/L1/L2 定义** (本次审计的核心基准) |
| `docs/PROJECT_ARCHITECTURE.md` | 六层架构定义 |
| `docs/V6.0/DEV_ONTOLOGY.md` | 本体定义 |
| `.agent/rules/Agent-Planning-Standard.md` | 设计对齐/代码现实检验要求 |
| `.agent/rules/DIMCAUSE.SecurityBaseline.ABC.md` | Behavior Consistency Check 要求 |
| `src/dimcause/cli.py:412-780` | `down()` 函数实现 |
| `src/dimcause/cli.py:2857-2902` | `_scan_job_summaries()` |
| `src/dimcause/audit/context_injector.py` | 新注入系统 |
| `src/dimcause/core/workflow.py` | Job 层模板/工作流 (被绕开) |
| `docs/logs/raw/AG_Exports/` | 30 个原始对话文件 (未被消费) |
| `~/.gemini/antigravity/brain/<session>/` | Brain 目录完整内容 (50+ 文件，只读了 3 个) |

---

**审计结论**: `dimc down` 存在系统性的架构违规和数据源遗漏。不仅违反了六层 DIKW 架构的分层隔离原则，更严重的是**违反了项目自身 `SYSTEM_CONTEXT.md` 早已定义好的数据层级设计**。L0 (AG_Exports 原始对话) 和 L0.5 (Brain 会话状态) 的大部分数据从未被采集和固化到 L1 (Ledger)，导致 `end.md` 只反映了冰山一角。
