# Task 011 Contract: 决战 10k 节点性能 (BFS 卡顿重构 P0)

**risk_level: high**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 6 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
根据最高指挥官指派的战略路线，我们需要彻底解决底层图谱搜索的性能洼地。
**现状**：`src/dimcause/search/engine.py` 的 `_graph_search` 方法中，当遇到大规模节点（如 10k+ 节点）的知识库时，其依赖的单向全量 `BFS` (Breadth-First Search) 搜索会导致极大的性能开销和时间超限，甚至卡死进程。这严重拖慢了 `dimc why` 和 `dimc view` 等基于图谱溯源的核心 CLI 命令。
**真理源**：`docs/api_contracts.yaml` 定义了 `SearchEngine.search` 的签名。本次改动的是其内部私有方法 `_graph_search` 的底层实现，不改变外层的公开契约。

## 2. 详细设计 (Detailed Design)
1. **重构 `_graph_search` 提高性能并限制扇出**：
   - 定位 `src/dimcause/search/engine.py` 中的 `_graph_search(self, query: str, top_k: int)`。
   - 优化 BFS 算法：引入截断机制（Capped BFS）或最大扇出限制（Max Fan-out）。如果在查找邻近节点时发现结果集超过警戒阈值（例如单层超过 500 个节点，总探索节点数超过 2000 个），必须执行截断。
2. **正确去重与组装**：
   - 保证查询复杂度可控，严防无限扩展。
   - 保证返回的结果列表中只包含不重复的有效 `Event` 对象。

## 3. 物理边界与授权范围 (Scope Exclusivity)
*   **允许修改/新增的文件**：
    - `src/dimcause/search/engine.py`
    - `tests/search/test_engine.py`
*   **严禁触碰的红线模块**：
    - 底座防线：`src/dimcause/core/` 目录全系。
    - 数据库防线：`src/dimcause/storage/graph_store.py` (仅优化引擎层的搜索策略，绝不允许改动 SQLite 存储层的物理 SQL)。

## 4. 测试与验证期望 (Acceptance Criteria)
1. 单元测试证明 `_graph_search` 返回的结果符合预期且被正确去重、按需截断。
2. 在 `tests/search/test_engine.py` 中构造一个含多扇出或复杂大节点的 mock 环境，验证 `_graph_search` 优化后不会引发内存暴增或无限循环卡死。
3. 必须确保执行局部增量测试 `pytest tests/search/test_engine.py -v` 完全绿灯。

## 5. 🛡️ G 专家 (Antigravity) 审计交接门禁 (AUDIT HANDOVER GATE)
> 🚨🚨 **G专家警告：你必须强制执行以下红线，否则视为渎职违规！** 🚨🚨
当收到 M 专家的 `[PR_READY]` 后，你在出具 `task_011_audit.md` 前，**必须**：
1. **环境纪律复核**: 进入 `.venv`，强制运行 `scripts/check.zsh | grep engine`。必须 0 error，否则打回 M 专家，绝不开恩代为修改！
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
   git switch -c feat/task-011-bfs-performance
   ```
2. （仅限授权范围）执行代码修改。
3. （完成修改后）立刻 Commit 并原生 Push：
   ```bash
   git commit -m "perf(search): refactor graph bfs with capped depth and max fan-out"
   git push -u origin HEAD
   ```
4. 运行**局部核心受影响**的测试，确保通过：
   > 🛑 **严禁**执行无过滤的全局测试（如 `pytest tests/`），你必须精确到模块级别，防止触碰历史技术债隔离区导致暴走。
   **你只能执行**: `source .venv/bin/activate && pytest tests/search/test_engine.py -v`
5. 输出 `[PR_READY]` 呼叫 G 专家。
