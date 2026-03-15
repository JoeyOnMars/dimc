# Task 005 契约: CLI `dimc extract` 与 Watcher 整合

## 1. 目标
现已完成核心的 `ExtractionPipeline` 和存储侧机制，本任务需将其在 CLI 层面开放，并替换 `SessionEndService` 中过时的 `run_smart_scan()` 逻辑，实现真正的 Local-First Causal Engine 流水线。

## 2. 交付物与修改点

### 2.1 新增/修改 CLI 命令 (`src/dimcause/cli.py`)
- **`dimc extract [session_id]`**
  - 使用 `typer` 注册。
  - 参数：可选的 `session_id`。如果不提供，则使用 `dimcause.core.state` 中 `get_last_session()`/`get_active_job()` 推断出的最近或当前 active session。
  - 核心逻辑：
    1. 实例化 `ExtractionPipeline`（其依赖 `EventIndex`, `GraphStore`, `ChunkStore`）。
    2. 调用 `pipeline.run(session_id)`。
    3. 在控制台通过 `rich` 打印返回的执行统计 (`stats`)。

- **`dimc chunks [session_id]`** (可选增强，V6.3_ROADMAP 中提到)
  - 用于调试和查看某个 session 的 chunks 状态（总数、`raw`、`embedded`、`extracted` 数量统计等）。

### 2.2 重构 `SessionEndService` (`src/dimcause/core/session_end.py`)
- 废弃当前基于 `SessionExtractor` 与本地 `LiteLLMClient` 混合裸调的 `run_smart_scan` 及其关联的私有防重写子方法 (`_run_llm_extraction`, `_run_local_extraction`)。
- 在 `SessionEndService.execute()` 阶段（第 4 步）：
  1. 实例化 `ExtractionPipeline`。
  2. 调用 `pipeline.run(session_id)` 代替 `run_smart_scan`。
  3. 通过 `console.print` 输出本次结案（down）收集入库的数据统计。

### 2.3 测试回归与集成
- 补充/修改 `test_cli.py` 或增设 `test_cli_extract.py` 来覆盖 `dimc extract`。
- 修改 `test_session_end.py` 以适应 `run_smart_scan` 被 `ExtractionPipeline` 替换。

## 3. 合并与分支准则复申 (致: M)
- 由于之前阶段已在 `main` 固化跑通，**无需将前面任务的提交重新打回各自的独立分支**，直接继续前进。
- 从本 Task (005) 开始，严格执行 **One Task, One Branch** 纪律。现已基于 `main` 检出 `feat/task-005-extract-cli`，M 专家请直接基于此分支完成以上契约并提交。

## 4. 验收标准
1. 在 `dimc extract <sess-id>` 执行后，能够正确调用并走通 Pipeline，输出执行统计。
2. 运行 `dimc down`，能够平滑触发流水线（L1 必须执行；如有 Key 则 L2 执行并建边）。
3. Pytest 核心与 CLI 测试 100% PASS。
