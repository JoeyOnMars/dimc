# Core Object Model v1

## 文档定位

1. 本文是**产品职责层**的《Core Object Model v1》草案，目标是先定义产品的一等对象家族、对象边界、最小字段责任与层归属，再作为后续 `Evidence Policy and Causality Grades v1`、`PROJECT_ARCHITECTURE.md`、`STORAGE_ARCHITECTURE.md` 的前置约束。
2. 本文**不是**当前 repo 代码结构说明，不是当前 workspace 路径映射，也不是当前开发流程规则汇总。
3. 本文只定义对象语义、对象边界与对象的最小责任；本文**不**冻结具体表结构、目录结构、序列化格式、物理存储后端或 profile 的实现细节。
4. 本文默认服从已经形成的产品主链与四层存储草案：对象模型必须能落入 `Evidence / Runtime / Knowledge / Derived Index` 的职责切分，但不能反过来从当前实现路径推导对象本体。

## 已知事实

1. 当前正式产品架构已经收口为：**DIMCAUSE 是一套面向本地异构材料的证据驱动因果调查系统。**[`docs/PROJECT_ARCHITECTURE.md`; `docs/PROPOSALS/WORKSPACE_PROFILE_V1.md`]
2. 产品核心目标不是通用知识库、通用 RAG 平台或通用开发调度器，而是从给定材料中抽取、验证、组织尽可能强的因果关系，并输出可追溯、可分级、可解释的调查结论。[`docs/PROJECT_ARCHITECTURE.md`]
3. 当前正式产品架构已经把系统主线收敛为：接收本地材料、提升为结构化对象、生成并验证因果关系、输出带证据链和等级的解释结论。[`docs/PROJECT_ARCHITECTURE.md`]
4. 正式产品架构已经要求：统一运行单位应是 `Run`，`Task` 只是某种 `Run` 的语义化特例，不是唯一入口。[`docs/PROJECT_ARCHITECTURE.md`]
5. 当前正式产品架构已经把 `Material`、`MaterialVersion` 归为材料接入的核心对象合同，并把 `Entity`、`Event`、`Decision`、`Claim`、`Task`、`Symbol`、`Artifact`、`Check`、`Result`、`Relation` 归入对象装配与知识构建的关键对象家族。[`docs/PROJECT_ARCHITECTURE.md`]
6. 当前正式产品架构已经明确：`Event` 很重要，但不能吞掉所有对象类型，Knowledge Layer 必须允许多对象共存。[`docs/PROJECT_ARCHITECTURE.md`]
7. 当前正式存储架构已经确定四层职责：Evidence 保存原始证据和可审计工件，Runtime 保存可变运行状态，Knowledge 保存结构化对象与关系，Derived Index 保存可重建索引与加速结构。[`docs/STORAGE_ARCHITECTURE.md`]
8. 当前正式存储架构已经明确：四层差异核心不在介质，而在可变性、真理源地位、生命周期、可重建性与对外语义。[`docs/STORAGE_ARCHITECTURE.md`]
9. 当前《存储架构草案 v1》已经把 Evidence Layer 明确拆成 `Source Materials` 与 `Generated Evidence Artifacts` 两类子对象，并要求在 provenance、生命周期、版本语义、引用方式上显式区分二者。[`docs/PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md`]
10. 当前《存储架构草案 v1》已经要求：Knowledge Layer 中关系状态历史必须可回放，“当前状态”只是投影，不得成为唯一记录。[`docs/PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md`]
11. 当前正式产品架构已经明确：对象模型需要单独成文，并至少覆盖 `Run`、`Material`、`Decision`、`Claim`、`Task`、`Symbol`、`Check`、`Result`、`Relation` 等关键对象家族，而不是把这些职责散落在实现目录或 profile 说明里。[`docs/PROJECT_ARCHITECTURE.md`; `docs/STORAGE_ARCHITECTURE.md`]
12. 当前正式共享文档已经明确：产品架构、workspace profile、当前项目开发流程必须拆开，不能把 repo 目录、日志路径、分支纪律或治理规则写成产品本体。[`docs/ARCHITECTURE_INDEX.md`; `docs/PROPOSALS/WORKSPACE_PROFILE_V1.md`; `docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md`]

## 推测与假设

