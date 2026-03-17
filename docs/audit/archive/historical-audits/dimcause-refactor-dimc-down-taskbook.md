# DIMCAUSE 测试修复任务书 · `refactor/dimc-down`

**状态**: 历史任务书；仅供追溯当时修复约束，不作为当前正式执行入口。

**文件版本**: v1.0
 **日期**: 2026-02-20
 **性质**: 这是一份**强制性任务书**，不是建议。你在执行任何步骤前必须完整阅读本文档。
 **依据文档**（你必须在开始前全部读取）：

* `.agent/rules/Honesty-And-Structure.md`
* `.agent/rules/Code-Audit.md`
* `.agent/rules/contracts.md`
* `.agent/rules/Agent-Planning-Standard.md`
* `.agent/rules/SYSTEM_CONTEXT.md`

------

## 第零节：你必须理解的现实

在 `refactor/dimc-down` 分支上，过去的 AI 操作产生了以下系统性破坏，你有义务修复，但修复方式受到严格约束：

1. **GraphStore 构造签名被破坏**：旧测试传入 `persist_path=`，新构造函数不接受该参数，导致 42 个测试崩溃。
2. **state.py 多个公开函数被删除**：`record_job_start`、`ensure_today_dir`、`OrphanJob` dataclass 等被移除，导致 12 个测试 ImportError。
3. **CLI 输出语言被单方面改为中文**：19 个测试断言期望英文字符串，现在输出是中文。
4. **workflow/context 接口被破坏**：`context.get_root_dir` 不存在，导致 15 个 fixture 级别的 ERROR，e2e 全线崩溃。
5. **测试断言被降级**：两个 CLI 测试从"验证行为"降级为"只要不崩"，这是不可接受的。

**这些破坏的根本原因是：在没有兼容层、没有迁移策略、没有 RFC 的情况下，直接修改了对外接口。**

------

## 第一节：铁律约束（高于任何任务指令）

以下约束在整个修复过程中**绝对有效**，不得因任何原因违反：

## 约束 A：禁止再次破坏接口

* **严禁**修改以下模块的公开函数签名、返回值结构、类构造参数（除非任务书明确要求）：
  * `src/dimcause/storage/graph_store.py` — `GraphStore.__init__()` 及所有公开方法
  * `src/dimcause/core/state.py` — 所有公开函数
  * `src/dimcause/core/context.py` — 所有公开函数
  * `src/dimcause/cli/` — 所有命令名和主要参数
* 如果你认为某个接口"设计有问题应该改"，**必须停下来**，在对话中提出 RFC 请求，等待人类决策，不得自行修改。

## 约束 B：禁止降级测试断言

* **严禁**通过修改断言期望值、删减验证项、或把精确断言改成"只检查不崩"的方式来让测试变绿。
* **每一处测试修改**，必须在对话中先输出 `[TEST_FIX_REASON]` 声明，格式如下：

```
text
[TEST_FIX_REASON]
测试文件: tests/xxx.py :: test_xxx
修改前断言: assert X == Y
修改后断言: assert X == Z
原因: 旧期望值 Y 是因为 [具体历史原因]，实际正确行为是 Z，因为 [理由]
验证方式: [如何确认这个修改是正确的]
```

* 未输出 `[TEST_FIX_REASON]` 就直接改测试，视为**严重违规**，修改必须回滚。

## 约束 C：禁止跳步提交

* 每完成一个任务节（Task）的所有子步骤后，**必须先运行验收命令**，确认通过后才能 commit。
* **禁止**"先提交，测试后补"或"一次提交覆盖多个任务节"。
* 每次 commit message 必须包含本任务节编号，例如：`fix(T1): 恢复 GraphStore persist_path 兼容层`

## 约束 D：禁止修改设计文档

* **严禁**修改 `docs/PROJECT_ARCHITECTURE.md`、`docs/V6.0/DEV_ONTOLOGY.md`、`docs/STORAGE_ARCHITECTURE.md`。
* 这些是设计目标，不是进度记录。进度只更新 `docs/STATUS.md`。

