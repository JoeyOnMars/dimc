# ⚡️ [DIRECTIVE] Task 007‑01: 铸造 Causal Core「时空硬锁」(双轨制第一阶段)

**执行背景**  
DIMCAUSE 数据底座正式确立「防线领域上浮」的企业级隔离架构：  
- **Storage 哑存储层 (`GraphStore`)**：彻底剥离业务规则，仅负责基于白名单的结构边写入（如 `calls`）与内部私有落库。
- **Domain 领域护城河 (`CausalEngine`)**：独占因果关系知识库，全权负责因果边写入时的严格时空锁与全局广播豁免。

**执行目标**  
在本任务中，你需要将因果防线彻底从数据库提取到业务领域层。建立唯一的 `CausalEngine.link_causal` 领域入口，并将底层的 `GraphStore` 改造为只允许结构边通行、私有化其余写库能力的纯净沙盒。

---

## 0. 前置环境检查 (Pre-flight Check)
> **强制纪律**: 任何代码落地前，M 专家必须确认以下物理环境，并在第一次回复中向用户汇报。

1. **虚拟环境确认**: 运行 `which python`，确保指向 `/Users/mini/projects/GithubRepos/dimc/.venv/bin/python`。
2. **正确分支切入**: 运行 `git status` 检查当前分支，如果不为 `feat/task-007-01-v2`，必须**强制执行切换**:
   ```bash
   git fetch origin
   git checkout feat/task-007-01-v2
   ```

---

## 1. 架构隔离与双入口剥离 (Enterprise Scheme A & Roadmap B)

为彻底阻断“幽灵路由”与“类型签名断裂”，本任务强制执行以下**方案 A（本地/私有云同进程隔离）**的重构：

1. **改造底座 `GraphStore`（白名单结构层）**  
   - 废除原有的公共接口 `add_relation`，对外**唯一暴露**用于写结构边的接口（注意必须包含 `metadata` 参数以承接原始行为）：
   ```python
   def add_structural_relation(
       self,
       source: str,
       target: str,
       relation: str,
       weight: float = 1.0,
       metadata: Optional[Dict] = None,
   ) -> None:
   ```
   - 在此接口内部写死常量校验：`STRUCTURAL_RELATIONS = {"calls", "imports", "contains", "depends_on"}`。若传入 `relation` 不在白名单内，立刻抛出 `IllegalRelationError`。
   - 保留一个退化为**纯私有的落库方法** `_internal_add_relation(...)`，该方法只做 SQL 操作不含业务校验。

2. **确立正式因果边领域防线 (`CausalEngine`)**  
   - 在推理域（如 `src/dimcause/reasoning/causal_engine.py`）新建领域服务：`CausalEngine`。  
   - **强制依赖注入 (For Scheme B)**: `CausalEngine.__init__(self, graph_store: GraphStore)` 必须通过参数显式注入底层实例，**绝对禁止**在内部硬编码 `GraphStore()`。这将保证未来方案 B 的无痛替换。
   - 此处掌握 `CAUSAL_RELATIONS_SET` 的知识，暴露唯一业务入口：`link_causal(source: Event, target: Event, relation: str, ...) -> dict`。
   - **强制可序列化 (For Scheme B)**: `Event` 对象的所有字段、`link_causal` 的所有出入参，必须 100% 可被 JSON/Protobuf 序列化。绝对禁止在逻辑中依赖“仅同进程有效”的内存引用或文件句柄。
   - 这里负责全权拥有并提取 `Event` 信息的权力。只有当彻底通过时空双锁验证后，才允许在此调用特权通道 `self.graph_store._internal_add_relation(...)` 完成物理落盘。

3. **全局调用收尾**  
   - 所有原先调 `add_relation("calls")` 或其他非因果类型的地方，强制全部改调 `add_structural_relation`。
   - 凡是原本写入因果边缘的代码，强制改调 `CausalEngine.link_causal`。无法传 `Event` 对象的旧口子标上 `TODO(task-007-02)` 并注释抛错拦截。

### 【架构远期展望】多智能体 (Multi-Agent) 协同部署方案 B (Not In Scope)
当系统未来演进为多 Agent 并发写入时，“方案 A”必然向“方案 B”演进，请知悉以避免当前过度设计：
- `CausalEngine` 将升级为独立的网络微服务，其他模块通过 IPC/gRPC 与之通信，无法获取数据库句柄。
- `GraphStore` 将与之实现物理网络隔离，写库接口对且仅对 `CausalEngine` 进程开放。
*(注：本前瞻性架构仅作为技术路线图记录，严禁在 Task 007-01 中去实现此分离，严格把守方案 A 即为完成任务)*

---

## 2. 防线 A：时间锥拦截 (Temporal Block)

在 `CausalEngine.link_causal` 中实施：
- 统一使用 `event.occurred_at: float` (Unix 秒)。  
- 硬编码 `JITTER_SECONDS = 1.0`。  
- 若 `target.occurred_at + JITTER_SECONDS < source.occurred_at`，直接抛出 `CausalTimeReversedError`。  
- **约束**：旧数据如果缺时间，必须粗暴拒绝。

---

## 3. 防线 B：拓扑孤岛与广播豁免 (Topological & Global Broadcast)

在 `CausalEngine.link_causal` 中实施：
- 实现 `get_topological_anchors(event) -> set[str]`，至少必须包含 `session_id`, `service_name`, `module_path`。**绝对禁止**使用 `event.id` 作为无脑兜底。
- **默认拦截**：计算源与目标的锚点交集，若 `intersection` 为空，抛出 `TopologicalIsolationError`。
- **广播豁免 (Global Override)**：如果 `source` 是明确的全局灾难级事件（如 `metadata` 中带有合法的 `is_global=True` 且属于确切的全局范围异常），则允许其与局部 session 建立连接。