1. [推测] 《Core Object Model v1》首先应冻结的是**对象家族语义与最小字段责任**，而不是数据库表设计或物理目录布局。原因：事实 #7、#8、#12 已经说明当前阶段要先固定产品职责和层语义，而不是从实现介质倒推产品本体。
2. [推测] `Material` 与 `MaterialVersion` 应当是**跨 Evidence 与 Knowledge 的双重对象**：Evidence 保存其原始快照与可回放内容，Knowledge 保存其稳定身份、版本关系、材料间链接与可查询语义。原因：事实 #3、#5、#7、#9 同时要求材料既是证据入口，又要进入对象化主链。
3. [推测] `Run` 应保持为**Runtime-first** 的一等对象；Evidence 与 Knowledge 最多保留对 `Run` 的引用和 provenance，而不应把运行状态本身挪成 Knowledge 真理源。原因：事实 #4、#7、#8 已把 `Run` 和运行状态明确放到 Runtime 语义中心。
4. [推测] 本稿中的 13 个对象家族都应被视为**产品通用内核的一等对象家族**；领域 profile 主要负责它们的子类型、写入约束、关系集合、提取策略和证据政策，而不是发明另一套平行对象层。原因：事实 #2、#5、#6、#11 已经把这些对象放进“跨材料对象化”的主链，而不是某个单独 profile 的临时补丁。
5. [推测] `Artifact` 这个对象必须与 Evidence Layer 的 `Generated Evidence Artifacts` 严格区分：前者是可参与关系与解释的对象家族，后者是系统为审计、回放、引用而持久化的证据工件。原因：事实 #7、#9 已把“知识对象”和“证据工件”区分开。
6. [推测] `Check` 与 `Result` 不能合并成一个对象：`Check` 更像检查动作、检查定义或检查义务，`Result` 更像一次检查或一次运行产生的结构化结论。原因：事实 #2、#5、#7 已经要求系统同时表达检查过程、证据和调查结论。
7. [推测] `Claim` 与 `Relation` 也不能合并：`Claim` 是来自材料、角色或系统推断的命题；`Relation` 是经结构化整理后连接对象的边，并需要状态历史、等级与证据绑定。原因：事实 #3、#10 已把“关系候选”“验证”“关系状态历史”与对象化主链区分开。

## 结论与建议

### 1. 总体判断

1. 《Core Object Model v1》应被定义为：**为证据驱动因果调查系统提供一组可跨材料、跨运行、跨解释复用的一等对象家族，并明确这些对象在 Evidence、Runtime、Knowledge 三类真理源中的归属与最小字段责任。**依据: 事实 #1, #2, #3, #4, #5, #7, #8 + 推测 #1, #2, #3。
2. 本文的主语必须是**对象语义与对象边界**，而不是当前代码目录、当前 repo 里的文件路径、当前工程工作流或当前实现缺口。依据: 事实 #8, #12 + 推测 #1。
3. 本稿的职责不是一次性定完 ontology 全量类型，也不是提前冻结物理 schema；本稿应先为后续证据政策、领域 profile 与正式架构文档提供不可绕开的上位约束。依据: 事实 #8, #11, #12 + 推测 #1, #4。

### 2. 对象模型的共通约束

1. 进入产品对象模型的一等对象，必须至少回答五件事：**它是谁、它属于什么对象家族、它与哪些证据相连、它在什么时间或版本上下文中成立、它应落在哪一层做真理源。**依据: 事实 #2, #3, #7, #8, #9 + 推测 #1, #2, #3。
2. 任何进入 Knowledge Layer 的一等对象，都应具有**稳定身份**；其中“稳定”指的是可被跨材料引用、跨 run 复用、进入关系网络并被解释层持续引用，而不是指某个实现中的自增主键。依据: 事实 #3, #5, #6, #7, #8 + 推测 #1, #2, #4。
3. 任何一等对象如果能进入调查结论、报告引用或因果链解释，就必须能回到对应的 Evidence 引用，而不能只剩下 Derived Index 命中结果。依据: 事实 #2, #3, #7, #9 + 推测 #2, #5, #7。
4. `MaterialVersion` 这类版本对象必须按**不可覆盖的版本语义**定义；“当前版本”可以是投影，但某个历史版本一旦形成可引用快照，就不能被覆盖式写回。依据: 事实 #3, #5, #7, #8, #9 + 推测 #2。
5. `Run` 的生命周期状态应属于 Runtime 语义；`Task`、`Decision`、`Claim`、`Relation` 的调查语义应属于 Knowledge 语义。实现上可以存在引用和镜像，但不能混淆真理源。依据: 事实 #4, #5, #7, #8 + 推测 #3, #7。
6. `Relation` 的“当前状态”不得成为唯一记录；对象模型层必须默认其状态迁移历史可被保留和回放。依据: 事实 #10 + 推测 #7。
7. 本 v1 不把任何当前工程 profile 的目录、日志布局、临时状态文件或分支治理规则写成对象字段责任。依据: 事实 #12 + 推测 #1。

