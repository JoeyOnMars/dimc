# Task Packet Template

> 用途：并行多 Agent 开发时的最小任务包模板
> 适用模式：`Mode B: Parallel Multi-Agent`
> 目标：把任务边界、测试边界、交付边界写成可执行约束，而不是口头约定

---

## 1. Task Identity

- `task_id`:
- `title`:
- `owner`:
- `priority`:
- `status`:
- `protected_doc_override`: false
- `user_approval_note`:
- `design_change_reason`:

## 2. Goal

- 目标：
- 完成后应得到什么：

## 3. Out Of Scope

- 明确不做什么：
- 禁止顺手修什么：

## 4. Allowed Files

只允许修改以下文件或目录：

```text
- path/to/file_a
- path/to/file_b
- path/to/dir_c/
```

## 5. Forbidden Files

本任务明确禁止触碰：

```text
- docs/PROJECT_ARCHITECTURE.md
- docs/STORAGE_ARCHITECTURE.md
- docs/V6.0/DEV_ONTOLOGY.md
- path/to/forbidden_a
- path/to/forbidden_b
```

## 6. Protected Design Doc Override

默认必须保持：

```text
- `protected_doc_override`: false
```

只有在 **User 当前回合明确批准** 的 RFC / 设计变更任务中，才允许改为 `true`，并同时补齐：

- `user_approval_note`:
- `design_change_reason`:

其中：

- `user_approval_note` 必须写明当前回合的批准语义，而不是留空或写占位词。
- `design_change_reason` 必须说明为什么本次设计文档变更是必要的，以及它对应的设计目标或 RFC。

若 `protected_doc_override` 为 `false`，则受保护设计文档必须继续留在 Forbidden Files 中。

## 7. Required Checks

本任务在 `[PR_READY]` 前必须运行：

```bash
# 受影响测试
pytest path/to/test_file.py -v

# 如需要
scripts/check.zsh
```

## 8. Delivery Contract

交付时必须包含：

1. 代码改动
2. 测试结果摘要
3. 修改文件列表
4. 白名单合规结论（`pass` / `fail`）
5. 受保护设计文档合规结论（`pass` / `fail`）
6. 剩余风险或未覆盖项

## 9. Branch / Worktree

- branch:
- worktree:
- session:

## 10. Risks

- 风险 1：
- 风险 2：

## 11. Dependency Notes

- 前置任务：
- 可并行任务：
- 冲突任务：

## 12. Internal Agent Context Transfer

如需换 Agent / 换会话，补充：

- 已完成：
- 未完成：
- 当前卡点：
- 下一步建议：

## 13. Completion Signal

本任务唯一合法完成信号：

```text
[PR_READY]
branch: <branch>
task: <task_id>
checks:
- <command 1>
- <command 2>
files:
- <changed file 1>
- <changed file 2>
whitelist: pass
protected_docs: pass
risks:
- <remaining risk>
```
