# Phase 2 审计检查清单 (Audit Checklist)

这是 Superagent (User + Architect) 在合并任何 Feature Branch 之前必须逐项核对的 **"质量门禁" (Quality Gate)**。

## 1. 设计合规性 (Design Compliance) —— The Conscience
> 依据: `docs/V6.0/DEV_ONTOLOGY.md`

- [ ] **Ontology 映射**: 所有新增的类/关系是否在 `src/dimcause/core/ontology.yaml` 中不仅有定义，而且用法一致？
    - *检查点*: 是否有硬编码的字符串代替了 `Ontology.classes.Decision`？
- [ ] **物理路由门禁**: 是否严格执行了 Structural vs Causal 边的隔离写入？
    - *检查点*: 严禁任何模块直接调用图库的 `add_relation`（该原始方法已被物理废弃/私有化）。
    - *核实*: **因果边**必须且只能走 `CausalEngine.link_causal` 接受时空硬锁（`CausalTimeReversedError` 等）的洗礼；**结构边**必须走 `GraphStore.add_structural_relation`。
- [ ] **无暗算 (No Hidden Logic)**: 是否有未在设计文档中提及的"隐形逻辑"？

## 2. 自动化测试 (Automated Tests) —— The Safety Net
> 依据: `tests/`

- [ ] **单元测试通过**: `pytest tests/unit/reasoning/` 全绿。
- [ ] **Mock 边界**: Mock 是否仅限于外部 I/O (如 DeepSeek, 文件系统)？核心逻辑是否经过了真实测试？
    - *拒绝*: Mock 了本该测试的 `HybridEngine` 核心算法。
- [ ] **性能基线**: 1000 个事件的处理时间是否在 10s 以内 (MPS开启)？

## 3. 视觉验证 (Visual Verification) —— The Proof
> 依据: `dimc graph show`

- [ ] **CLI 演示**: 必须提供命令运行的 **截图** 或 **日志输出**。
    - *要求*: 不能只说 "It works"，必须展示它跑在新数据上的样子。
- [ ] **错误处理**: 当输入非法数据时，报错信息是否是“人话”而非堆栈跟踪？

## 4. 代码卫生 (Code Hygiene) —— The Craft
> 依据: `ruff`, `mypy`

- [ ] **类型提示**: 所有函数签名都有 Type Hints。
- [ ] **文档字符串**: 核心类都有 Docstring 说明 "Why" 而不仅是 "What"。
- [ ] **无死代码**: 没有注释掉的旧代码块。