---

## 4. 授权修改清单 (Authorized Scope - Rule 31 Compliance)

> **警告**: 依据 `dimcause-ai-system.md`，执行修改前必须拥有逐一列出的白名单。M 专家在执行本契约时，**仅且仅被授权修改以下具体对象**：

- `src/dimcause/storage/graph_store.py`: `GraphStore.add_structural_relation`, `GraphStore._internal_add_relation`
- `src/dimcause/storage/graph_store.py`: `GraphStore.add_relation` (彻底废除并移除)
- `src/dimcause/core/protocols.py`: `IGraphStore.add_relation` (更新签名为 `add_structural_relation`)
- `src/dimcause/reasoning/causal_engine.py`: 新增 `CausalEngine` 类及 `link_causal` 方法
- `src/dimcause/core/__init__.py`: 导出新增异常 (`CausalCoreError` 体系)
- `src/dimcause/storage/__init__.py`: 导出新增异常 (`CausalCoreError` 体系)
- `src/dimcause/extractors/extraction_pipeline.py`: `ExtractionPipeline._extract_causal_relations` (旧的 `add_relation` 调用点转移)
- `src/dimcause/extractors/ast_analyzer.py`: `build_code_dependency_graph` (旧的结构边调用点转移)
- `tests/storage/test_causal_core.py`: 本任务所需的全部新增与重构测试（必须有 `[TEST_FIX_REASON]` 声明）
- `tests/test_graph_store_sqlite.py`: 修复 `add_relation` 废除报错（必须有 `[TEST_FIX_REASON]` 声明）
- `tests/test_v51_components.py`: 修复 `add_relation` 废除报错（必须有 `[TEST_FIX_REASON]` 声明）
- `tests/test_graph_store.py`: 修复 `add_relation` 废除报错（必须有 `[TEST_FIX_REASON]` 声明）
- `tests/storage/test_graph_performance.py`: 修复 `add_relation` 废除报错（必须有 `[TEST_FIX_REASON]` 声明）
- `tests/test_export_jsonld.py`: 修复 `add_relation` 废除报错（必须有 `[TEST_FIX_REASON]` 声明）

不在上述清单中的任何核心文件与对象，**绝对禁止**修改。

---

## 5. 测试验收要求 (Zero Tolerance)

更新以下 `pytest` 用例，验证架构隔离方案 A 能够确实生效：

1. **底座越权测试**：尝试调用 `GraphStore.add_structural_relation(..., "causes")`，断言被底座内建白名单干掉，抛出 `IllegalRelationError`。
2. **结构边绿灯**：调用 `GraphStore.add_structural_relation(..., "calls")`，断言底座白名单放行，正常写库。
3. **负向测试 1 (时间倒流)**：通过 `CausalEngine.link_causal`，target 时间早于 source 超出 Jitter，断言拦截。
4. **负向测试 2 (拓扑孤岛)**：通过 `CausalEngine.link_causal`，无交集且非 Global 事件，断言拦截。
5. **豁免正向测试 (Global Broadcast)**：通过 `CausalEngine.link_causal`，无交集但 source 带有合法的 global 设定，断言写入成功。
6. **执行命令验证**：修改完成后，必须运行 `pytest tests/storage/` 以及 `dimc audit` 确保全局无回归 (端到端验收)。
7. **对齐证明 (Alignment Proof)**：在提交前，必须生成一份 `[ALIGNMENT_PROOF]` 清单并放进最终汇报中，证明更改后的代码严格对应 `DEV_ONTOLOGY.md` 中的设计（应对 Rule 5.3）。

---

## 6. Git 操作纪律

- 必须在统一指定的新分支 `feat/task-007-01-v2` 上进行开发。  
- **严禁使用 `git rebase`** 篡改历史。
- **强制原子化**：遵循 One Task One Branch 及 Commit Early, Commit Often 准则。每次 commit 后必须立即 `git push origin HEAD`。
- **严禁合并**：M 专家**无权**执行 `git checkout main && git merge ...`。开发与测试全部完成后，必须输出 `[PR_READY]` 标记并停止，等待 G 专家审计和合并。

---

## 7. 授权豁免与结束准则 (Exceptions & Completion)

- **权限覆盖 (Rule 31)**：本契约显式覆盖 `dimcause-ai-system.md` 中定义的「默认扮演审计员，只读不自动落地」模式，赋予修改以上业务与存储模块的最高权限。
- **删除豁免 (Rule 23)**：授权废除、替换旧接口 `add_relation`，显式在此任务内豁免 `Rule 5.2` (盲目删除零容忍) 中的绝对禁令。但修改前仍需 `grep` 全局引用以确保被正确迁移。
- **进度登记 (Rule 19)**：在向用户报告任务完成前，必须确信测试 100% 通过且 **同步更新 `docs/STATUS.md`** 中的相关层级状态。
- **一致性交付 (Rule 5.3)**：交付时必须显式提供 `[ALIGNMENT_PROOF]` 表格，证明新加的类和接口全量映射到了架构文档。
- **交接流程**：所有工作完成后，向用户输出 `[PR_READY] 当前分支 feat/task-007-01-v2 的开发与测试已通过，请求 G 专家审查并合并。` 然后停止，等待 G 专家进场审计。
