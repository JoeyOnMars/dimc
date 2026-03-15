# 项目愿景: DIMCAUSE

> **"代码是结果 (What)，DIMCAUSE 记录原因 (Why)。"**

## 1. 核心痛点：上下文失忆 (Context Amnesia)
在现代软件开发中，我们擅长追踪 **代码变更** (Git) 和 **任务状态** (Jira/Linear)。但我们要么丢失了，要么从未记录最宝贵的资产：**工程上下文 (Engineering Context)**。

- *为什么我们当时选择了 SQLite 而不是 Postgres？*
- *上周我们尝试并放弃的那个替代架构是什么？*
- *谁批准了这个 API 破坏性变更，权衡是什么？*

这种 "上下文失忆" 导致了重复的错误、团队知识流失以及新成员上手困难。

## 2. 我们的方案：工程师的知识操作系统 (Knowledge OS)

Dimcause 不是现有笔记工具的竞品，而是它们的 **超集 (Superset)**。

**公式**: `Dimcause = Context (知识管理) + Git (版本控制) + Audit (因果逻辑)`

我们采用 "Include + Extend" 战略：
1.  **Include (包含)**: 像传统工具一样轻松摄入文档、聊天记录和想法 (Smart Ingest)。
2.  **Extend (扩展)**: 独有的 **代码理解** 和 **因果审计** 能力。

### "事件优先" 哲学 (Event-First)
不同于传统工具索引原始文本或 Git 提交，DIMCAUSE 将 **工程事件 (Engineering Events)** 视为历史的原子单位。

| 维度 | Git | 传统笔记工具 | **DIMCAUSE (Superset)** |
|-----------|-----|------------------|-----|
| **单位** | 代码行 | 页面/章节 | **事件** (决策 + 代码 + 语境) |
| **关注点** | 最终实现 | 静态知识 | **演进与因果** |
| **查询** | "谁改了这一行？" | "功能 X 是什么？" | **"为什么功能 X 是这样设计的？"** |

## 3. 六层架构 (The 6-Layer Architecture)

DIMCAUSE V6.2 采用扩展的 DIKW 模型，从基础设施到展现层，构建完整的六层架构：

0.  **Layer 0：基础设施 (Infrastructure)**
    -   组件: `DaemonManager`, `Orchestrator`, 数据库迁移, 通用工具。
    -   角色: 提供系统运行底座，不包含业务逻辑。

1.  **Layer 1：数据接入 (Data Ingestion)**
    -   来源: 人类输入 (`dimc log`)，AI 对话归档 (`ExportWatcher`)，Git 历史 (`GitImporter`)，文件树与状态变更 (`StateWatcher`)。
    -   引擎: `EventExtractor` (DeepSeek / LLM) — 将非结构化文本解析为结构化事件。
    -   角色: 原始数据捕获、清洗与标准化。

2.  **Layer 2：信息索引 (Information & Indexing)**
    -   存储: SQLite (`EventIndex`) + 向量库 (sqlite-vec) + 图谱 (`GraphStore`)。
    -   角色: 为 CLI 命令 (`dimc timeline`, `dimc search`) 提供毫秒级检索。

3.  **Layer 3：知识本体 (Knowledge & Ontology)**
    -   定义: `ontology.yaml` — 6 大类、7 种关系、3 条公理。
    -   角色: 赋予数据语义约束，确保因果链的合法性。

4.  **Layer 4：智慧推理 (Wisdom & Reasoning)**
    -   引擎: `HybridEngine` — 三阶段推理 (时序启发 → 语义关联 → LLM 深度推理)。
    -   组件: `AxiomValidator` (公理验证), `AuditEngine` (自动审计), `DecisionAnalyzer` (`dimc why` 核心)。
    -   角色: 自动化因果推理与决策追溯。

5.  **Layer 5：展现交互 (Presentation)**
    -   CLI: `dimc` 命令行主入口 (Typer)。
    -   TUI: `Textual` 终端交互界面，图谱浏览器。
    -   可视化: 图谱渲染 (ASCII/Mermaid)，数据报表。
    -   角色: 用户交互接口，不包含核心业务逻辑。

## 4. 核心护城河 (Key Differentiators)

### A. 混合时间轴 (The Hybrid Timeline)

DIMCAUSE 融合了两条此前平行的平行线：
- **Git 历史**: 代码发生了什么。
- **决策历史**: 工程师脑子里想了什么。
`dimc timeline` 将两者交织展示，还原从想法到提交的完整生命周期。

### B. 零摩擦自动化 (Zero-Friction Automation)
我们认为文档应该是工作的副作用，而不是额外的苦差事。
- `dimc up` / `dimc down`: 会话级日志自动管理（上下文恢复 + 日终总结）。
- `dimc capture export`: 自动摄取 AI 对话记录（支持多工具导出目录）。
- `dimc ingest`: 自动从 Git Diff 和代码变更中提取事件。

### C. 本地优先与隐私 (Local-First & Privacy-Centric)

你的工程思维是你的核心资产。DIMCAUSE 本地运行，本地存储 (Markdown + SQLite)，并让你完全掌控哪些数据会被发送给 LLM 进行提取。

## 5. 前方之路
- **V6.0** *(当前)*: 本体引擎 + 因果推理 + 多 Agent 并发支持。
- **V6.x**: 个人工程记忆完善（Session 注册表 + Brain 数据融合 + 自动 end.md 生成）。
- **V7.0** *(Next)*: **Agent OS (File-System Memory)** — 将内存、工具、知识统一为文件系统，解决 Context 传递问题 (详见 [RFC-001](design/RFC_001_FILESYSTEM_MEMORY.md))。
- **V8.x**: 自主 Agent 治理 (让 Agent "记住" 此前的架构约束)。
