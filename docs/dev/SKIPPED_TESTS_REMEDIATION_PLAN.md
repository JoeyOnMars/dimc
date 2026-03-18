# DIMCAUSE 全量 Skipped 测试整改清单

**状态**：当前有效
**定位**：测试债专项清单，用于跟踪全量 skipped 的分类、归宿与整改顺序。
**边界**：本文不替代 `BACKLOG`、`ROADMAP` 或正式产品设计文档。

**审计基线**: 2026-03-18
**审计命令**: `pytest -q -rs`  
**审计结果**: `1116 passed, 19 skipped, 4 deselected`

---

## 1. 目的

这份清单只解决一个问题：把当前全量测试中的 `19` 个 skipped 和 `4` 个受保护测试拆成可执行整改项。
它不负责解释产品架构，也不替代 `BACKLOG`；它是测试债的专项处置文档。

原则：

1. `skipped` 不是“已验证通过”。
2. `skipped` 必须分清：过时测试、手工测试、受保护测试、环境依赖缺失、真正未实现。
3. 不同类型的 skipped，处置动作不同；不能统一用“后面再补”糊过去。

---

## 2. 总体分类

当前默认全量结果分成两部分：

1. `19` 个 skipped
2. `4` 个 deselected 受保护测试

其中 `19` 个 skipped 分成四类：

1. 过时测试：`0`
2. 手工 / 完整环境测试：`2`
3. 环境依赖缺失：`0`（已清零）
4. 真正未实现的测试：`17`

---

## 3. 逐类整改

### 3.1 过时测试，已清零

这类测试当前描述的行为已经不对应 live 代码。继续保留只会制造伪覆盖。

#### 已完成动作

1. 删除 `tests/test_cli_event_index.py::test_search_command_with_event_index`
   - 原因：`search` 命令没有 `--mode` 参数，EventIndex 搜索路径也未按旧测试描述实现。
2. 删除 `tests/test_e2e_scenarios.py::test_day_handover_scenario`
   - 原因：`daily-start` / `daily-end` 命令已从 CLI 移除，旧工作流测试不再属于 live 产品面。
3. 将 `tests/test_cli_event_index.py::test_history_command_context_panel` 替换为当前 live 行为测试
   - 新测试：`tests/test_cli_history.py::test_history_command_non_interactive_renders_rows`
   - 新断言：验证 `history --no-interactive` 能渲染当前历史行，而不再断言不存在的“同期决策上下文”面板。

**结果**:

1. 过时 skipped 已清零。
2. 当前默认套件不再为这 3 条旧用例支付维护成本。

---

### 3.2 手工 / 完整环境测试，保留但转到手工套件

这类测试不是“坏”，而是不能放在默认自动化套件里。

#### A. `tests/integration/test_cli_event_index.py` (`2`)

1. `test_cli_tasks_command_output`
2. `test_cli_index_rebuild`

原因：需要完整 CLI 环境与真实命令执行。

**动作**:

1. 保留测试意图。
2. 从默认自动化中剥离，转为手工检查清单或受控集成套件。
3. 在文件头明确“为什么不自动化”和“如何手工跑”。

---

### 3.3 真实数据 / 真实代码库保护性阻断，已迁出默认套件

这类测试直接打到真实量产数据或真实代码库，不适合默认 CI/本地全量自动跑。

#### A. `tests/integration/test_eventindex_compat_legacy.py` (`3`)

1. `test_eventindex_does_not_drop_events`
2. `test_eventindex_scans_both_directories`
3. `test_cli_index_scans_correct_directories`

原因：触碰实际用户量产数据，容易带来缓慢、并发超时和现场污染。

#### B. `tests/test_e2e_scenarios.py` (`1`)

1. `test_audit_scan`

原因：`audit` 会扫描真实代码库，`lint/format/sensitive_data` 结果受现场状态影响，不适合做稳定自动断言。

**已完成动作**:

