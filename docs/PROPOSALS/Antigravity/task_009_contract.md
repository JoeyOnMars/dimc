# Task 009 Contract: Orchestrator L0 Infrastructure (P1 Architecture)

**risk_level: high**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
根据 `PROJECT_ARCHITECTURE.md` (v6.2)，**Layer 0: Infrastructure** 规划了 `scheduler/Orchestrator` 用于管理常驻进程和任务循环。
**现状**：目前系统缺乏真正的后台控制流，依然是纯响应式的单次命令行驱动 (`dimc down` / `dimc audit`)，无法支撑后续的自动导入、定时向量化与状态监测。
**目标**：本任务要求在 `src/dimcause/scheduler/` 目录下正式落地 `Orchestrator` 骨架及基础控制流，实现基于配置频率的任务分发架构。

## 2. 详细设计 (Detailed Design)
1. **模块与类结构**：
   - 新建/完善 `src/dimcause/scheduler/orchestrator.py`。
   - 实现核心类 `Orchestrator`，包含 `start()`, `stop()`, `register_job(job_name, interval, func)` 等生命周期方法。
2. **状态与容错**：
   - 使用 `threading` 或类似轻量级机制维持心跳（由于是本地工具，不强求多进程）。
   - 必须捕获子任务异常，保证单个 Job (`func`) 的崩溃不会导致整个 Orchestrator 进程死亡。
3. **集成点设计**：
   - 本次仅需搭建骨架和模拟心跳日志，**不要**在此分支内跨越层级去挂载真实的 L1 导入或 L4 推理任务（严守 Scope）。

## 3. 物理边界与授权范围 (Scope Exclusivity)
*   **允许修改/新增的文件**：
    - `src/dimcause/scheduler/orchestrator.py`
    - `tests/scheduler/test_orchestrator.py` (新增)
*   **严禁触碰的红线模块**：
    - `src/dimcause/core/` (CausalEngine, GraphStore, Schema 等底座全部禁碰)
    - 任何现有 CLI 的运行入口 (`cli.py`, `services/session_end.py`) 以防破坏现有工作流。

## 4. 测试与验证期望 (Acceptance Criteria)
1. 单元测试证明 `Orchestrator` 可以成功 register 两个不同的 mock jobs。
2. 单元测试证明调用 `start()` 后，能按 interval 触发 func。
3. 单元测试证明其中一个 mock job 抛出 Exception 时，另一个 job 和主 loop 依然存活。
4. 全局测试不受破坏：执行 `pytest tests/ -m "not legacy_debt"` 必须 100% Passed。

## 5. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)
> 🚨🚨 **M专家警告：以下为物理隔离铁律！** 🚨🚨
一旦看到本契约获得 User 盖章的 `Approved/已确认`，你必须**严格按顺序**执行以下起手式，否则视为最高级别违规：

1. **绝对禁止**在 `main` 涂鸦，立刻新开分支（如果当前不是的话）：
   ```bash
   git switch main && git pull
   git switch -c feat/task-009-orchestrator
   ```
2. （仅限授权范围）编写 `orchestrator.py` 和对应测试。
3. （完成修改后）立刻 Commit 并原生 Push：
   ```bash
   git add src/dimcause/scheduler/ tests/scheduler/
   git commit -m "feat(scheduler): implement layer 0 orchestrator backbone"
   git push -u origin HEAD
   ```
4. 运行所有相关测试，确保通过 (`pytest tests/ -m "not legacy_debt"`).
5. 输出 `[PR_READY]` 呼叫 G 专家进行代码结构审计。
