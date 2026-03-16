# Codex CLI 多 Agent 作战手册

## 1. 文档定位

1. 本文定义的是当前仓库中基于 `Codex CLI + git worktree + Task Packet` 的最小多 Agent 协作方式。
2. 本文不是产品架构文档，不定义产品语义。
3. 本文不是自动编排实现文档；当前仓库尚未提供一条统一的 `autopilot` 入口。

## 2. 当前仓库的正式控制面

1. Task Packet 模板：
   - `docs/PROPOSALS/TASK_PACKET_TEMPLATE.md`
2. 运行时任务包目录：
   - `tmp/coordination/task_packets/`
3. 任务看板：
   - `tmp/coordination/task_board.md`
4. 调度器运行时状态：
   - `.agent/scheduler_state.json`
5. worktree 默认池：
   - `/tmp/dimc-worktrees/`

## 3. 角色

1. 司令官
   - 负责拆解、定边界、下发 Task Packet、审查结果。
   - 默认驻留在仓库根目录。
2. 执行工位
   - 负责实现单个原子任务。
   - 每个任务使用一个独立 `branch + worktree + CLI 会话`。
3. 精炼官
   - 负责独立复核、关键验证、`ff-only` 合流与清理。
   - 不改功能代码。

## 4. 核心纪律

1. 一个原子任务对应一个 Task Packet。
2. 一个原子任务对应一个分支。
3. 一个分支对应一个 worktree。
4. 一个 worktree 对应一个 CLI 会话。
5. 不在共享工作区里并行跑多个实现任务。

## 5. 模式

1. `W`
   - 单任务、单 worktree。
   - 当前默认模式。
2. `M`
   - 多任务并行，每个任务各自独立 worktree。
   - 只在任务边界明确、白名单明确、验证明确时开启。

## 6. 最小工作流

1. 司令官先生成或填写 Task Packet。
2. 为任务分配分支与 worktree。
3. 执行工位只按 Task Packet 改动白名单文件。
4. 执行工位完成后输出 `[PR_READY]`。
5. 司令官审查是否允许进入收口。
6. 精炼官独立复核并做 `ff-only` 合流。

## 7. 当前仓库里的最小命令约定

1. 根目录 CLI 会话
   - 用于司令官或精炼官。
2. worktree CLI 会话
   - 用于执行工位。
3. 调度器如果自动物化任务，会把 worktree 建到 `/tmp/dimc-worktrees/`，并把任务包写到 `tmp/coordination/task_packets/`。

## 8. 当前边界

1. 当前仓库已有 Task Packet 模板、运行时任务包目录、任务看板和 worktree 物化能力。
2. 当前仓库还没有一个统一的自动入口，把“高层目标 -> Issue -> Task Packet -> 执行 -> 收口”全部串起来。
3. 因此当前阶段的最小可信做法是：
   - 用正式模板和运行时目录约束人工编排；
   - 不假装已经有完整 autopilot。