1. 已把这 `4` 条测试从 `skip` 改为 `@pytest.mark.protected`。
2. `pytest` 默认套件现在会自动 deselect 受保护测试；只有显式传 `--run-protected` 才运行。
3. `tests/integration/test_eventindex_compat_legacy.py` 已改成临时工作区 + 临时 `HOME` 下的受控兼容性验证，不再依赖开发机真实 `~/.dimcause` 或历史索引。
4. `tests/test_e2e_scenarios.py::test_audit_scan` 已改为受保护真实 audit 链路验证（不再 fake `run_audit`），在临时工作区中执行真实检查并断言敏感信息命中。

**当前状态**:

1. 默认全量：这 `4` 条不再计入 skipped。
2. 显式运行：`pytest -q -rs --run-protected tests/integration/test_eventindex_compat_legacy.py tests/test_e2e_scenarios.py` 当前 `4/4` 通过。

---

### 3.4 环境依赖缺失，已清零

#### A. `tests/test_extractors.py` (`1`)（已完成）

1. `test_litellm_client_with_mock`
   - 原问题：`litellm` 未安装时直接 `skip`。
   - 已完成动作：改为 mock `litellm` 的可执行测试，不再依赖真实安装环境。

**结果**:

1. 环境依赖缺失类 skipped 已从 `1` 降为 `0`。
2. 默认全量基线由 `1112/23/4` 收敛到 `1116/19/4`。

---

### 3.5 真正未实现的测试，纳入产品/基础设施路线

这类 skipped 才是最实在的测试债。

#### A. `tests/integration/test_data_pipeline.py` (`4`)

覆盖：

1. EventIndex → VectorStore
2. 部分失败后的恢复
3. 端到端查询
4. 真实事件流

现状：`ingest → markdown` 与 `markdown → EventIndex` 已转为可执行测试并通过；其余 `4` 条仍是 TODO skip。

#### B. `tests/integration/test_fault_tolerance.py`（总计 `6`：已落地 `1`，剩余 `5`）

覆盖：

1. daemon 崩溃恢复
2. 部分写入失败
3. 启动时 WAL 恢复
4. 索引损坏重建
5. 并发写入冲突
6. 真实崩溃场景

现状：`test_index_corruption_rebuild` 已转为可执行集成断言并通过；其余 `5` 条仍为 TODO skip。

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

### ~~P1.5. 优先处理“受保护测试”的归宿~~ (已完成)

范围：

1. `tests/integration/test_cli_event_index.py`
2. `tests/integration/test_eventindex_compat_legacy.py`
3. `tests/test_e2e_scenarios.py::test_audit_scan`

结果：

1. 这些测试已不再混在默认套件里。
2. 也不再继续靠 skip 假装存在，而是进入显式 `--run-protected` 受控套件。

### ~~P2. 处理依赖门槛不清~~ (已完成)

范围：

1. `tests/test_extractors.py`

结果：

1. 相关 skipped 已清零，不再把“环境里正好没装”当作长期跳过理由。

### P2/P3. 按产品路线补未实现测试

范围：

1. `tests/integration/test_data_pipeline.py`
2. `tests/integration/test_fault_tolerance.py`
3. `tests/unit/test_llm_extractor.py`

理由：

1. 这是最大的测试空洞。
2. 但它们对应的是产品能力和基础设施能力本身，不能脱离产品路线孤立补。

---

## 5. 后续建议执行顺序（基于已启用受保护机制）

1. 保持受保护测试继续走 `--run-protected` 受控入口，不回流默认套件。
2. 按产品优先级补齐未实现测试：
   - data pipeline
   - fault tolerance
   - LLM extractor

---

## 6. 审计结论

当前测试债的核心问题不是“环境偶发”，而是：

1. 有一批测试已经过时；
2. 有一批测试本来就不该在默认自动化里跑；
3. 有一批关键测试到现在还没实现。

所以这件事不能靠“全量是绿的”带过去。  
这份清单的作用，就是把 `skipped + deselected protected` 从“测试输出里的背景噪音”变成明确的整改队列。
