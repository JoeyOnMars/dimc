# Task 010 Contract: L1 数据防线自动化 (DirectoryImporter 挂载 Orchestrator)

**risk_level: medium**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
根据最高指挥官指派的战略路线 [B]，我们需要完善 L1 层的数据自动化防线。
**现状**：`src/dimcause/importers/dir_importer.py` 当前只能通过显式的单次函数调用 `run_dir_import` 执行，缺乏后台轮询机制。我们在 Task 009 中修建的 `Orchestrator` 目前还没有装载任何真实的业务作业。
**目标**：将 `DirectoryImporter` 包装为一个合法的系统作业 (Job)，并挂载到 `Orchestrator` 内，打通定时自动增量/全量扫描目录并写入图谱的自动化通路。

## 2. 详细设计 (Detailed Design)
1. **新建系统作业集**：
   - 创建 `src/dimcause/scheduler/system_jobs.py`，负责收编系统级后台任务。
2. **挂载 DirectoryImporter**：
   - 在 `system_jobs.py` 内实现 `register_importer_job(orchestrator: Orchestrator, target_dir: str, interval: float)`。
   - 功能：定时调用 `DirectoryImporter(Path(".")).import_directory(target_dir)`。
   - 容错：使用 `try...except` 进行包裹并输出 `logger.error`，配合 Orchestrator 现有的异常隔离器。
3. **暴露启动入口**：
   - 提供一个辅助启动函数或在现有 daemon 架构中留下钩子，供以后 `dimc daemon up` 时自动注册。

## 3. 物理边界与授权范围 (Scope Exclusivity)
*   **允许修改/新增的文件**：
    - `src/dimcause/scheduler/system_jobs.py` (新增)
    - `tests/scheduler/test_system_jobs.py` (新增)
*   **严禁触碰的红线模块**：
    - 底座防线：`src/dimcause/core/` 目录全系。
    - CLI 表现层：除了添加必要的注册逻辑，不得重构 `cli.py`。
    - 严禁修改 `SearchEngine` 或 `GraphStore`。

## 4. 测试与验证期望 (Acceptance Criteria)
1. 单元测试证明调用 `register_importer_job` 后，Orchestrator 中确实多了一个名为 `directory_importer` 的作业。
2. 单元测试证明该作业被 Orchestrator 触发时，能正确调用内部导入钩子 (可通过 mock test 完成验证)。

## 5. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)
> 🚨🚨 **M专家警告：以下为物理隔离铁律！** 🚨🚨
一旦看到本契约获得 User 盖章的 `Approved/已确认`，你必须**严格按顺序**执行以下起手式，否则视为最高级别违规：

1. **绝对禁止**在 `main` 涂鸦，立刻新开分支：
   ```bash
   git switch main && git pull
   git switch -c feat/task-010-importer-job
   ```
2. （仅限授权范围）执行第一行代码修改。
3. （完成修改后）立刻 Commit 并原生 Push：
   ```bash
   git add src/dimcause/scheduler/ tests/scheduler/
   git commit -m "feat(scheduler): mount DirectoryImporter into orchestrator"
   git push -u origin HEAD
   ```
4. 运行**局部核心受影响**的测试，确保通过：
   > 🛑 **严禁**执行无过滤的全局测试（如 `pytest tests/`），你必须精确到模块级别，防止触碰历史技术债隔离区导致暴走。
   **你只能执行**: `pytest tests/scheduler/test_system_jobs.py -v`
5. 输出 `[PR_READY]` 呼叫 G 专家。