------

## 第二节：Pre-flight 检查（第一件事，必须执行）

在动任何代码之前，你必须完成以下检查，并将结果**完整输出在对话中**，不得省略或简化：

## PF-1：确认环境

```
bash
# 必须在激活 venv 后执行
source /Users/mini/projects/GithubRepos/dimc/.venv/bin/activate
which python
python --version
git branch --show-current
git status --short | head -20
```

**期望**：

* `python` 路径包含 `.venv`
* 分支为 `refactor/dimc-down`
* 输出 git status，让人类看到当前 dirty 状态

## PF-2：扫描 GraphStore 当前签名

```
bash
grep -n "def __init__" src/dimcause/storage/graph_store.py
grep -n "persist_path" src/dimcause/storage/graph_store.py
```

**输出目的**：确认现在的 `GraphStore.__init__()` 签名，以便 T1 任务的兼容层设计。

## PF-3：扫描 state.py 当前状态

```
bash
grep -n "^def \|^class " src/dimcause/core/state.py | head -40
grep -rn "record_job_start\|ensure_today_dir\|OrphanJob" src/ tests/ | grep -v ".pyc"
```

**输出目的**：确认哪些函数已经不存在、哪些调用点引用了已删除的函数。

## PF-4：扫描 context.py 当前状态

```
bash
grep -n "^def \|^class " src/dimcause/core/context.py | head -40
grep -rn "get_root_dir" src/ tests/ | grep -v ".pyc"
```

**输出目的**：确认 `get_root_dir` 是否真的不存在，以及有多少调用点。

## PF-5：基线测试快照

```
bash
python -m pytest tests/ \
  --ignore=tests/test_graph_store.py \
  --ignore=tests/test_tui.py \
  --ignore=tests/integration \
  -q --tb=no 2>&1 | tail -5
```

**输出目的**：记录修复前的基线数字（103 failed, 693 passed），后续每个任务节完成后都要对比这个数字。

------

## 第三节：任务节清单

任务节按**优先级和依赖关系**排序，必须**按顺序执行**，不得并行或跳过。

------

## T1：修复 GraphStore 兼容层（阻塞 42 个测试）

**根因**：`GraphStore.__init__()` 签名变更，旧代码传 `persist_path=` 但新构造函数不接受。
 **修复策略**：在 `GraphStore.__init__()` 中添加 `persist_path` 兼容参数，打印 deprecation 警告，内部映射到新参数。**不得修改新签名的核心逻辑。**

**步骤 T1.1**：读取并输出当前 `GraphStore.__init__()` 完整签名（来自 PF-2 结果）。

**步骤 T1.2**：在对话中输出你的兼容层设计方案，格式：

```
text
[T1 兼容层设计]
当前签名: GraphStore.__init__(self, ...)
新增参数: persist_path=None (Optional[str])
映射逻辑: 若 persist_path 不为 None，则 [说明如何映射到新参数]
警告输出: warnings.warn("persist_path 已废弃，请改用 xxx，将在 V7.0 移除", DeprecationWarning)
影响范围: 仅新增兼容参数，不改变其他任何行为
```

等待人类确认后再写代码。

**步骤 T1.3**：实现兼容层，只改 `src/dimcause/storage/graph_store.py`，改动不超过 10 行。

**步骤 T1.4**：验收命令：

```
bash
python -m pytest tests/test_daemon.py tests/test_daemon_full.py \
  tests/test_daemon_manager.py tests/test_coverage_boost.py \
  tests/test_llm_mock.py tests/test_final_push.py \
  -q --tb=short 2>&1 | tail -20
```

**期望**：原来因 `TypeError: unexpected keyword argument 'persist_path'` 崩溃的测试，此时不再崩溃（可能还有其他原因失败，但不应再有 `persist_path` 错误）。

**步骤 T1.5**：commit：`fix(T1): 恢复 GraphStore persist_path 兼容参数`

------

