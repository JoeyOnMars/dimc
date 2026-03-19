# Workspace Profile v1

## 文档定位

1. 本文是当前 `dimc` 仓库的 **workspace profile** 提案文档；在五层结构中，它对应第三层“项目落地层”。
2. 本文不是产品架构重写稿，不是存储架构重写稿，不是对象模型重写稿，也不是证据政策重写稿。相关产品本体已经由正式架构文档与正式产品子规范约束。
3. 本文也不是当前仓库内部 workflow 规则汇编。分支纪律、`[PR_READY]`、预写入检查、`worktree`、格式化 gate、虚拟环境、审计模板等内容属于当前 repo 的治理与协作规则，不属于 workspace profile 本体。
4. 本文将当前 `dimc` 仓库视为一个**默认 kernel workspace profile 的实例**，而不是把整个仓库直接等同于产品本体。
5. 更准确地说：当前 `dimc` 共享仓库同时承载了五层结构中的前四层共享内容：
   - 产品定义层
   - 产品实现层
   - 项目落地层
   - 仓库治理层
6. 第五层“本地开发控制层”在本项目中同样存在，但它默认保留在本地开发目录，不属于本文的正式范围。

## 已知事实

1. 当前产品的一句话定义已经收口为：**DIMCAUSE 是一套面向本地异构材料的证据驱动因果调查系统。**
2. 当前已经落定的系统重构三项主线是：
   - `L0`: `task-centric scheduler -> run-centric runtime kernel`
   - `L1-L4`: `development-material bias -> domain-agnostic local material objectification plus evidence-backed causal reasoning`
   - `Storage`: `Evidence / Runtime / Knowledge / Derived Index` 四层职责分离
3. 正式产品架构文档与正式存储架构文档已经在 `main` 上重写完成，并继续作为受保护设计文档存在。
4. `docs/CORE_OBJECT_MODEL.md` 与 `docs/EVIDENCE_POLICY_AND_CAUSALITY_GRADES.md` 已经形成当前 workspace profile 的正式产品子规范约束；正式存储职责以 `docs/STORAGE_ARCHITECTURE.md` 为准。
5. 产品定义层、产品实现层、项目落地层、仓库治理层、本地开发控制层必须严格切开，不能互相代写。
6. 产品架构已经明确禁止从当前 repo 目录结构反推产品本体；当前目录结构最多只能说明一个具体 workspace profile 的当前实现现实。
7. 当前工作目录现实中同时存在以下几类区域：
   - `src/dimcause/` 及其子模块，承载产品内核实现的主要代码表面
   - `docs/logs/` 与仓库外原始导出材料目录这类本地材料与证据承载面（`docs/logs/` 默认不进入 git，不属于共享文档入口）
   - `docs/audit/` 这类共享审计工件承载面
   - `.agent/rules/`、`docs/coordination/`、本地开发控制层中的临时协作目录、`scripts/check.zsh`、`scripts/preflight_guard.py` 这类仓库治理与协作表面
8. 当前仓库中的 `docs/` 并不是单一职责目录。它同时包含产品正式设计文档、proposal、研究材料、日志材料、报告工件和协作模板，因此 `docs/` 本身不能直接等同于某一产品层。
9. 当前仓库中的 `tmp/` 也不是产品层专属目录。它同时包含讨论、协调、救援、测试沙箱等临时表面，因此 `tmp/` 本身不能被写成产品架构或 workspace profile 的稳定语义。

## 推测与假设

1. [推测] 当前仓库仍然保留着多轮演化留下的历史层次，因此一个物理路径往往同时带有“当前实现现实”“历史遗留结构”“临时协作表面”三种含义中的至少一种。
2. [推测] 当前 workspace profile 的重点，不应是把所有路径一一塞进某个产品层，而应先澄清“哪些当前路径体现了默认本地映射”，“哪些只是当前仓库治理或临时协作表面”。
3. [推测] 当前仓库中的本地材料组织、报告工件组织与索引/存储实现，仍带有明显的工程 dogfooding 痕迹；这些痕迹可以被解释为默认 profile 的当前选择，但不能上升为产品普遍要求。
4. [推测] 当前代码与正式新架构之间未必已经做到“一物理路径 = 一产品层”的完全整齐对齐，因此本文应解释当前映射关系，而不是假装当前实现已经物理完成了彻底分层。
5. [推测] 对未来 profile 而言，最可能变化的不是产品内核本体，而是材料根、证据工件布局、本地索引后端、运行态落点以及领域化材料类型。

