# PROPOSALS 目录说明

> **状态**: `当前有效`
> **角色**: `专项文档区目录入口`
> **范围**: `docs/PROPOSALS/` 当前树

## 1. 目录职责

1. `docs/PROPOSALS/` 是当前共享仓库中的**专项文档区**。
2. 本目录只承载三类当前有效文档：
   - 项目落地专项文档
   - 仓库治理专项文档
   - 产品实现层的实现契约 / 设计记录 / ADR
3. 本目录**不再承载**第一层正式产品子规范。
4. 本目录**不再保留**历史 draft 的 current tree 副本；历史追溯统一交给 git history。

## 2. 当前目录清单

### 第三层：项目落地专项

1. [WORKSPACE_PROFILE_V1.md](./WORKSPACE_PROFILE_V1.md)

### 第四层：仓库治理专项

1. [REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md](./REPO_WORKFLOW_AND_GOVERNANCE_BOUNDARY_V1.md)

### 第二层：产品实现专项契约 / 设计记录

1. [UNIX_RETRIEVAL_CONTRACT.md](./UNIX_RETRIEVAL_CONTRACT.md)
2. [V6.3_extraction_pipeline_design.md](./V6.3_extraction_pipeline_design.md)
3. [V6.3_CAUSAL_LINKER_DESIGN.md](./V6.3_CAUSAL_LINKER_DESIGN.md)

## 3. 明确不应进入本目录的内容

1. 第一层正式产品定义文档：
   - 产品架构
   - 存储架构
   - 核心对象模型
   - 证据政策与因果分级
2. 仅用于历史追溯的 draft、草案、废弃设计稿。
3. 本地讨论稿、临时控制文件、会话 handoff、任务实例和其他第五层材料。

## 4. 新增文档准入规则

1. 新文档进入本目录前，必须先回答它属于哪一类：
   - 项目落地专项
   - 仓库治理专项
   - 实现契约 / 设计记录 / ADR
2. 若文档实际属于第一层正式产品定义，应直接进入 `docs/` 顶层，而不是进入本目录。
3. 若文档仅为历史记录或阶段草稿，不应保留在 current tree；默认交给 git history。
4. 新文档必须在开头明确至少三项元数据：
   - `状态`
   - `归属`
   - `类型`
5. 若某份实现文档中的局部原则已经被证明属于长期产品语义，应将该原则抽升到第一层正式文档；原实现文档继续保留其第二层实现细节，不整体升格。

## 5. 命名与维护规则

1. 本目录中的文件名允许保留历史命名习惯，但目录角色判断**不依赖文件名本身**，而依赖正文元数据与 [ARCHITECTURE_INDEX.md](../ARCHITECTURE_INDEX.md) 的归层说明。
2. 现存文件若继续保留 `_V1`、`V6.3`、`CONTRACT`、`DESIGN` 等命名，应在正文头部明确它到底是：
   - 当前有效专项文档
   - 当前有效实现设计记录
   - 当前有效实现契约
3. 后续若某份专项文档升格为正式产品定义，应迁移到 `docs/` 顶层，并同步更新索引与引用链。

## 6. 与正式入口的关系

1. 第一层正式产品定义入口见 [ARCHITECTURE_INDEX.md](../ARCHITECTURE_INDEX.md)。
2. 本目录是共享仓专项文档区，不是第二套正式产品真理源。
3. 当本目录文档与第一层正式产品定义冲突时，应优先服从第一层正式文档。
4. 即使某份文档标题含有 `Design`、`Contract`、`ADR`、`Proposal`，也必须按内容归层，而不能按体裁直接判层。