### 3. 产品通用内核与领域 profile 的切分

1. 本稿中列出的 13 个对象家族，全部视为**产品通用内核的一等对象家族**：`Run`、`Material`、`MaterialVersion`、`Entity`、`Event`、`Decision`、`Claim`、`Task`、`Symbol`、`Artifact`、`Check`、`Result`、`Relation`。依据: 事实 #2, #3, #5, #6, #11 + 推测 #4。
2. 领域 profile 负责决定的是：这些对象家族在某个领域中的**子类型体系、合法关系集合、提取策略、证据政策、显示风格与可选激活范围**；领域 profile **不应**改变这些对象家族在产品主链中的基本职责。依据: 事实 #2, #5, #6, #11, #12 + 推测 #4。
3. 某个 profile 可以选择“不主动产出某类对象”，但这属于 profile 的激活策略，不代表该对象家族从产品通用内核中被删除。依据: 事实 #2, #5, #11 + 推测 #4。
4. 任何 profile 都不应重新把所有对象压回单一 `Event` 或单一路径模型，否则会直接违背多对象共存和对象化主链。依据: 事实 #3, #5, #6 + 推测 #4, #7。

### 4. 对象与存储层的最低归属

1. `Run` 是**Runtime-first** 对象；它的一等真理源在 Runtime Layer。Evidence 和 Knowledge 只应保留对 `Run` 的引用、产出登记或 provenance，而不承载运行状态本体。依据: 事实 #4, #7, #8 + 推测 #3。
2. `Material` 与 `MaterialVersion` 是**Knowledge + Evidence 双重对象**：Evidence 保存原始内容、原始输入快照、历史版本快照；Knowledge 保存稳定身份、版本链、对象链接、材料语义与调查引用。依据: 事实 #3, #5, #7, #9 + 推测 #2。
3. `Entity`、`Event`、`Decision`、`Claim`、`Task`、`Symbol`、`Artifact`、`Check`、`Result`、`Relation` 都应作为**Knowledge Layer 的一等对象**存在；Evidence 层存它们所依赖的原始片段、附件、报告、日志或引用工件，但不应成为这些对象身份的唯一真理源。依据: 事实 #3, #5, #6, #7, #9, #10 + 推测 #5, #6, #7。
4. 在本 v1 指定的对象家族里，没有任何对象应被定义成“只存在于 Evidence”的一等对象；Evidence 更像对象的**证据承载层**，而不是这些一等对象的唯一身份层。依据: 事实 #7, #9 + 推测 #2, #5, #6。
5. Derived Index 不应成为任何一等对象的唯一归属层；它只能承载这些对象的索引、召回结构、遍历优化和缓存。依据: 事实 #7, #8 + 推测 #1。

### 5. 逐对象定义

1. `Run`
   - 定义：`Run` 是系统统一的运行单位，用来表达一次导入、分析、验证、索引重建、检查、报告生成或其他产品执行过程。
   - 最小字段责任：`run_id`（稳定运行标识）、`run_kind`（运行语义类型）、`input_refs`（输入对象或输入材料引用）、`state`（生命周期状态）、`context_refs`（执行上下文/父子运行/触发来源）、`output_refs`（产出物或结果引用）。
   - 主层归属：Runtime Layer。
   - 边界：`Run` 不是 `Task`；`Run` 回答“系统这次怎么跑”，`Task` 回答“被调查世界里要做什么或做了什么”。依据: 事实 #4, #7, #8 + 推测 #3。