## 结论与建议

### 1. 什么是 Workspace Profile

1. `workspace profile` 不是产品本体，而是**某个具体工作空间如何实例化产品内核**的映射说明。
2. 它回答的问题包括：
   - 当前工作空间把哪些本地材料当作默认输入面
   - 当前工作空间把证据、运行态、知识承载与派生索引映射到哪些本地实现表面
   - 当前工作空间把哪些区域视为产品内核实现、哪些视为 profile 选择、哪些明确不属于 profile
3. 它不回答的问题包括：
   - 产品是什么
   - 四层存储为什么这样定义
   - 哪些对象是一等对象
   - `E1-E4` 与 `C0-C4` 如何定义
   - 当前 repo 应该怎样协作、起分支、做预检查或生成交付门禁

### 2. 为什么当前 `dimc` 仓库被视为默认 Kernel Workspace Profile 的实例

1. 当前 `dimc` 仓库并不等于产品本体；它只是当前产品内核最主要的实现仓库，同时也是一个长期被用来承载本地材料、运行结果和协作痕迹的默认本地工作空间实例。
2. 因此，当前 `dimc` 仓库既不是“纯产品代码仓”，也不是“纯治理仓”，更不是“纯材料仓”；它是一个**内核实现、默认 profile 映射、仓库治理三者叠加共存**的现实工作区。
3. 本文选择把它解释为“默认 kernel workspace profile 的实例”，目的不是把仓库整体神圣化，而是把其中真正属于 profile 映射的部分单独抽出来，避免继续污染产品架构与 repo workflow。
4. 这里的“默认”只表示：在当前阶段，`dimc` 仓库是产品内核最主要的 dogfooding 工作空间，并且提供了一套可运行的本地默认映射；它不表示未来所有部署或所有 profile 都必须照搬这里的布局。

### 3. 当前 `dimc` 共享仓库同时承载的四类共享内容

先说明：这四类是当前共享仓库中的并存层次，不等于四者都属于项目落地层；本文只解释第三层“项目落地层”的部分。
1. **产品定义**
   - 主要承载面是正式架构文档和正式产品子规范，例如：
   - `docs/PROJECT_ARCHITECTURE.md`
   - `docs/STORAGE_ARCHITECTURE.md`
   - `docs/CORE_OBJECT_MODEL.md`
   - `docs/EVIDENCE_POLICY_AND_CAUSALITY_GRADES.md`
2. **产品内核实现**
   - 主要承载面是 `src/dimcause/` 及其相关入口文件，例如：
   - `src/dimcause/cli.py`
   - `src/dimcause/cli_export.py`
   - `src/dimcause/cli_graph.py`
   - `src/dimcause/core/`
   - `src/dimcause/storage/`
   - `src/dimcause/reasoning/`
   - `src/dimcause/search/`
   - `src/dimcause/importers/`
   - `src/dimcause/scheduler/`
   - `src/dimcause/watchers/`
   - `src/dimcause/audit/`
   - `src/dimcause/services/`
   - `src/dimcause/tui/`
3. **默认 workspace profile 映射**
   - 主要承载面是当前工作目录中被用作本地材料、证据工件、报告工件、索引/存储支撑面的那些表面。
   - 当前工作目录中最清晰的本地材料承载面之一是 `docs/logs/`；原始导出材料默认保留在仓库外导出目录。
   - 当前共享仓库里仍保留的生成型审计工件主要出现在 `docs/audit/`。
   - 当前仓库中的本地索引、知识建模与检索能力则主要通过 `src/dimcause/core/`、`src/dimcause/storage/`、`src/dimcause/reasoning/`、`src/dimcause/search/` 这些代码表面来实现。
4. **当前 repo 内部治理**
   - 主要承载面包括 `.agent/rules/`、`docs/coordination/`、本地开发控制层中的临时协作目录、`scripts/check.zsh`、`scripts/preflight_guard.py` 等。
   - 它们属于当前仓库的协作与门禁现实，不属于 workspace profile 本体。
