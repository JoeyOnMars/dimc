# Repo Workflow and Governance Boundary v1

Status: Draft v1 (2026-03-12)  
Scope: Current `dimc` repository only  
Type: Repository governance boundary proposal

## 1. 文档目的与边界

本文用于说明当前 `dimc` 仓库中的“项目开发流程与治理边界”到底指什么，以及它与产品架构、workspace profile 之间的严格分层关系。

当前 `dimc` 仓库同时承载三类不同层次的内容：

1. 产品内核实现
2. 默认 workspace profile 映射
3. 当前仓库内部 workflow / governance

这三类内容在当前仓库现实中并存，但并不属于同一层语义，也不应写进同一类文档。本文只解释第三类，即当前仓库内部 workflow / governance 的边界、作用范围与维护原则。

本文不做以下事情：

1. 不重新定义产品架构
2. 不重新定义存储架构
3. 不重新定义对象模型
4. 不重新定义证据政策或因果等级
5. 不把当前仓库目录结构写成产品普遍要求
6. 不把 repo-specific 协作规则写成产品能力或 workspace profile 本体

## 2. 三层边界总览

### 2.1 产品架构回答什么问题

产品架构回答的是：“DIMCAUSE 这个产品本体是什么，它解决什么问题，它依靠什么长期稳定语义运行。”

在当前正式文档体系里，产品架构已经收口为以下结论：

1. DIMCAUSE 是一套面向本地异构材料的证据驱动因果调查系统。
2. 它不是通用知识库、通用 RAG、AI SRE、调试 copilot 或通用 memory OS。
3. 它以 run-centric runtime kernel、面向本地异构材料的对象化与证据支撑因果推理、以及 `Evidence / Runtime / Knowledge / Derived Index` 四层职责分离为长期稳定架构主线。
4. `Deterministic Precision Retrieval` 已属于正式产品架构原则。

这些内容应由正式架构文档和上位 proposal 负责表达，而不是由仓库内部流程规则负责定义。

### 2.2 Workspace profile 回答什么问题

workspace profile 回答的是：“当前仓库怎样把产品内核实例化为一个默认本地 workspace。”

workspace profile 负责说明的是当前默认映射，而不是产品本体。例如：

1. 当前本地材料从哪些表面被接入
2. 当前默认的本地 artifact / storage / index 组合如何落地
3. 当前仓库如何把产品抽象映射成一个可运行的默认工作空间

workspace profile 可以描述当前默认选择，但不能把这些选择上升为产品普遍要求。

### 2.3 Repo workflow / governance 回答什么问题

repo workflow / governance 回答的是：“当前 `dimc` 仓库如何协作、保护文档、维护质量、控制变更、组织交付。”

它关注的是当前仓库这一协作对象的治理，不是产品运行时语义，也不是 workspace profile 的实例化逻辑。

换句话说：

1. 产品架构定义“产品是什么”
2. workspace profile 定义“当前仓库怎样映射这个产品”
3. repo workflow / governance 定义“当前仓库怎样被协作、被约束、被维护”

## 3. 当前 repo 内部 workflow / governance 的定义

本文所说的“当前 repo 内部 workflow / governance”，是指围绕当前 `dimc` 仓库建立的一组协作纪律、文档保护规则、交付门禁、环境约束、上下文维护方式和审计表达规范。

它的核心目标不是定义产品能力，而是降低当前仓库在协作过程中出现以下问题的概率：

1. 在错误分支上工作
2. 误改受保护设计文档
3. 在上下文衰减后继续错误推进
4. 把瞬时实现现实误写成长期架构结论
5. 把 repo-specific 流程误写成产品能力
6. 在没有检查的情况下提交不稳定变更

因此，repo workflow / governance 本质上是一套“当前仓库治理机制”，而不是“产品设计层语义”。

它通常包括以下几类内容：

1. 分支、session、worktree 与交付节律
2. 受保护文档的编辑前置检查与升级路径
3. 本地检查命令、格式与提交门禁
4. 当前仓库的环境准备与密钥处理方式
5. 任务上下文保持、checkpoint 与恢复机制
6. 审计、review、报告与问题分级表达格式
7. 当前仓库中的历史规则如何与新架构并存

它明确不包括以下内容：

1. 产品内核的本体定义
2. run、material、object、relation、validation、explanation 的产品层语义
3. 证据等级与因果等级的正式定义
4. 四层存储职责本身
5. 当前默认 workspace profile 的本地映射说明

## 4. 现有 rules 的归类

### 4.1 跨层行为约束，但不是产品定义

以下规则会影响“如何工作”和“如何写文档”，但它们不应被误当成产品定义或 workspace profile 定义：

