# Task 016 Contract: L4 解释器因果引擎接入加深与提纯 (P0 Architecture)

**risk_level: high**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
当前系统中存续 P0 级底层缺陷（BACKLOG P0-4）：我们在 Task 007-01 中建构了 `CausalEngine` 真实因果图谱（`caused_by`, `triggers` 等结构语义），虽然目前 `dimc why` 调用的 `core/history.py` 内部已经启用了 `use_causal_chain=True`，但其实际“因果追溯”实现存在严重瑕疵：
1. **纯度不足**：`_get_causal_related_events` 盲目使用 `GraphStore.find_related` 做无脑全向 BFS，混淆了结构边和因果边，没有限定在因果关系语义（`CAUSAL_RELATIONS_SET`）内。
2. **架构漏洞 (P0 坠毁风险)**：
    - `history.py` 目前的 Fallback 创建了一个脱离生命周期且默认指向 `~/.dimcause/index.db` 的 `GraphStore`。在测试环境下这会突破沙盒污染物理盘面。
    - `history.py` 中的 `_get_causal_related_events` SQL 语句包含了 `content LIKE ?` 参数，但实际上由于架构变迁，`events` 表中的 `content` 字段早就不存在了，该代码一旦触发必报 `no such column`。

本任务目标是彻底重写这一链路，在图谱层（`GraphStore`）补齐专属的因果回溯 API，并在业务层（`history.py`）提纯回溯逻辑并铲除遗留的毒性 SQL 查询，真正发挥 `CausalEngine` 积攒的高质量图谱因果数据。

## 2. 详细设计 (Detailed Design)
1. **GraphStore: 拓展只读单向因果回溯 API**
   - 在 `src/dimcause/storage/graph_store.py` 新增方法 `get_causal_chain(self, target_id: str, depth: int = 3) -> List[str]`。
   - 实现逻辑：从 `target_id` 开始，**只**沿着关系包含在 `CAUSAL_RELATIONS_SET` 内的入边（predecessors）做带深度的回溯。
   - ⚠️ **返回顺序与边界约束 (P2/Flaky 防线)**：必须采用 **BFS（广度优先层序）** 遍历返回；必须在结果列表中**排除自身 (`target_id` 不得出现)**；**必须在查询 SQLite 获取前置节点时强制追加稳定排序键（必须是 `ORDER BY created_at DESC, source ASC, relation ASC`）**，因为没有 `ORDER BY` 的 SQL 返回顺序完全取决于物理页的任意分配，这会导致同层节点的队列入队与出列顺序呈随机态，产生致命的 Flaky Tests；同层级内的同级节点若产生去重冲突，保留首次出现即可。
   - ⚠️ **返回值强制约束 (P1 Fix)**：为了让下游 `history.py` 能够与 `events` 表完美聚合，该 API **必须收集并返回引发当前事件的 `event_id` 集合**。严禁下沉猜测节点内部属性，由于是沿入边回溯前置节点，**只能以 `graph_edges` 表的 `source` 字段字面量作为唯一候选提取 ID**，并在下游跟 `events.id` 直接进行精确的主键 `IN` 匹配，绝不允许任何前缀推断或 `LIKE` 模糊查询！
   - ⚠️ **内存图踩踏防线 (P0 Fix)**：目前的内存图 `self._graph` 是 `nx.DiGraph`（不支持多重边），同节点对的因果边极易被结构边（如 `calls`）物理覆盖。因此，**严禁** `get_causal_chain` 依赖内存图遍历，**必须强制**通过 `self._get_conn()` 直接对 SQLite `graph_edges` 表使用 `relation IN (...)` 进行精准 SQL 回溯查询！
   - ⚠️ **循环依赖规避**：必须在 `get_causal_chain` 方法内部进行延迟导入（`from dimcause.reasoning.causal_engine import CAUSAL_RELATIONS_SET`），**严禁**在文件顶部全局导入。
2. **History: 重构提取逻辑、降级策略与 SQL 修复**
   - 修改 `src/dimcause/core/history.py` 中的 `_get_causal_related_events`。
   - 替换粗糙的 `find_related` 为新的 `get_causal_chain` 调用。⚠️ **因果种子提取法则 (P1 Fix)**：因果图谱的入边回溯必须针对“事件节点”。必须先通过现有的**关系型访问层（如 `EventIndex` SQL 查询，绝对禁止使用基于 `nx.DiGraph` 的 `graph_store.get_file_history`，以防种子被同源的其他结构边覆盖丢失）**将输入文件解析为一批关联的历史事件（种子事件），然后对这批种子事件集合的 `id` 逐一执行 `get_causal_chain`。**绝对禁止直接用 `file_path` 也就是纯字符串路径当作 ID 丢给因果链查图，那会导致逻辑空转并返回空集。**
   - ⚠️ **强制同库降级法则 (P0 Fix)**: `EventIndex` 本身并没有维护全局的 `_graph_store` 属性引用。你只能通过 `from dimcause.storage.graph_store import create_graph_store; graph_store = create_graph_store(path=str(event_index.db_path))` 安全生成匹配现有库的游离接口。**绝对禁止裸调用参数留空的** `create_graph_store()`。
   - ⚠️ **铲除幽灵字段 SQL (P0 Fix)**: `events` 表中没有 `content` 列。现有的 `query_sql` (`summary LIKE ? OR content LIKE ?`) 必须被改成仅合法访问现有列的形式（如 `json_cache LIKE ? OR summary LIKE ?`）。**注意语义边界**：该 `LIKE` 查询仅可作为非因果路径或非主键匹配的极弱 Fallback。对于 `get_causal_chain` 传递上来的结果，必须强走主键 `IN` 查询，严禁任何形式的模糊匹配扩散！