## T2：修复 context.py `get_root_dir`（阻塞 15 个 ERROR）

**根因**：`context.py` 中 `get_root_dir` 函数不存在，导致 6 个 context 测试和多个 e2e/workflow 测试在 fixture 阶段就 ERROR。
 **修复策略**：在 `context.py` 中**恢复** `get_root_dir` 函数（或提供等效别名），不得改变其他函数。

**步骤 T2.1**：输出 PF-4 的 grep 结果，确认：

* `get_root_dir` 在 context.py 里是否完全不存在。
* 测试里如何使用它（monkeypatch 对象还是直接调用）。

**步骤 T2.2**：在对话中输出你的方案：

```
text
[T2 修复方案]
确认: get_root_dir 在 context.py 中 [存在/不存在]
现有替代: context.py 中存在 get_logs_dir()，路径逻辑为 [...]
恢复方案: 在 context.py 末尾添加:
  def get_root_dir() -> Path:
      """已废弃，请使用 get_logs_dir()。保留用于兼容旧测试。"""
      return [具体返回值]
影响: 只新增函数，不改其他任何逻辑
```

等待人类确认后再写代码。

**步骤 T2.3**：实现。

**步骤 T2.4**：验收命令：

```
bash
python -m pytest tests/test_context.py tests/test_e2e.py \
  tests/test_e2e_scenarios.py tests/test_workflow.py \
  -q --tb=short 2>&1 | tail -20
```

**期望**：不再有 `AttributeError: module 'dimcause.core.context' has no attribute 'get_root_dir'` 的 ERROR。测试可能还会有其他原因 FAIL，但不能有 fixture-level ERROR。

**步骤 T2.5**：commit：`fix(T2): 恢复 context.get_root_dir 兼容函数`

------

## T3：修复 state.py 被删除的 API（阻塞 12 个测试）

**根因**：`record_job_start`、`ensure_today_dir`、`OrphanJob` 等被从 state.py 移除，12 个测试（非 test_state.py）出现 ImportError。
 **修复策略**：在 state.py 中恢复这些函数的签名（可以是薄封装，内部调用新逻辑），不改变调用者的代码。

**步骤 T3.1**：基于 PF-3 的 grep 结果，列出所有引用了被删除函数的测试文件，格式：

```
text
[T3 影响范围]
被删除函数: record_job_start, ensure_today_dir, OrphanJob
引用测试文件:
  - tests/xxx.py: 第 N 行，调用方式 [...]
  - tests/yyy.py: 第 N 行，调用方式 [...]
引用源码文件 (非测试):
  - src/xxx.py: 第 N 行，调用方式 [...]
```

**步骤 T3.2**：对每个被删除的函数，确认：

* 它在旧版本里做什么。
* 现在是否有等效的替代函数。
* 兼容层实现方式。

在对话中输出完整映射表：

```
text
[T3 函数映射]
record_job_start(job_id, ...) -> [旧行为] -> 现在用 [新函数] 替代，映射方式: [...]
ensure_today_dir() -> [旧行为] -> 现在用 [新函数] 替代，映射方式: [...]
OrphanJob dataclass -> [旧结构] -> 现在返回 dict，兼容方案: [...]
```

等待人类确认。

**步骤 T3.3**：实现。只改 `src/dimcause/core/state.py`，只新增兼容层，不改其他逻辑。

**步骤 T3.4**：验收命令：

```
bash
# 先找到受影响的测试文件（来自 T3.1 的清单）
python -m pytest [T3.1中列出的测试文件] -q --tb=short 2>&1 | tail -20
```

**期望**：不再有 `ImportError: cannot import name 'record_job_start'` 类错误。

**步骤 T3.5**：commit：`fix(T3): 恢复 state.py 兼容函数 record_job_start/ensure_today_dir`

------

## T4：处理 CLI 语言变更问题（影响 19 个测试）

**这是一个需要人类决策的节点，不得自行执行。**

**背景**：CLI 输出从英文改为中文，19 个测试期望英文字符串但实际输出为中文。