1. `Honesty-And-Structure.md`
   - 作用：要求事实、推测、结论分开表达；不允许装懂；不允许把未验证内容写成既定事实。
   - 正确归属：跨层行为约束。
   - 边界说明：它约束表达方式与工作方式，不定义产品本体。
2. `Agent-Behavior-And-Professionalism.md`、`Agent-Planning-Standard.md`、`chinese.md`
   - 作用：约束代理工作风格、计划表达和语言输出。
   - 正确归属：跨层行为约束。
   - 边界说明：它们不应反向成为产品或 workspace profile 的语义来源。

### 4.2 明确属于 repo 内部 workflow / governance 的规则

以下规则主要属于当前仓库内部 workflow / governance：

1. `agent-git-workflow.md`
   - 主要内容：branch naming、One Task One Branch One Session、`[PR_READY]`、preflight、protected-doc gate、merge/rebase 纪律、worktree 约束、Task Packet。
   - 正确归属：repo workflow / governance。
2. `anti-forgetting.md`
   - 主要内容：启动检查、checkpoint、`task.md`、`[CONTEXT_DECAY]` 提醒、恢复流程。
   - 正确归属：repo workflow / governance。
3. `ruff-check.md`
   - 主要内容：`scripts/check.zsh`、格式化与 lint gate、禁止随意运行某些格式化动作。
   - 正确归属：repo workflow / governance。
4. `Environment-Setup.md`
   - 主要内容：虚拟环境、`.env`、密钥、启动命令与本地环境依赖。
   - 正确归属：repo workflow / governance。
5. `Code-Audit.md`
   - 主要内容：审计输出格式、P0/P1/P2 问题分级、代码卫生与报告组织方式。
   - 正确归属：repo workflow / governance。
   - 补充说明：其中保留的旧产品叙事不能覆盖正式架构与 proposal。

### 4.3 含有历史叙事或混合语义的规则

以下规则包含对系统的描述，但它们当前更适合作为历史语境或仓库局部约束，而不是新的产品真理源：

1. `SYSTEM_CONTEXT.md`
   - 当前问题：仍保留 `Local-first Causal Memory Engine for AI Agents` 等旧阶段产品叙事。
   - 正确使用方式：可作为历史语境和仓库背景材料读取，但在产品层冲突时必须让位于正式架构文档、上位 proposal 和 handoff。
2. `dimcause-ai-system.md`
   - 当前问题：仍明显保留 event、WAL、日志链、旧实现中心叙事。
   - 正确使用方式：只能作为旧阶段系统理解与当前仓库局部实现语境参考，不能反向重定义产品。
3. `DIMCAUSE.SecurityBaseline.ABC.md`
   - 当前问题：部分表述仍与旧阶段 event/log/WAL 中心设计绑定较深。
   - 正确使用方式：其操作性和保护性要求可以保留在仓库治理层，但不能被误写成新的产品架构定义。

## 5. 明确属于内部治理的内容

以下内容应明确保留在“当前 repo 内部 workflow / governance”层，而不是回流进入产品架构或 workspace profile 本体。

### 5.1 Git 协作与交付纪律

1. 分支命名规则
2. `main` 保护与禁止直接开发
3. One Task / One Branch / One Session
4. PR_READY 作为交付状态标记
5. merge、push、rebase 的仓库内纪律
6. worktree 使用与清理规则

这些都是当前仓库的协作和变更控制机制，不描述产品能力。

### 5.2 受保护文档与前置门禁

1. 哪些文档被视为受保护设计文档
2. 修改这些文档前的 preflight / 审查要求
3. 什么情况下必须升级为更高审慎度处理

这些都是为了保护当前仓库中的关键文档资产，不是产品运行时的一部分。

### 5.3 本地检查与格式门禁

1. `scripts/check.zsh` 作为当前仓库检查入口
2. ruff / lint / format 的当前执行纪律
3. 提交前检查与失败处理流程

这些是当前仓库的质量控制面，不是产品层设计。

### 5.4 环境、密钥与运行准备

1. 虚拟环境要求
2. `.env` 与本地密钥管理方式
3. 当前仓库命令如何在本地环境中运行

这些属于当前仓库的运维和开发准备条件，不是产品架构结论。

### 5.5 上下文保持与协作恢复

1. checkpoint
2. `task.md`
3. `CONTEXT_DECAY` 提醒
4. Task Packet 与线程交接材料

这些内容解决的是当前仓库协作中的上下文连续性问题，不是产品本体的一部分。

### 5.6 审计、review 与报告表达

1. 审计输出模板
2. P0 / P1 / P2 问题分级
3. review 输出格式
4. 当前仓库如何组织问题与修复记录

这些内容属于当前仓库的治理表达面，不应上升为产品能力定义。

