# 架构索引

## 文档目的

1. 本文是当前仓库中**正式共享文档**的稳定阅读入口。
2. 本文采用五层结构，但不把五层写成五个同轴并列层，而是按三类域来组织：
   （1）产品域：产品定义层、产品实现层；
   （2）项目桥接域：项目落地层；
   （3）工程复用域：仓库治理层、本地开发控制层。
3. 本索引只覆盖**共享仓库内容**中的前四层：
   （1）产品定义层；
   （2）产品实现层；
   （3）项目落地层；
   （4）仓库治理层。
4. 第五层“本地开发控制层”在当前项目中是合法且必要的，但它默认保留在本地开发目录，不构成正式共享入口的一部分。
5. 本文不重写任何一层的定义，只说明：
   （1）每一层的正式入口在哪里；
   （2）这些入口应按什么顺序阅读；
   （3）层与层之间发生冲突时，优先级如何判断。

## 五层总览

### 产品域

1. 第一层：产品定义层
2. 第二层：产品实现层

### 项目桥接域

1. 第三层：项目落地层

### 工程复用域

1. 第四层：仓库治理层
2. 第五层：本地开发控制层

## 正式共享入口

### 第一层：产品定义层

1. [PROJECT_ARCHITECTURE.md](./PROJECT_ARCHITECTURE.md)
2. [STORAGE_ARCHITECTURE.md](./STORAGE_ARCHITECTURE.md)
3. [STORAGE_ARCHITECTURE_DRAFT_V1.md](./PROPOSALS/STORAGE_ARCHITECTURE_DRAFT_V1.md)
4. [CORE_OBJECT_MODEL_V1.md](./PROPOSALS/CORE_OBJECT_MODEL_V1.md)
5. [EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md](./PROPOSALS/EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md)

本层回答：
1. 产品是什么；
2. 产品依靠什么长期稳定语义运行；
3. 运行内核、对象模型、证据政策和存储职责如何分层。

### 第二层：产品实现层

1. [src/dimcause](../src/dimcause)
2. [tests](../tests)
3. [UNIX_RETRIEVAL_CONTRACT.md](./PROPOSALS/UNIX_RETRIEVAL_CONTRACT.md)
4. [V6.3_extraction_pipeline_design.md](./PROPOSALS/V6.3_extraction_pipeline_design.md)
5. [V6.3_CAUSAL_LINKER_DESIGN.md](./PROPOSALS/V6.3_CAUSAL_LINKER_DESIGN.md)
6. 当前与产品运行直接相关的入口脚本与打包配置

本层回答：
1. 产品目前被实现成什么样；
2. 源代码、测试和运行脚本目前做到哪一步；
3. 当前关键实现设计契约、技术债、未完成迁移和实现现实是什么。

本层规则：
1. 本层属于产品本身，不应被排除出产品主线；
2. 本层必须服从第一层的产品定义；
3. 当前实现现实不能反向改写产品定义。

### 第三层：项目落地层

1. [WORKSPACE_PROFILE_V1.md](./PROPOSALS/WORKSPACE_PROFILE_V1.md)
2. [pyproject.toml](../pyproject.toml)
3. [README.md](../README.md)
4. [README_zh-CN.md](../README_zh-CN.md)

本层回答：
1. 本项目怎样承载、组织并默认运行这个产品；
2. 当前默认入口、目录组织、打包方式和本地落地约定是什么；
3. 哪些内容是“本项目的默认选择”，而不是产品普遍要求。

### 第四层：仓库治理层

1. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](./PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)
2. [docs/coordination](./coordination)
3. [.agent/rules](../.agent/rules)
4. [ci.yml](../.github/workflows/ci.yml)
5. [scripts/preflight_guard.py](../scripts/preflight_guard.py)
6. [scripts/pr_ready.py](../scripts/pr_ready.py)
7. [scripts/check.zsh](../scripts/check.zsh)

本层回答：
1. 这个仓库怎样被协作、验证、保护和收口；
2. 分支、worktree、session、Task Packet、preflight、PR_READY、merge gate 的规则是什么；
3. 哪些内容属于共享工程规则，哪些不得回流进入产品定义或项目落地。

### 第五层：本地开发控制层

1. 本层在本项目中是合法且必要的。
2. 但它默认不进入正式共享入口。
3. 它负责的是：
   （1）当前任务板与经验记录；
   （2）运行中的 Task Packet 实例；
   （3）本地讨论、临时验证和运行态工件；
   （4）本地 Agent 记忆与会话态。
4. 对第五层的判断与维护，应在本地开发资料中进行，而不是回写到正式共享入口中。

## 标准阅读顺序

1. 第一层：先读产品定义层文档，明确产品边界。
2. 第二层：再看产品实现层入口，确认当前代码现实。
3. 第三层：之后读取项目落地层文档，理解本项目如何承载这个产品。
4. 第四层：最后读取仓库治理层文档，理解当前仓库怎样协作、验证和收口。

## 快速恢复顺序

1. [PROJECT_ARCHITECTURE.md](./PROJECT_ARCHITECTURE.md)
2. [STORAGE_ARCHITECTURE.md](./STORAGE_ARCHITECTURE.md)
3. [CORE_OBJECT_MODEL_V1.md](./PROPOSALS/CORE_OBJECT_MODEL_V1.md)
4. [EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md](./PROPOSALS/EVIDENCE_POLICY_AND_CAUSALITY_GRADES_V1.md)
5. [src/dimcause](../src/dimcause)
6. [tests](../tests)
7. [WORKSPACE_PROFILE_V1.md](./PROPOSALS/WORKSPACE_PROFILE_V1.md)
8. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](./PROPOSALS/REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)

## 冲突优先级

1. 产品定义层优先于产品实现层、项目落地层和仓库治理层。
2. 产品实现层可以暴露现实偏差，但不能重写产品定义。
3. 项目落地层只能解释“本项目怎样落地”，不能吸收仓库治理规则。
4. 仓库治理层只能约束协作与交付，不能反向定义产品能力或项目默认语义。
5. 第五层本地开发控制层可以维持当前现场连续性，但不得被抬升为正式共享真理源。

## 本索引要防止的错误

1. 把当前代码现实直接写成产品定义。
2. 把项目默认落地方式写成产品普遍要求。
3. 把仓库治理规则写成产品能力。
4. 把本地开发控制内容误写进正式共享入口。
5. 因为准备公开或准备收口，就把本地开发控制层从工作目录物理清空。

## 维护规则

1. 新增正式共享文档时，必须先判断它属于前四层中的哪一层。
2. 第五层内容默认不加入本索引。
3. 若某文档同时涉及两层以上内容，必须先拆边界，再决定入口位置。
4. 修改本索引时，不得把本地草稿、讨论稿或临时控制文件写成正式入口。