5. **本地开发控制层**
   - 它在本项目中真实存在，但默认不进入共享入口。
   - 本文只在边界判断中承认它的存在，不把它写成本层正式内容。

### 4. 当前 Default Workspace Profile 回答的核心问题

1. 当前默认本地工作空间把哪些输入面视为“默认可接入材料”。
2. 当前默认本地工作空间把哪些目录或本地介质当作证据与工件的承载面。
3. 当前默认本地工作空间把运行时、知识建模和派生索引主要依赖于哪些本地代码与本地存储实现表面。
4. 当前默认本地工作空间如何在一个仓库中同时容纳代码、材料、工件与派生结果，而不把这种共址关系误写成产品普遍要求。

### 5. 当前 `dimc` 仓库对产品内核的映射方式

#### 5.1 解释与接口表面

1. 当前仓库把命令行与相关入口能力主要放在 `src/dimcause/cli.py`、`src/dimcause/cli_export.py`、`src/dimcause/cli_graph.py`。
2. 当前仓库把交互式与展示相关表面放在 `src/dimcause/tui/`、`src/dimcause/ui/`、`src/dimcause/visualization/`。
3. 这些表面属于产品内核的接口实现，不等于 workspace profile 本体；workspace profile 只解释“当前本地工作空间怎样接住这些接口的输入输出”。

#### 5.2 运行内核与运行控制表面

1. 当前仓库中与运行管理、守护、轮询和执行控制最接近的代码表面，主要位于：
   - `src/dimcause/scheduler/`
   - `src/dimcause/services/`
   - `src/dimcause/watchers/`
   - `src/dimcause/daemon/`
2. 这说明当前默认 profile 确实把一部分运行能力与本地工作空间强绑定在同一仓库中。
3. 但这并不意味着未来所有 profile 都必须采用相同的目录拆分、相同的本地运行方式或相同的运行态落点。
4. 当前仓库里如果存在某些 repo-local 运行辅助表面，也只能被理解为当前 profile 的现实依附面，而不是产品运行架构本体。

#### 5.3 材料接入与证据承载表面

1. 当前默认 profile 的材料接入面明显带有“本地优先、仓库共址”的特征：
   - `docs/logs/` 在当前工作目录中承载按日期组织的本地日志与记录材料，但默认不进入 git
   - 仓库外导出目录承载原始导出材料
   - `src/dimcause/importers/` 承载目录导入与 Git 导入代码
2. 这些路径说明：当前 profile 倾向于把“本地材料集”和“产品内核代码”放在同一工作空间中运营。
3. 但这仍然只是当前默认 profile 的选择，不表示未来 profile 必须使用 `docs/logs/` 或必须把原始导出放进仓库内。
4. 同理，`docs/audit/` 这类路径当前可以承载共享审计工件，但这也是当前 profile 的现实表面，不是产品级固定目录规范。

#### 5.4 知识建模与对象化表面

1. 当前仓库把对象模型、本体、历史、时间线、追踪与部分知识组织能力主要放在：
   - `src/dimcause/core/`
   - `src/dimcause/reasoning/`
   - `src/dimcause/storage/graph_store.py`
   - `src/dimcause/storage/markdown_store.py`
2. 这表明当前默认 profile 采用“代码内核 + 本地材料 + 本地图谱/索引实现”共址的方式来承接对象化、关系化和解释准备。
3. 但这里需要明确：这些代码表面属于**内核实现**，不是 workspace profile 本体；workspace profile 本体只解释“当前工作空间怎样让这些内核能力拥有默认输入、默认承载面和默认结果落点”。

#### 5.5 派生索引与检索表面

1. 当前仓库中与派生索引、检索与可重建加速结构最接近的代码表面主要包括：
   - `src/dimcause/core/event_index.py`
   - `src/dimcause/core/code_indexer.py`
   - `src/dimcause/storage/chunk_store.py`
   - `src/dimcause/storage/vector_store.py`
   - `src/dimcause/search/`