## 6. 明确不应进入产品架构或 workspace profile 的内容

以下内容如果被写入产品架构或 workspace profile，本质上都属于层级污染。

1. branch naming、`[PR_READY]`、One Task / One Branch / One Session
2. preflight、protected-doc gate、worktree / session 纪律
3. `scripts/check.zsh`、ruff/check gate、当前 lint / format 流程
4. venv、`.env`、本地 secrets 处理方式
5. checkpoint、`task.md`、Task Packet、`CONTEXT_DECAY`
6. 审计模板、review 模板、P0 / P1 / P2 输出格式
7. 当前仓库的协作型目录、临时目录、讨论目录、交接材料目录
8. 当前某些实现把代码、文档、日志、报告混合放置的仓库现实
9. 旧规则中的 event / WAL / `docs/logs` 中心叙事，如果它们被拿来重写产品定义
10. 当前代理行为规范、计划规范和输出规范，如果它们被误写成产品接口约束

应特别强调：

1. 当前仓库目录结构只能被当作当前仓库现实或当前默认映射现实读取，不能自动上升为产品普遍要求。
2. 当前仓库的治理规则只能约束当前仓库如何协作，不能自动变成产品能力。
3. workspace profile 只能解释默认映射，不能吸收 repo-specific 治理机制。

## 7. 旧规则叙事与新架构的冲突处理原则

### 7.1 当前可见冲突

当前规则、handoff、正式架构之间至少存在以下可见冲突：

1. `SYSTEM_CONTEXT.md` 仍把系统叙述为 `Local-first Causal Memory Engine for AI Agents`，而正式架构已经收口为“面向本地异构材料的证据驱动因果调查系统”。
2. `Code-Audit.md` 仍保留“AI 决策审计基础设施 / 黑匣子记录仪”叙事，而正式架构已经把该表述降回局部场景语境。
3. `dimcause-ai-system.md` 与部分安全基线文本仍以 event、WAL、日志链和旧实现中心表述为核心，而正式架构已转向 run-centric runtime kernel 与四层职责分离。

### 7.2 优先级判断

当这些材料彼此冲突时，应按以下优先级处理：

1. 正式架构文档
2. 上位 proposal
3. 最新 handoff 中已确认的产品层结论
4. workspace profile 中对当前默认映射的说明
5. repo workflow / governance 文档与 rules 中的仓库治理约束

这意味着：

1. rules 可以约束当前仓库如何工作
2. rules 不可以反向定义产品本体
3. rules 也不可以反向重写 workspace profile 的本体边界
4. 含旧叙事的 rules 在产品层冲突时应被视为历史语境或仓库局部约束

### 7.3 实际处理原则

当一个规则文件同时含有“操作性约束”和“过时产品叙事”时，应拆开处理：

1. 保留其中仍有效的仓库治理约束
2. 显式降级其中过时的产品叙事
3. 不为了表面一致而把旧叙事重新写回正式架构或 workspace profile
4. 如需更新旧规则，应以“纠正分层”而不是“回收产品定义”为目标

## 8. 后续维护建议

为了避免三层边界再次混淆，后续维护建议如下：

1. 新增或修改规则文件时，先标明它属于哪一层：
   - 产品架构层
   - workspace profile 层
   - repo workflow / governance 层
   - 跨层行为约束层
2. 凡是 branch、preflight、worktree、lint gate、venv、checkpoint、审计模板之类内容，默认先归入 repo governance，而不是产品层。
3. 凡是对象模型、证据政策、因果等级、四层职责、运行时主链之类内容，默认先归入正式架构与上位 proposal，而不是 rules。
4. 凡是当前本地默认材料表面、默认 artifact layout、默认 storage/index 组合之类内容，默认先归入 workspace profile，而不是产品架构。
5. 含历史叙事的规则文件应逐步补充边界说明，避免后来读者把旧语境误当作当前产品定义。
6. 当 repo workflow 与 workspace profile 同时变化时，应优先确认“变的是默认映射，还是变的是内部治理”，避免混写。
7. 后续如需把本文从 proposal 提升为正式仓库治理说明，应保持它仍然只解释当前仓库治理边界，而不接管产品架构或 workspace profile 的职责。

## 9. 结论

当前 `dimc` 仓库中的三层语义必须继续严格切开：

1. 产品架构负责定义产品本体
2. workspace profile 负责定义当前默认映射
3. repo workflow / governance 负责定义当前仓库如何被协作、被保护、被维护

本 proposal 的作用，不是增加新的产品设计，而是防止当前仓库的治理现实继续污染产品架构与 workspace profile。

只要这条边界不被重新混淆，旧规则可以继续作为仓库治理材料存在，正式架构与 workspace profile 也才能保持稳定、可维护、可迁移。