**你需要做的**：仅做分析，不改代码，在对话中输出以下决策报告：

```
text
[T4 决策报告]
影响测试数: 19
典型冲突示例:
  测试期望: assert 'No Axiom Violations Found' in output
  实际输出: '✅ 未发现公理违规。'

选项 A: 恢复 CLI 为英文输出
  优点: 测试不用改，与原始设计一致
  缺点: 失去中文本地化
  工作量: 改 CLI 输出文案，约 N 处

选项 B: 更新测试以匹配中文输出
  优点: 保留中文输出
  缺点: 测试需要逐一更新，且中文字符串若再变动需要再改
  工作量: 改 19 个测试文件，约 M 处
  [TEST_FIX_REASON 前提: 必须确认中文输出是经过架构决策确定的，不是随意改的]

选项 C: 支持 --lang 参数，CI 用英文、交互用中文
  优点: 两端都满足
  缺点: 实现成本最高，需要 RFC

我的评估: [基于 Honesty-And-Structure.md 第 0 条，此处属于产品行为变更，需要人类决策]
```

**等待人类选择 A/B/C 之后，才能进入 T4 实现阶段。**

------

## T5：修复 workflow 接口变更（影响 12 个测试）

**前置条件**：T2 完成（`get_root_dir` 已恢复），因为 workflow 测试的 ERROR 很可能就是 `get_root_dir` 引起的。

**步骤 T5.1**：在 T2 完成后，重跑 workflow 测试，确认剩余失败数：

```
bash
python -m pytest tests/test_workflow.py -q --tb=short 2>&1
```

**步骤 T5.2**：对每一个仍然失败的测试，输出分析：

```
text
[T5 失败分析]
测试: test_workflow.py :: test_xxx
错误类型: KeyError / AssertionError / ImportError
根因: [具体是哪个接口/字段不存在]
是接口被删除了，还是返回结构变了，还是逻辑行为变了？
```

**步骤 T5.3**：基于分析，提出修复方案（同样需要区分"恢复旧接口"还是"更新测试"），等待人类确认。

**步骤 T5.4**：实现，每修一个测试文件，必须先输出 `[TEST_FIX_REASON]`。

**步骤 T5.5**：验收：

```
bash
python -m pytest tests/test_workflow.py -q --tb=short 2>&1 | tail -10
```

**步骤 T5.6**：commit。

------

## T6：修复 model_config 默认值（影响 3 个测试）

**步骤 T6.1**：找到失败的测试：

```
bash
python -m pytest tests/core/test_model_config.py -q --tb=short 2>&1
```

**步骤 T6.2**：输出分析：

```
text
[T6 分析]
测试期望默认值: ModelStack.TRUST
实际默认值: ModelStack.PERFORMANCE
这个默认值是在哪里定义的？[文件:行号]
这个默认值是什么时候被改的？(git log 查询)
改动是否经过 RFC 或人类确认？
```

**步骤 T6.3**：如果改动没有经过确认，**默认回滚默认值**，而不是更新测试。提出方案等待确认。

**步骤 T6.4**：实现，commit：`fix(T6): 恢复 model_config 默认值`

------

## T7：恢复被降级的 CLI 测试断言

**背景**：`test_log_command` 和 `test_reflect` 在上一轮修复中被降级为"只检查不崩"，这是不可接受的。

**步骤 T7.1**：读取这两个测试的当前状态：

```
bash
grep -A 20 "def test_log_command\|def test_reflect" tests/test_cli.py
```

**步骤 T7.2**：对每个降级测试，输出：

```
text
[T7 降级恢复分析]
测试: test_cli.py :: test_log_command
当前断言: assert result.exit_code == 0  (只检查不崩)
原始断言应该是什么？[基于 Code-Audit.md §12.1，测试应覆盖正常路径+主要异常路径]
为什么之前降级？mock 不足，原因是 [...]
恢复方案: 
  - 需要 mock 哪些依赖？
  - 断言什么行为？
  - 是否需要先修复 CLI 实现本身？
```