2. `Material`
   - 定义：`Material` 是进入产品调查主链的材料入口对象，用来表达“某份被纳入调查范围的材料”。
   - 最小字段责任：`material_id`（稳定材料标识）、`material_kind`（材料家族/媒介类型）、`source_ref`（原始来源或导入来源）、`provenance_root`（材料来源根）、`current_version_ref`（当前版本投影）、`time_anchors`（采集/形成/可定位时间锚）。
   - 主层归属：Knowledge + Evidence。
   - 边界：`Material` 不是某个具体文件路径，也不等于某条 chunk；它表达的是“被调查系统承认的一份材料身份”。依据: 事实 #3, #5, #7, #9 + 推测 #2。
3. `MaterialVersion`
   - 定义：`MaterialVersion` 是某份材料在某个时间、版本点或采集状态下形成的不可替代快照。
   - 最小字段责任：`material_version_id`（稳定版本标识）、`material_ref`（所属材料）、`snapshot_ref`（不可变内容快照引用）、`version_anchor`（版本点/时间点/采集点）、`provenance_ref`（版本形成来源）、`supersession_ref`（与前后版本的替代关系）。
   - 主层归属：Knowledge + Evidence。
   - 边界：`MaterialVersion` 不是“当前内容”的覆盖写回，而是可回放、可引用、可被审计的历史快照对象。依据: 事实 #3, #5, #7, #8, #9 + 推测 #2。
4. `Entity`
   - 定义：`Entity` 是相对稳定、可被多份材料共同引用的对象，如人、组织、系统、模块、组件、地点、制度对象或概念对象。
   - 最小字段责任：`entity_id`（稳定对象标识）、`entity_type`（对象家族/子类）、`canonical_name`（规范名称）、`alias_set`（别名集合）、`scope_ref`（所属作用域/命名域）、`evidence_refs`（支持该实体存在或归一化的证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Entity` 不应用来替代 `Symbol` 或 `Event`；它强调的是较稳定的“对象是谁”，不是“发生了什么”。依据: 事实 #5, #6, #7 + 推测 #4。
5. `Event`
   - 定义：`Event` 是在时间上可锚定的一次发生、变化、动作、状态跃迁或交互。
   - 最小字段责任：`event_id`（稳定对象标识）、`event_type`（事件家族/子类）、`time_anchor`（时间点或时间区间）、`participant_refs`（参与对象引用）、`summary`（事件摘要）、`evidence_refs`（支撑该事件被识别的证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Event` 很重要，但不能吞掉 `Decision`、`Claim`、`Task`、`Check`、`Result` 等其它对象家族。依据: 事实 #5, #6, #7 + 推测 #4。
6. `Decision`
   - 定义：`Decision` 是某个角色或系统对行动方向、方案取舍、约束条件作出的承诺性选择。
   - 最小字段责任：`decision_id`（稳定对象标识）、`decision_type`（决策家族/子类）、`statement`（决策内容或摘要）、`decision_time`（作出时间或生效时间）、`scope_refs`（决策影响范围或对象范围）、`status`（采用/废弃/被替代等状态）、`evidence_refs`（证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Decision` 不等于 `Claim`；它强调的是“采纳了什么立场或行动方向”，而不是单纯提出了一个命题。依据: 事实 #2, #5, #6, #7 + 推测 #4, #7。
7. `Claim`
   - 定义：`Claim` 是来自材料、角色或系统推断的命题，可以是事实命题、解释命题或因果命题。
   - 最小字段责任：`claim_id`（稳定对象标识）、`claim_type`（命题家族/子类）、`proposition`（命题内容）、`claimant_ref`（提出者或来源）、`assessment_status`（待核验/被支持/被反驳/证据不足等状态）、`evidence_refs`（支撑或反驳该命题的证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Claim` 可以先存在于“命题层”，后续再被整理成 `Relation Candidate` 或被结构化进 `Relation`；它不应直接被等同为一条最终关系边。依据: 事实 #2, #3, #5, #10 + 推测 #7。
8. `Task`
   - 定义：`Task` 是被调查世界中的工作项、目标项、待办项或执行项。
   - 最小字段责任：`task_id`（稳定对象标识）、`task_type`（任务家族/子类）、`goal`（任务目标或说明）、`status`（未开始/进行中/完成/放弃等状态）、`time_window`（计划或执行时间窗口）、`owner_refs`（负责人或承担对象）、`evidence_refs`（材料依据）。
   - 主层归属：Knowledge Layer。
   - 边界：`Task` 不等于 `Run`；`Task` 是调查对象的一部分，`Run` 是系统执行的一部分。依据: 事实 #4, #5, #7 + 推测 #3, #4。