2. 当前工程型 default profile 中，`Deterministic Precision Retrieval` 的一个显性承载面是 `src/dimcause/search/unix_retrieval.py`。
3. 这说明当前 profile 的检索设计既依赖语义/索引类加速，也依赖工程环境中的确定性精确召回。
4. 但本文不把任何当前模块名、任何当前索引文件名、任何当前缓存路径写成所有 profile 的固定要求。

### 6. 当前 Default Workspace Profile 的四层映射

#### 6.1 Evidence Layer 的当前默认映射

1. 作为当前 default workspace profile 的默认本地映射，而不是产品层定义或正式存储架构补充规范，当前 `dimc` 仓库中的 Evidence Layer 主要体现为：
   - `docs/logs/` 这类按日期组织的本地记录材料（位于当前工作目录中，但默认不进入 git）
   - 仓库外导出目录中的原始导出材料
   - `docs/audit/` 这类共享审计工件目录
2. 这些映射表明：当前 default profile 把本地材料与一部分生成型证据工件共同保存在仓库可见的文档表面中。
3. 但 Evidence Layer 的产品级定义并不要求必须使用 `docs/` 前缀，也不要求必须按当前日期目录方式组织。

#### 6.2 Runtime Layer 的当前默认映射

1. 作为当前 default workspace profile 的默认本地映射，而不是产品层定义或正式存储架构补充规范，当前 `dimc` 仓库把运行能力的代码表面主要放在 `scheduler`、`services`、`watchers`、`daemon` 一带。
2. 当前 default profile 的现实表现是运行控制与本地工作空间共址，但这不要求未来 profile 必须把运行态与仓库本身绑定在同一结构里。
3. 当前仓库中如果存在 repo-local 的运行辅助面或临时运行面，它们也只能被理解为当前 profile 的实现依附，而不能被上升为 Runtime Layer 的产品级定义。

#### 6.3 Knowledge Layer 的当前默认映射

1. 作为当前 default workspace profile 的默认本地映射，而不是产品层定义或正式存储架构补充规范，当前 `dimc` 仓库把对象、本体、关系建模、验证、追踪与部分知识持久逻辑主要放在 `core`、`reasoning` 与 `storage/graph_store.py` 等代码表面。
2. 当前 default profile 因此表现为：知识建模能力与本地材料集、派生索引能力共同驻留在同一工作空间中。
3. 但这不等于 Knowledge Layer 必须由当前目录结构承载，也不等于产品必须复用当前仓库的代码路径命名。

#### 6.4 Derived Index Layer 的当前默认映射

1. 作为当前 default workspace profile 的默认本地映射，而不是产品层定义或正式存储架构补充规范，当前 `dimc` 仓库把事件索引、代码索引、chunk 存储、向量存储、检索与排序能力分布在 `core`、`storage` 与 `search` 的相关模块中。
2. 当前 default profile 因而呈现出“本地材料 + 本地索引 + 本地检索”的共址映射。
3. 但这些都是当前 profile 的默认实现现实，不是产品对所有 profile 的固定物理要求。

### 7. 哪些内容属于 Workspace Profile

1. 当前默认材料根与默认证据承载面的选择。
2. 当前默认生成型工件和报告工件的落点选择。
3. 当前默认本地检索、索引与知识承载能力如何与仓库共址。
4. 当前默认工作空间如何让产品内核在一个本地仓库里同时接住代码、材料、工件与派生结构。
5. 当前哪些实现选择是“默认 profile 选择”，而不是产品普遍要求。

### 8. 哪些内容不属于 Workspace Profile

1. 产品架构本体，不属于本文。
2. 存储四层职责定义，不属于本文。
3. 对象模型与证据政策本体，不属于本文。
4. 当前 repo 的分支纪律、审查门禁、协作模板、预写入检查、交付信号、格式化策略、虚拟环境与 secrets 管理，不属于本文。
5. 当前 repo 的临时讨论目录、协调目录和治理脚本，不属于本文。

### 9. 当前实现中最需要明确标注为“默认 Profile 选择”的部分