## 3. 物理边界与授权范围 (Scope Exclusivity)
你**仅被授权**修改下列文件：
- [MODIFY] `src/dimcause/storage/graph_store.py`
- [MODIFY] `src/dimcause/core/history.py`
- [NEW] `tests/test_history_causal.py` (新建该文件用于专门测试 `history.py` 因果链抽取逻辑)
- [NEW] `tests/test_graph_store_causal.py` (补齐因果图谱本体遍历 API `get_causal_chain` 的专项白盒测试)
- ⚠️ **红线禁区**: 绝对禁止触碰 `src/dimcause/reasoning/causal_engine.py` 的写操作防线，绝不修改 `cli.py`。

## 4. 测试与验证期望 (Acceptance Criteria)
需确保不破坏已有功能基础之上实现新特性。你需要：
1. **测试用例 1: `test_graph_store_causal.py`** 必须独立测试 `get_causal_chain`。
   - **拦截校验（防 DiGraph 物理覆盖吞没）**：必须显式构建同一对节点 (A, B) 同时存在结构边（如 `calls`）和因果边（`caused_by`）的满载测试场景。断言该方法能超越内存图受限的死角，通过底层 SQL 稳定命中真实的极稀疏因果边，绝对免疫结构边的覆盖干扰。
2. **测试用例 2: `test_history_causal.py`** 必须覆盖 `get_file_history(use_causal_chain=True)`。
   - ⚠️ **落盘隔离法则 (P0 防护靶心)**：由于 GraphStore/EventIndex 每次建表都新开连接，**严禁使用**:memory: 初始化。必须使用 `tmp_path` 夹具生成物理沙盒临时 DB 全路径，才能安全度过并发测试连通。
   - **拦截校验 1（防字段越界）**：该真实数据库用例必须能流畅跑通 `_get_causal_related_events` 查询，而不报 `No such column: content` 错误。
   - **拦截校验 2（防库分裂）**：测试必须证明内部生成的 `graph_store` 连到了测试配置的 `db_path`，而不是跑到 `~/.dimcause` 生根污染宿主。
   - **拦截校验 3（防种子物理覆盖）**：显式注入一个文件事件，并同时给它绑上 `modifies` 与 `calls` 等其它边，断言种子绝不会被 `DiGraph` 冲刷为 0 且能打通因果调用链。
3. 执行以下唯一合法命令证明测试通过（必须同时覆盖底座、门面、和回归）：
`source .venv/bin/activate && pytest tests/test_core_history.py tests/test_history_causal.py tests/test_graph_store_causal.py -v`

## 5. 🛡️ G 专家 (Antigravity) 审计交接门禁 (AUDIT HANDOVER GATE)
> 🚨🚨 **G专家警告：你必须强制执行以下红线，否则视为渎职违规！** 🚨🚨
当收到 M 专家的 `[PR_READY]` 后，你在出具 `task_xxx_audit.md` 前，**必须**：
1. **防污染安全纪律**: 进入 `.venv`，强制运行**只读审计命令**（严禁运行含有写副作用的 `scripts/check.zsh` 本体）：`ruff check src/`、`ruff format --check src/` 以及上文要求的局部 `pytest`。必须 0 error，否则打回 M 专家，绝不开恩代为修改！保卫只读防线！
2. **加载当前仓库治理门禁**: 你必须去读取并逐项核对当前有效的仓库治理规则与交付门禁，至少包括：
   - `.agent/rules/agent-git-workflow.md`
   - `docs/coordination/codex_cli_multi_agent_playbook.md`
   - 当前任务对应的 `docs/STATUS.md`、`docs/dev/BACKLOG.md` 与 roadmap / 执行计划文档同步要求
3. **移交权柄**: 最后向 User 汇报结果，等待 User 盖章 Checklist 后，由 User 或 User 明确授权方可 `git merge`。

## 6. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)
> 🚨🚨 **M专家警告：以下为物理隔离铁律！** 🚨🚨
一旦看到本契约获得 User 盖章的 `Approved/已确认`，你必须**严格按顺序**执行以下起手式，否则视为最高级别违规：

1. **绝对禁止**在 `main` 涂鸦，立刻新开分支：
   ```bash
   git switch main && git pull
   git switch -c feat/task-016-why-causal-chain-pure
   ```
2. （仅限授权范围）执行第一行代码/测试修改。
3. 运行**局部核心受影响**的测试，确保通过：
   > 🛑 **严禁**执行无过滤的全局测试（如 `pytest tests/`），你必须精确到模块级别，防止触碰历史技术债隔离区导致暴走。
   > **本契约唯一合法的测试指令为：**
   > `source .venv/bin/activate && pytest tests/test_core_history.py tests/test_history_causal.py tests/test_graph_store_causal.py -v`
4. （测试完全通过后）立刻 Commit 并原生 Push：
   ```bash
   git commit -m "feat: [简短说明]"
   git push -u origin HEAD
   ```
5. 输出 `[PR_READY]` 呼叫 G 专家。
