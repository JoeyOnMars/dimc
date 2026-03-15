# RFC 003: Master-Slave 多 Agent 开发环境架构

## 1. 背景 (Background)
我们旨在将 `dimcause` 演进为一个 **多 Agent 编码系统** (Multi-Agent Coding System)。在此系统中，一个中心化的 **Master** (编排器) 负责管理一组 **Slave** (Worker) Agent。这些 Agent 作为独立的进程在开发环境中运行，能够利用 `dimcause` CLI 的全部能力自主执行任务。

## 2. 架构 (Architecture)

### 2.1 Master (编排器)
- **角色**: 任务分发与状态管理。
- **组件**: `dimc scheduler loop` (增强版)。
- **职责**:
    1.  监控 `docs/V6.0/STATUS.md` 和 `agent-tasks/*.md` 中的待办任务。
    2.  将任务分配给空闲的 Worker。
    3.  验证任务完成情况 (运行检查、审查日志)。
    4.  更新全局项目状态。

### 2.2 Slave (Worker Agents)
- **角色**: 任务执行者。
- **组件**: 独立的 OS 进程 (例如 `python script`, `docker container`, 或 `MCP Client`)。
- **职责**:
    1.  向 Master 请求任务。
    2.  使用 `dimc` 工具执行任务。
    3.  汇报结果 (成功/失败/阻塞)。

## 3. 接口 (Interfaces)

### 3.1 任务接口 (控制面)
为简化 V1 版本，我们将使用 **基于文件的队列** (后续可升级为 Redis/Socket)。
- **待处理**: `queue/pending/*.json` (任务定义)
- **进行中**: `queue/processing/*.json` (被 WorkerID 锁定)
- **结果**: `queue/results/*.json` (输出与状态)

### 3.2 工具接口 (数据面)
Agent 通过 **两条路径** 与系统交互：
1.  **CLI 桥接 (原生)**: Agent 直接通过子进程调用 `dimc why`, `dimc audit`, `dimc edit`。
2.  **MCP 协议 (标准化)**: `dimc` 将所有 CLI 命令暴露为 MCP Tools (例如 `call_tool("dimcause", "run_command", {"command": "dimc why ..."})`)。

## 4. 实施计划 (近期)

### 第一阶段: MCP Server 扩展 (第 1 周)
**目标**: 通过 MCP 向 Agent 开放所有 `dimc` 能力。
- [ ] 重构 `src/dimcause/protocols/mcp_server.py`。
- [ ] 添加 `run_dimc_command` 工具 (通用 CLI 包装器)。
- [ ] 添加高频操作的专用工具: `read_file`, `write_file`, `git_commit`。

### 第二阶段: Worker 运行时 (第 1-2 周)
**目标**: 创建一个能够领取并运行任务的 "Minion" 进程。
- [ ] 创建 `src/dimcause/agent/worker.py`。
- [ ] 实现 `Worker.loop()`:
    - 轮询任务。
    - 生成计划 (使用 LLM)。
    - 执行步骤 (使用 MCP/CLI)。
    - 提交结果。

### 第三阶段: 调度器 v2 (第 2 周)
**目标**: 自动化 Master 循环。
- [ ] 更新 `dimc scheduler loop` 以扫描 `docs/V6.0/STATUS.md` 并分发任务。
- [ ] 实现 `TaskQueue` 管理。
- [ ] 支持 Worker 并发执行。

## 5. 成功标准
- [ ] 验证脚本 (`scripts/test_multi_agent.py`) 能够：
    1.  向队列发布一个 "Fix Typo" 任务。
    2.  启动一个 Worker 进程。
    3.  Worker 允许 LLM 使用 `dimc` 完成任务。
    4.  Master 验证并标记任务为 Done。
