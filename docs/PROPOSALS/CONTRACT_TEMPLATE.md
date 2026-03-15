# Task XXX Contract: [任务简称] ([优先级如 P0 Architecture])

**risk_level: [high/medium/low]**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
[G 专家填空：说明为什么要改这个，以及目前系统里的真理源是什么状态]

## 2. 详细设计 (Detailed Design)
[G 专家填空：如何改。精确到函数模块与依赖。]

## 3. 物理边界与授权范围 (Scope Exclusivity)
[G 专家填空：明确列出“允许修改的文件”，甚至列出“严禁触碰的文件”]

## 4. 测试与验证期望 (Acceptance Criteria)
[G 专家填空：如何验收。例如：局部的增量 pytest 指令是什么]

## 5. 🛡️ G 专家 (Antigravity) 审计交接门禁 (AUDIT HANDOVER GATE)
> 🚨🚨 **G专家警告：你必须强制执行以下红线，否则视为渎职违规！** 🚨🚨
当收到 M 专家的 `[PR_READY]` 后，你在出具 `task_xxx_audit.md` 前，**必须**：
1. **环境纪律复核**: 进入 `.venv`，强制运行 `scripts/check.zsh`。必须 0 error，否则打回 M 专家，绝不开恩代为修改！
2. **加载最高指挥官的 Checklist**: 你必须去读取并逐项验证 `docs/dev/PHASE2_AUDIT_CHECKLIST.md` 中的设计合规、测试防线、代码卫生。
3. **移交权柄**: 最后向 User 汇报结果，等待 User 盖章 Checklist 后，由 User 或 User 明确授权方可 `git merge`。

## 6. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)
> 🚨🚨 **M专家警告：以下为物理隔离铁律！** 🚨🚨
一旦看到本契约获得 User 盖章的 `Approved/已确认`，你必须**严格按顺序**执行以下起手式，否则视为最高级别违规：

1. **绝对禁止**在 `main` 涂鸦，立刻新开分支：
   ```bash
   git switch main && git pull
   git switch -c feat/task-XXX-[简短名称]
   ```
2. （仅限授权范围）执行第一行代码修改。
3. （完成修改后）立刻 Commit 并原生 Push：
   ```bash
   git commit -m "feat: [简短说明]"
   git push -u origin HEAD
   ```
4. 运行**局部核心受影响**的测试，确保通过：
   > 🛑 **严禁**执行无过滤的全局测试（如 `pytest tests/`），你必须精确到模块级别，防止触碰历史技术债隔离区导致暴走。
   > **本契约唯一合法的测试指令为：**
   > `[G专家填空：如 pytest tests/模块/test_文件.py -v]`
5. 输出 `[PR_READY]` 呼叫 G 专家。