9. `Symbol`
   - 定义：`Symbol` 是在某个材料系统或命名体系中可被稳定寻址的正式标识对象，如函数名、类名、字段名、条款号、编号或其他形式化符号。
   - 最小字段责任：`symbol_id`（稳定对象标识）、`symbol_kind`（符号家族/子类）、`canonical_symbol`（规范符号表达）、`namespace_ref`（命名空间或所属系统）、`material_version_refs`（与哪些材料版本关联）、`evidence_refs`（支持该符号识别的证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Symbol` 强调“可寻址的形式化标识”，不是所有 `Entity` 都是 `Symbol`，也不是所有 `Material` 都必须产出 `Symbol`。依据: 事实 #2, #5, #7, #11 + 推测 #4。
10. `Artifact`
   - 定义：`Artifact` 是在调查对象层可被识别和引用的工件对象，如文档成品、交付物、构建产物、报告产物、方案稿、发布包或其他成形工作产物。
   - 最小字段责任：`artifact_id`（稳定对象标识）、`artifact_type`（工件家族/子类）、`role`（它在调查中的作用）、`producer_refs`（由谁或什么产生）、`material_or_version_refs`（与哪些材料或版本相关）、`evidence_refs`（证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：这里的 `Artifact` 是对象层工件，不等于 Evidence Layer 里的 `Generated Evidence Artifacts`；同一个物理文件可以既是 `MaterialVersion` 的快照来源，也映射出一个对象层 `Artifact`。依据: 事实 #5, #7, #9 + 推测 #2, #5。
11. `Check`
   - 定义：`Check` 是围绕某个对象、关系、材料或运行进行的检查、验证、审计、评估动作或检查义务。
   - 最小字段责任：`check_id`（稳定对象标识）、`check_type`（检查家族/子类）、`target_refs`（检查目标）、`policy_ref`（检查依据或规则来源）、`check_time`（发生时间）、`status`（待执行/已执行/失败/跳过等状态）、`evidence_refs`（证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Check` 不是最终结论；它描述“做了哪类检查/该做哪类检查”。依据: 事实 #2, #5, #7 + 推测 #4, #6。
