# Codex CLI 多 Agent 作战手册

## 1. 文档定位

1. 本文定义的是当前仓库中基于 `Codex CLI + git worktree + Task Packet` 的最小多 Agent 协作方式。
2. 本文不是产品架构文档，不定义产品语义。
3. 本文不是自动编排实现文档；当前仓库尚未提供一条统一的 `autopilot` 入口。

## 2. 当前仓库的正式控制面

1. Task Packet 模板：
   - `docs/coordination/task_packet.template.md`
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

1. 司令官先用 `dimc scheduler intake <task_id> --title ... --goal ...` 物化本地任务卡。
   - 这类任务卡会进入 `scheduler plan/status` 的本地调度视图。
   - intake 会按任务文本自动补齐最小骨架，并推断 `task_class`、`cli_hint` 与建议相关文件。
2. 如果只有高层目标，没有稳定的 `task_id` 和标题，直接使用 `dimc scheduler kickoff --goal ...`。
   - kickoff 会自动生成 `task_id`、标题和任务卡，并立即进入 `scheduler run`。
3. `scheduler run <task_id> --yes` 会分配分支、worktree、Task Packet 与 session bundle。
4. 执行工位使用 `dimc scheduler codex-run <task_id>`，基于已有 session bundle 调用 `codex exec`。
5. `scheduler codex-run` 只做执行桥接，不替代 Codex App 的 swarm/subagent 调度。
6. 执行工位只按 Task Packet 改动白名单文件。
7. 执行工位完成后执行 `dimc scheduler complete <task_id>`，生成 `[PR_READY]` 并回写运行时状态。
8. `dimc scheduler summary <task_id>` 汇总 runtime、任务卡、证据和收口资格。
9. 对低风险任务，执行 `dimc scheduler closeout <task_id> --yes` 做本地 `ff-only` 收口。
10. 非低风险任务仍由司令官与精炼官人工裁决。
11. 产品线任务收口后，司令官必须同步第四层共享治理文档，至少复核并更新：
   - `docs/STATUS.md`
   - `docs/dev/BACKLOG.md`
   - 对应 roadmap / 执行计划文档

## 7. 当前仓库里的最小命令约定

1. 根目录 CLI 会话
   - 用于司令官或精炼官。
2. worktree CLI 会话
   - 用于执行工位。
3. 调度器如果自动物化任务，会把 worktree 建到 `/tmp/dimc-worktrees/`，并把任务包写到 `tmp/coordination/task_packets/`。

## 8. 当前边界

1. 当前仓库已有 Task Packet 模板、运行时任务包目录、任务看板和 worktree 物化能力。
2. 当前仓库现在已有第一档和第二档入口：
   - `scheduler intake/run/complete`
   - `scheduler kickoff`
3. 当前仓库现在也有执行桥接入口：
   - `scheduler codex-run`
4. 当前仓库也已有第三档的最小收口入口：
   - `scheduler summary`
   - `scheduler closeout`
5. 这些入口仍然是本地控制层能力，不会自动生成 Issue，也不会自动做多任务拆解。
6. `scheduler codex-run` 的定位是“项目控制层到 Codex CLI 的桥接”，不是通用多 Agent 编排器。
7. 因此当前阶段的最小可信做法是：
   - 用正式模板和运行时目录约束人工编排；
   - 用 `scheduler intake/run/complete`、`scheduler kickoff`、`scheduler codex-run`、`scheduler summary/closeout` 打通分档自动化闭环；
   - 不假装已经有完整 autopilot。
