# Task 022 - `dimc why` 因果链对齐审计

日期：2026-03-06  
分支：`feat/task-022-why-causal-alignment`

## 结论

`dimc why` 已在代码层接入因果链检索，不再是“完全未接入”的状态。  
当前更准确表述应为：**已接入（有回归测试兜底），但仍存在展示层/策略层优化空间**。

## 物理证据

1. CLI 入口显式开启因果链  
   - `src/dimcause/cli.py:3044`、`src/dimcause/cli.py:3069`  
   - `get_file_history(..., use_causal_chain=True)`

2. 历史查询函数支持并执行因果扩展  
   - `src/dimcause/core/history.py:41` 定义 `use_causal_chain: bool = True`
   - `src/dimcause/core/history.py:68` 根据开关调用 `_get_causal_related_events`
   - `src/dimcause/core/history.py:247` 调用 `graph_store.get_causal_chain(...)`

3. 因果扩展查询策略符合安全约束  
   - `src/dimcause/core/history.py:262-264` 使用主键 `id IN (...)` 精确匹配
   - 未使用 `content LIKE` 模糊扩散

## 新增回归测试

1. `tests/test_cli_history.py::test_why_file_mode_enforces_causal_chain`  
   - 验证 `why` 文件模式调用 `get_file_history` 时始终传 `use_causal_chain=True`

2. `tests/test_cli_history.py::test_why_directory_mode_enforces_causal_chain`  
   - 验证 `why` 目录模式下的每次 history 查询都传 `use_causal_chain=True`

## 本轮验证

- `source .venv/bin/activate && pytest tests/test_cli_history.py tests/test_history_causal.py -q`  
  结果：`6 passed`
- `source .venv/bin/activate && ruff check tests/test_cli_history.py`  
  结果：`All checks passed!`

## 后续建议

1. 在 `STATUS.md` / `BACKLOG.md` 中将 “`dimc why` 未接入因果链” 改为 “已接入，待优化”。  
2. 下一步优化可聚焦：因果事件排序策略、展示层可解释性、与 LLM 分析阶段的权重联动。