12. `Result`
   - 定义：`Result` 是某次检查、某次运行或某次调查步骤产生的结构化结果对象。
   - 最小字段责任：`result_id`（稳定对象标识）、`result_type`（结果家族/子类）、`producer_ref`（由哪个 `Check`、`Run` 或步骤产生）、`target_refs`（结果作用于哪些对象）、`outcome`（结果结论或分类）、`result_time`（形成时间）、`evidence_refs`（证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Result` 不是报告文件本身；详细日志、报告正文、附件包等仍应进入 Evidence Layer 的工件体系。依据: 事实 #2, #5, #7, #9 + 推测 #5, #6。
13. `Relation`
   - 定义：`Relation` 是连接对象与对象的结构化边，用来表达因果、依赖、引用、归属、派生、支持、冲突等关系。
   - 最小字段责任：`relation_id`（稳定对象标识）、`relation_type`（关系家族/子类）、`endpoint_refs`（关系两端或多端对象）、`directionality`（有向/无向语义）、`current_state`（当前状态投影）、`state_history`（状态迁移历史）、`grade_refs`（证据覆盖与确定性等级）、`evidence_refs`（证据引用）。
   - 主层归属：Knowledge Layer。
   - 边界：`Relation` 不是瞬时缓存，不是 Derived Index 中的图优化边；它必须保留状态历史，支持候选、支持、确认、否决等演化回放。依据: 事实 #3, #7, #10 + 推测 #7。

### 6. 关键对象边界

1. `Run` vs `Task`：`Run` 是系统执行单位，`Task` 是被调查世界里的工作对象；一个 `Task` 可以触发多个 `Run`，一个 `Run` 也可以在没有 `Task` 对象的情况下存在。依据: 事实 #4, #5, #7 + 推测 #3, #4。
2. `Material` / `MaterialVersion` vs `Artifact`：前者回答“什么材料被纳入调查、它的历史版本是什么”，后者回答“在对象层被识别出的成形工件是什么”；二者可以同源，但不应强制一一对应。依据: 事实 #3, #5, #7, #9 + 推测 #2, #5。
3. `Event` vs `Decision`：不是所有事件都是决策，也不是所有决策只应被当作普通事件处理；决策需要自己的对象边界，因为它会直接约束后续任务、结果和关系。依据: 事实 #2, #5, #6 + 推测 #4。
4. `Claim` vs `Relation`：`Claim` 是命题层对象，允许尚未被充分验证；`Relation` 是连接对象的结构化边，并要求状态历史、等级和证据绑定。依据: 事实 #3, #10 + 推测 #7。
5. `Check` vs `Result`：`Check` 表达检查动作或检查义务，`Result` 表达一次检查或一次运行产出的结构化结论；一个 `Check` 可以产生多个 `Result`。依据: 事实 #2, #5, #7 + 推测 #6。
6. `Artifact` vs `Generated Evidence Artifacts`：前者属于对象模型，后者属于 Evidence Layer 的审计工件；实现时可以互相关联，但不得直接混成同一对象。依据: 事实 #7, #9 + 推测 #5。

### 7. 当前明确不做什么

1. 本稿**不**冻结各对象的物理 schema、数据库表、目录映射、JSON 结构、索引字段或 ID 编码算法。依据: 事实 #8, #12 + 推测 #1。
2. 本稿**不**定稿完整 ontology、完整 relation set、完整 profile subtype 树；这些仍需后续 `Evidence Policy and Causality Grades v1` 与领域 profile 文档继续收口。依据: 事实 #2, #5, #11 + 推测 #4。
3. 本稿**不**把 `RunSpec`、`RunState`、`RunInput`、`RunOutput`、`MaterialChunk`、`SourceSet` 等 supporting contract 直接提升为本轮的一等产品对象家族；它们后续可作为运行合同或材料处理合同继续定义。依据: 事实 #4, #5 + 推测 #1。
4. 本稿**不**把当前 repo 的目录、日志路径、worktree 纪律、preflight、分支规则或其他开发治理规则写入对象模型正文。依据: 事实 #12 + 推测 #1。

### 8. 后续文档接口

1. 下一份 `Evidence Policy and Causality Grades v1` 应继续回答：`Claim`、`Relation`、`Check`、`Result` 在什么证据条件下可进入哪些等级，哪些反证或缺口需要被显式记录。依据: 事实 #2, #3, #10, #11 + 推测 #6, #7。
2. 后续 `workspace profile` 或默认实现文档只能回答“这些对象如何映射到具体介质与目录”，不能回写这些对象的产品职责。依据: 事实 #7, #8, #12 + 推测 #1, #2, #3。
3. 后续重写或定稿 `PROJECT_ARCHITECTURE.md` 与 `STORAGE_ARCHITECTURE.md` 时，应以本稿和《存储架构草案 v1》作为上位约束，而不是反过来用旧实现结构压回对象边界。依据: 事实 #7, #8, #9, #10, #11, #12 + 推测 #1, #2, #4, #5, #7。

## 起草约束与审计附录

1. 本附录只记录本次起草所依赖的约束与依据清单，不属于对象模型正文。
2. 本次起草的主要依据文件包括：
   - `.agent/rules/Honesty-And-Structure.md`
   - `.agent/rules/agent-git-workflow.md`
   - `docs/PROJECT_ARCHITECTURE.md`
   - `docs/STORAGE_ARCHITECTURE.md`
   - `docs/PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md`
   - `docs/ARCHITECTURE_INDEX.md`
   - `docs/PROPOSALS/WORKSPACE_PROFILE_V1.md`
   - `docs/PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md`
3. 本文涉及的关键规则版本溯源如下：
   - `.agent/rules/Honesty-And-Structure.md`: `72d53e4 2026-02-25 23:16:27 +0800`
   - `.agent/rules/agent-git-workflow.md`: `e469d45 2026-03-08 21:53:55 +0800`
4. 本文没有修改受保护设计文档：
   - `docs/PROJECT_ARCHITECTURE.md`
   - `docs/STORAGE_ARCHITECTURE.md`
   - `docs/V6.0/DEV_ONTOLOGY.md`
