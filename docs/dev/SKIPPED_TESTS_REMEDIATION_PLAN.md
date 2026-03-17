# DIMCAUSE 全量 Skipped 测试整改清单

**审计基线**: 2026-03-17  
**审计命令**: `pytest -q -rs`  
**审计结果**: `1103 passed, 30 skipped`

---

## 1. 目的

这份清单只解决一个问题：把当前全量测试中的 `30` 个 skipped 拆成可执行整改项。  
它不负责解释产品架构，也不替代 `BACKLOG`；它是测试债的专项处置文档。

原则：

1. `skipped` 不是“已验证通过”。
2. `skipped` 必须分清：过时测试、手工测试、受保护测试、环境依赖缺失、真正未实现。
3. 不同类型的 skipped，处置动作不同；不能统一用“后面再补”糊过去。

---

## 2. 总体分类

本轮 `30` 个 skipped 分成五类：

1. 过时测试：`3`
2. 手工 / 完整环境测试：`2`
3. 真实数据 / 真实代码库保护性阻断：`4`
4. 环境依赖缺失：`1`
5. 真正未实现的测试：`20`

---

## 3. 逐类整改

### 3.1 过时测试，优先清零

这类测试当前描述的行为已经不对应 live 代码。继续保留只会制造伪覆盖。

#### A. `tests/test_cli_event_index.py` (`2`)

1. `test_search_command_with_event_index`
   - 原因：`search` 命令没有 `--mode` 参数，EventIndex 搜索路径也未按测试描述实现。
2. `test_history_command_context_panel`
   - 原因：测试断言的 `'同期决策上下文'` 文案在生产代码中未实现，mock 路径也写错了。

**动作**:

1. 不要简单取消 skip。
2. 先按 live CLI 重写测试目标。
3. 若该行为已经不属于产品范围，则直接删除测试。

#### B. `tests/test_e2e_scenarios.py` (`1`)

1. `test_day_handover_scenario`
   - 原因：`daily-start` / `daily-end` 命令已从 CLI 移除，测试仍基于旧工作流。

**动作**:

1. 直接按当前工作流重写。
2. 若对应能力已彻底下线，则删除旧场景测试。

---

### 3.2 手工 / 完整环境测试，保留但转到手工套件

这类测试不是“坏”，而是不能放在默认自动化套件里。

#### A. `tests/integration/test_cli_event_index.py` (`2`)

1. `test_mal_tasks_command_output`
2. `test_mal_index_rebuild`

原因：需要完整 CLI 环境与真实命令执行。

**动作**:

1. 保留测试意图。
2. 从默认自动化中剥离，转为手工检查清单或受控集成套件。
3. 在文件头明确“为什么不自动化”和“如何手工跑”。

---

### 3.3 真实数据 / 真实代码库保护性阻断，转受保护套件

这类测试直接打到真实量产数据或真实代码库，不适合默认 CI/本地全量自动跑。

#### A. `tests/integration/test_eventindex_compat_legacy.py` (`3`)

1. `test_eventindex_does_not_drop_events`
2. `test_eventindex_scans_both_directories`
3. `test_cli_index_scans_correct_directories`

原因：触碰实际用户量产数据，容易带来缓慢、并发超时和现场污染。

#### B. `tests/test_e2e_scenarios.py` (`1`)

1. `test_audit_scan`

原因：`audit` 会扫描真实代码库，`lint/format/sensitive_data` 结果受现场状态影响，不适合做稳定自动断言。

**动作**:

1. 不要取消 skip 直接塞回全量套件。
2. 把它们整理为“受保护测试组”。
3. 只在明确受控环境下运行，例如：
   - 指定样本仓库
   - 指定样本索引
   - 指定只读数据快照

---

### 3.4 环境依赖缺失，改成显式能力门槛

#### A. `tests/test_extractors.py` (`1`)

1. `test_litellm_client_with_mock`
   - 原因：`litellm` 未安装。

**动作**:

1. 这不是产品缺陷。
2. 需要决定该测试属于：
   - 默认依赖
   - 可选 extra
   - 独立 provider 测试组
3. 文档和测试标记要和安装方式一致，不能一直处于“环境里正好没装所以就 skip”。

---

### 3.5 真正未实现的测试，纳入产品/基础设施路线

这类 skipped 才是最实在的测试债。

#### A. `tests/integration/test_data_pipeline.py` (`6`)

覆盖：

1. ingest → markdown
2. markdown → EventIndex
3. EventIndex → VectorStore
4. 部分失败后的恢复
5. 端到端查询
6. 真实事件流

现状：文件整体仍是 TODO 骨架。

#### B. `tests/integration/test_fault_tolerance.py` (`6`)

覆盖：

1. daemon 崩溃恢复
2. 部分写入失败
3. 启动时 WAL 恢复
4. 索引损坏重建
5. 并发写入冲突
6. 真实崩溃场景

现状：文件整体仍是 TODO 骨架。

#### C. `tests/unit/test_llm_extractor.py` (`8`)

覆盖：

1. JSON 解析
2. Markdown 包裹 JSON 解析
3. 降级到正则提取
4. 解析失败标记
5. LLM 超时处理
6. summary/entities 提取
7. 真实 LLM 响应样本

现状：模块与测试都未完成。

**动作**:

1. 这三组不应继续长期停留在 skipped。
2. 必须按产品路线拆期处理，而不是统一写“后续补”。

---

## 4. 整改优先级

### P1. 先处理“测试已过时”

范围：

1. `tests/test_cli_event_index.py`
2. `tests/test_e2e_scenarios.py::test_day_handover_scenario`

理由：

1. 这类测试会误导审计结果。
2. 它们不是未来债，而是当前错误表达。

### P1.5. 再处理“受保护测试”的归宿

范围：

1. `tests/integration/test_cli_event_index.py`
2. `tests/integration/test_eventindex_compat_legacy.py`
3. `tests/test_e2e_scenarios.py::test_audit_scan`

理由：

1. 这些测试不该混在默认套件里。
2. 但也不能只靠 skip 永远挂着。

### P2. 处理依赖门槛不清

范围：

1. `tests/test_extractors.py`

理由：

1. 先明确它到底属于默认依赖还是可选依赖。
2. 这件事小，但不应一直含混。

### P2/P3. 按产品路线补未实现测试

范围：

1. `tests/integration/test_data_pipeline.py`
2. `tests/integration/test_fault_tolerance.py`
3. `tests/unit/test_llm_extractor.py`

理由：

1. 这是最大的测试空洞。
2. 但它们对应的是产品能力和基础设施能力本身，不能脱离产品路线孤立补。

---

## 5. 本轮建议的实际执行顺序

1. 先清零过时测试：
   - `tests/test_cli_event_index.py`
   - `tests/test_e2e_scenarios.py::test_day_handover_scenario`
2. 再把受保护测试迁出默认套件，整理出手工 / 受控运行入口。
3. 明确 `litellm` 相关测试的依赖策略。
4. 最后按产品优先级补：
   - data pipeline
   - fault tolerance
   - LLM extractor

---

## 6. 审计结论

当前 `30` 个 skipped 的核心问题不是“环境偶发”，而是：

1. 有一批测试已经过时；
2. 有一批测试本来就不该在默认自动化里跑；
3. 有一批关键测试到现在还没实现。

所以这件事不能靠“全量是绿的”带过去。  
这份清单的作用，就是把 skipped 从“测试输出里的背景噪音”变成明确的整改队列。
