# Coordination Templates

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
4. Task Packet 模板位于 `docs/PROPOSALS/TASK_PACKET_TEMPLATE.md`
5. `codex_cli_multi_agent_playbook.md`：当前仓库的 `Codex CLI + worktree + Task Packet` 最小作战手册