1. **代码与材料共址**：当前 `dimc` 仓库把产品内核代码与本地材料承载面放在一个仓库中，这是当前 default profile 的选择，不是产品普遍要求。
2. **`docs/` 的混合承载**：当前 `docs/` 同时容纳正式设计文档、proposal、研究材料、日志材料和报告工件，这是当前仓库现实，不是产品级推荐目录法则。
3. **工程导向的输入面**：当前 profile 对代码仓库、日志、聊天导出、审计报告等工程材料特别友好；这说明工程是当前最强默认 profile，但不表示产品只能做工程调查。
4. **本地检索与本地索引共址**：当前 profile 倾向于把检索、索引与材料工作区放在一起；未来 profile 完全可以选择不同的本地组织方式。
5. **repo-local 的运行辅助面**：当前仓库里的某些辅助脚本、临时运行面或本地状态面，只能解释为当前 profile 的工程现实，不应被产品化。

### 10. 哪些区域应被明确排除为 Repo Internal Workflow

1. `.agent/rules/`
2. `docs/coordination/`
3. `tmp/coordination/`
4. 本地开发控制层中的临时讨论与协调目录
5. `scripts/check.zsh`
6. `scripts/preflight_guard.py`
7. 其他用于当前仓库门禁、审查、流程治理和临时协作的脚本与目录

这些区域可以影响当前仓库怎样工作，但它们不构成 workspace profile 本体语义。

### 11. 未来其他 Workspace Profile 可能变化的点

1. 材料根不一定在仓库内，也不一定使用 `docs/logs/`。
2. 原始导出材料不一定保存在 repo 内。
3. 生成型证据工件不一定保存在 `docs/audit/`。
4. 运行态不一定与产品代码仓共址。
5. 知识承载与派生索引不一定沿用当前模块与当前物理落点。
6. 不同领域 profile 可能激活不同材料类型、不同解释模板、不同证据权重，但不应重写产品内核。

### 12. 本文明确不做什么

1. 本文不把 `dimc` 仓库整体写成产品本体。
2. 本文不把任何当前目录结构写成产品普遍要求。
3. 本文不把当前 repo 内部 workflow 写进 workspace profile 本体。
4. 本文不重新定义产品架构、存储职责、对象模型或证据政策。
5. 本文不试图用当前仓库现实去反推产品架构真理源。

## 当前结论

1. 当前 `dimc` 仓库应被理解为一个**同时承载产品定义、产品实现、项目落地和仓库治理**的共享工作空间；本地开发控制层则默认保留在本地开发目录中。
2. `WORKSPACE_PROFILE_V1` 的任务，不是把这个仓库整体上升为产品本体，而是只把其中**属于第三层“项目落地层”**的部分单独解释出来。
3. 因而，后续若将本文继续收敛为更正式版本，应坚持三条线：
   - 产品定义继续留在正式架构文档与正式产品子规范中
   - 产品实现继续由 `src/`、`tests/` 和相关运行入口承载
   - 项目落地层只写“本项目如何承载并默认运行产品”
   - 仓库治理层另文处理，不回流进本文

## 起草约束与审计附录

1. 本附录只记录本次起草所依赖的上位文档与当前仓库现实，不属于 workspace profile 正文。
2. 本文的主要上位依据包括：
   - `docs/PROJECT_ARCHITECTURE.md`
   - `docs/STORAGE_ARCHITECTURE.md`
   - `docs/CORE_OBJECT_MODEL.md`
   - `docs/EVIDENCE_POLICY_AND_CAUSALITY_GRADES.md`
   - `docs/ARCHITECTURE_INDEX.md`
   - `docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md`
3. 本文对当前仓库现实的映射，额外基于以下已核对事实：
   - 当前仓库现实已核对
   - 当前工作目录中确实存在 `src/dimcause/`、`docs/logs/`、`docs/audit/`、`.agent/rules/`、`docs/coordination/`、本地开发控制层中的临时协作目录、`scripts/check.zsh`、`scripts/preflight_guard.py` 等相关表面；其中 `docs/logs/` 默认不进入 git，原始导出材料默认位于仓库外导出目录
4. 本文没有修改受保护设计文档：
   - `docs/PROJECT_ARCHITECTURE.md`
   - `docs/STORAGE_ARCHITECTURE.md`
   - `docs/V6.0/DEV_ONTOLOGY.md`
