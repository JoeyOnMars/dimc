# 协调模板说明

**状态**：当前有效
**定位**：仓库治理层中的版本化协调模板入口。
**边界**：这里只保留模板、字段约束和最小作战流程，不承载运行时实例。

这组文件定义的是多 Agent 开发流程里的正式协调模板，而不是运行时实例。

目录职责：

1. `docs/coordination/`：版本化模板和字段约束
2. `tmp/coordination/`：当前批次并行开发的本地运行实例

使用方式：

1. 从本目录模板复制出当前批次实例
2. 将实例落在 `tmp/coordination/`
3. 只把稳定模板和字段演进提交到 git

当前模板：

1. `task_board.template.md`
2. `integration_log.template.md`
3. `agent_context_transfer_template.md`
4. Task Packet 模板位于 `docs/coordination/task_packet.template.md`
5. `codex_cli_multi_agent_playbook.md`：当前仓库的 `Codex CLI + worktree + Task Packet` 最小作战手册
6. Task Packet 现在包含 `risk_level`，用于区分低风险自动收口候选与必须人工把关的任务。
7. `context_decay_handoff_protocol.md`：长会话上下文压缩时的固定接力协议（共享层方法，不含本地现场快照）。

最小可执行入口：

1. 第一档：`dimc scheduler intake <task_id> --title ... --goal ...` -> `dimc scheduler run <task_id>` -> `dimc scheduler complete <task_id>`
2. 第二档：`dimc scheduler kickoff --goal ...` 直接把高层目标物化为任务卡并启动执行
3. 执行桥接：`dimc scheduler codex-run <task_id>` 复用现有 session bundle 调用 `codex exec`
4. 第三档：`dimc scheduler summary <task_id>` 汇总收口资格，`dimc scheduler closeout <task_id> --yes` 对低风险任务执行 ff-only 收口
5. `dimc scheduler plan` / `status` 会把这类 standalone 任务卡纳入本地调度视图
6. `scheduler intake` / `kickoff` 会自动生成最小任务骨架，并按任务文本推断默认 `task_class`、`cli_hint` 与建议相关文件

说明：

1. `.agent/agent-tasks/` 属于本地开发控制层，默认不进入共享提交范围
2. `tmp/coordination/` 承载运行时实例，不替代版本化模板
3. `scheduler codex-run` 只负责把任务卡与 `Codex CLI` 接起来，不负责通用 swarm 编排
4. 产品线任务完成并收口后，必须同步第四层共享治理文档；当前仓库最少要检查：
   - `docs/STATUS.md`
   - `docs/dev/BACKLOG.md`
   - 相关 roadmap / 执行计划文档