**步骤 T7.3**：基于分析，恢复完整断言（不是简单加回旧代码，是重新设计正确的 mock 和断言）。

**步骤 T7.4**：验收 + commit：`fix(T7): 恢复 test_log_command/test_reflect 完整断言`

------

## T8：修复 benchmark fixture 缺失（影响 1 个 ERROR）

**步骤 T8.1**：确认问题：

```
bash
python -m pytest tests/storage/test_graph_performance.py -q --tb=short 2>&1
```

**步骤 T8.2**：检查 `pyproject.toml` 是否有 `pytest-benchmark` 依赖：

```
bash
grep -i "benchmark" pyproject.toml
```

**步骤 T8.3**：输出方案选择：

```
text
[T8 方案]
选项 A: 安装 pytest-benchmark 依赖（如果 pyproject.toml 中有但未安装）
选项 B: 将 test_graph_performance.py 中的 benchmark fixture 改为手动计时
  - 方式: 用 time.perf_counter() 替代 benchmark()
  - 需要 [TEST_FIX_REASON]
```

等待确认后实施。

------

## T9：修复 C6 其他逻辑变更（15 个测试）

**步骤 T9.1**：在完成 T1-T8 后，重跑全量测试，输出新的失败清单：

```
bash
python -m pytest tests/ \
  --ignore=tests/test_graph_store.py \
  --ignore=tests/test_tui.py \
  --ignore=tests/integration \
  -q --tb=line 2>&1 | grep "FAILED" | head -30
```

**步骤 T9.2**：对剩余失败逐一分析，按同样的格式（`[TEST_FIX_REASON]` + 等待确认 + 实现）处理每一个。

**原则**：不允许批量"快速修复"，每一个失败都要单独分析和确认。

------

## 第四节：每轮结束时的交付标准

每个任务节完成后，你必须输出以下格式的进度更新：

```
text
[任务节完成报告]
任务节: T1（GraphStore 兼容层）
完成时间: [时间]
修改文件:
  - src/dimcause/storage/graph_store.py: 第 N 行，新增 persist_path 兼容参数
测试变化:
  - 修复前: 42 个 TypeError: persist_path
  - 修复后: 0 个 TypeError: persist_path（可能有其他原因失败）
本节 commit: [commit hash]
遗留问题: [如果有]
```

------

## 第五节：最终验收标准

所有任务节完成后，运行以下命令，结果需满足条件才可宣告完成：

```
bash
python -m pytest tests/ \
  --ignore=tests/test_graph_store.py \
  --ignore=tests/test_tui.py \
  --ignore=tests/integration \
  -q --tb=no 2>&1 | tail -5
```

**验收要求**：

* Failed 数量 ≤ 15（由于 T4 语言问题等待决策，允许保留一定数量的待确认失败）
* ERROR 数量 = 0（所有 fixture-level 错误必须清零）
* 所有被降级的测试断言必须恢复（T7）
* 无任何 `[TEST_FIX_REASON]` 未输出的测试修改

**不允许通过以下方式达到"验收通过"**：

* 新增 `--ignore` 来忽略更多测试文件
* 用 `pytest.skip()` 跳过失败测试
* 通过降低断言让失败测试变绿

------

## 附：任务开始前的确认问题

在开始 Pre-flight 之前，你必须回答以下问题（不允许含糊）：

1. 你是否已经读取了本文档中指定的全部 5 个规则文件？回答：是/否 + 文件名列表。
2. 你是否理解：在本任务中，改测试代码前必须输出 `[TEST_FIX_REASON]`，否则违规？回答：是/否。
3. 你是否理解：T4 是决策节点，在人类选择选项前不得动 CLI 或测试代码？回答：是/否。
4. 你是否理解：你的职责是**修复破坏**，不是**趁机重构**？回答：是/否。

只有在这 4 个问题全部回答"是"之后，才可以执行 Pre-flight 检查。
