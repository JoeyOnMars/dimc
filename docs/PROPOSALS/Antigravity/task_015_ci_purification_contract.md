# Task 015 Contract: CI Purification (Ruff Debt & check.zsh Hardening)

**risk_level: low** (Code formatting & script isolation only, no core business logic changes)

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。

## 1. 目标与背景 (Goal & Context)
在 Task 014 的红蓝对抗终局审计中，`scripts/check.zsh` 暴露出了两项历史包袱与脆弱点，导致脚本物理执行返回 `Exit Code 2`：
1. **Ruff 历史技术债**: `src/` 目录下多达 48 个历史存留的 lint 错误（如未使用导入、类型断言不规范等）。
2. **Pytest 环境穿透隔离失败**: `scripts/check.zsh` 脚本在未显式挂载 `.venv` 且系统 Python 与虚拟环境脱节的终端跑测时，会因寻找不到 `dimcause` 模块引发 9 errors 级别的系统级假阴性断代报错。

本任务目标：**清空 48 个 Ruff 错误达致全绿，加固 check.zsh 的物理隔离墙，确保未来所有检验达到绝对的 Exit Code 0 纯净态**。

## 2. 详细设计 (Detailed Design)

**2.1 清空 Ruff 历史技术债**
- 运行 `source .venv/bin/activate && ruff check --fix src/` 以自动修复大部分冗余的 `import` 遗留和空白符瑕疵。
- 审阅 `ruff check src/` 剩余的顽固报错，逐一手动修复代码，直至输出 0 errors 为止。
- *安全底线*：所有修复**必须**无损现有业务逻辑，仅仅是移除废弃依赖、调整类型注解或规范缩进。

**2.2 加固 `scripts/check.zsh` 物理隔离屏障 (The Iron Gate)**
- 定位 `scripts/check.zsh`。
- 在脚本开头的常量与路径声明区，加入环境强校验。脚本必须具备**自我隔离约束力**。
- **强制指令**：在执行实质性的 `ruff` 和 `pytest` 之前，在 `check.zsh` 中硬编码读取当前工程的 `.venv`：
    ```bash
    # Ensure correct virtual environment is active
    if [[ -z "${VIRTUAL_ENV}" ]] || [[ "${VIRTUAL_ENV}" != *".venv"* ]]; then
        if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
            echo "[DIMC] Force activating local .venv..."
            source "$REPO_ROOT/.venv/bin/activate" || { echo "Failed to activate .venv"; exit 1; }
        else
            echo "[DIMC] ERROR: No .venv found in expected path. Aborting check."
            exit 1
        fi
    fi
    ```
- 将底层原有的 `source .venv/bin/activate` 集中收拢到顶部全局。

## 3. 物理边界与授权范围 (Scope Exclusivity)

**允许修改的文件 (Whitelist):**
- `scripts/check.zsh`
- `src/dimcause/**/*.py` (仅限于解决 Ruff 抛出错误的文件，绝对禁止触碰未报错的正常业务逻辑文件)

**严禁触碰的文件 (Blacklist):**
- `docs/PROJECT_ARCHITECTURE.md`, `docs/V6.0/DEV_ONTOLOGY.md` 等 L1 架构文档
- `tests/**/*.py` （除非遇到 Ruff 发现在测试用例里也有格式错误）

## 4. 测试与验证期望 (Acceptance Criteria)

- **A组 [Lint 物理全绿]**: 在未挂载环境的基础终端里，直接 `bash scripts/check.zsh`，能看到脚本自身顺利接管启动 `.venv`。
- **B组 [执行绝对无错]**: `scripts/check.zsh` 脱壳全套跑完，全程 0 Errors（无 `ruff` 红字，无 `pytest` 假阴性路径红字），最终稳稳输出 `[DIMC] All checks passed`，并成功以 `Exit Code 0` 退出。

## 5. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)

1. 分支保障核实：本次锚点分支为 `feat/task-015-ci-purification`（此分支已由最高指挥官预先创建并推入，你必须先 `git fetch origin` 然后 `git checkout feat/task-015-ci-purification`）。
2. 执行代码层改动（首先改脚本，然后执行 ruff 扫清代码）。
3. Commit 并 Push 到远端。
4. 在本地反复执行 `./scripts/check.zsh`，直至得到唯一的结局：**All checks passed**。
5. 成功后，高呼 `[PR_READY]` 并提交由 G 专家最终审查。
