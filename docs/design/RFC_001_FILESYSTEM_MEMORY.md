# RFC 001: 文件系统即记忆 (File-System as Memory)

> **状态**: Draft
> **日期**: 2026-02-17
> **设计人**: User (Input), Dimcause Arch (Synthesis)
> **目标**: 解决上下文窗口限制与记忆丢失问题，从 "静态注入" 转向 "动态文件发现"。

## 1. 核心问题 Definition

**"The Context Handover Problem"**

- **现状 (Static Injection)**:
  - Agent 启动时，`context_loader`（如 OpenClaw/Dimcause Current）将 `MEMORY.md` 和最近日志一次性塞入 Context Window。
  - **缺陷**:
    1.  **Token 浪费**: 加载了无关信息。
    2.  **压缩破坏性**: 当 Window 满时，压缩操作清除 Token，Agent 彻底失去对旧信息的访问能力（无法回溯）。
    3.  **盲目继承**: Agent 不知道当前上下文里有什么，是被动接受者。

- **目标 (Dynamic Discovery)**:
  - **"Everything is a file"**: 将记忆、工具、知识统一为文件系统。
  - **Agent 主动性**: Agent 拥有 `ls`, `read`, `search` 权限，按需加载。
  - **持久化**: 即使 Context Window 重置，文件依然在磁盘上，Agent 随时可以重新 `read`。

## 2. 统一命名空间设计 (/context/*)

所有上下文映射到一个可预测的虚拟/物理文件系统：

```bash
/context/
├── history/            # 不可变交互日志 (Truth Timeline)
│   ├── 2026-02-17.log
│   └── ...
├── memory/
│   ├── episodic/       # [情景记忆] 会话限时的摘要 (Session Summaries)
│   ├── fact/           # [事实记忆] 原子性持久条目 (Preferences, Decisions, Constraints)
│   │   ├── user_profile.md
│   │   └── project_rules.md
│   └── user/           # [用户记忆] 个人属性跟踪
├── pad/                # [草稿工作区] 临时笔记 (Scratchpad)，可升级为 Memory 或丢弃
├── tools/              # 工具元数据与定义
└── sessions/           # 会话工件 (Artifacts)
```

## 3. 记忆生命周期 (The Lifecycle)

不再是简单的二元划分 ("Today" vs "Permanent")，而是三层流动：

1.  **草稿 (Draft)**: 存放在 `/context/pad/`。Agent 思考过程、临时尝试。
2.  **情景 (Episodic)**: 存放在 `/context/memory/episodic/`。任务完成后的 Event Summary。
3.  **事实 (Fact)**: 存放在 `/context/memory/fact/`。经过验证、多次确认的知识（如 "用户喜欢深色模式"）。

**流转机制**:
- Agent 运行时在 Pad 记录。
- 任务结束时压缩为 Episodic。
- `Reflector` (反思进程) 定期将高频 Episodic 提取为 Fact。

## 4. 交互模式变革

### Before (Push Model)
```python
# System Start
context = load_files(["MEMORY.md", "today.log"])
agent.run(context) 
# 如果 context > window，直接截断
```

### After (Pull Model)
```python
# System Start
agent.run(system_prompt="You have access to /context. Use tools to explore.")

# Agent Turn 1
Agent: "ls /context/memory/fact"
System: ["user_profile.md", "project_rules.md"]

# Agent Turn 2
Agent: "read /context/memory/fact/user_profile.md"
System: (Content of profile)

# Agent Turn 3
Agent: "Think: I need to know about API keys. search 'api key' in /context"
```

## 5. 审计与清单 (Manifest)

为了解决 "静默失败" (Silent Failure)，每次推理回合需生成 **Context Manifest**：

- **Loaded**: 本回合读取了哪些文件？(`read /context/fact/rules.md`)
- **Excluded**: 搜索到了但没读哪些？
- **Reason**: 为什么选这些？

## 6. 迁移路径 (Migration Path)

1.  **Step 1**: 实现 `ContextFS` 抽象层，将现有 `docs/`, `logs/` 映射到 `/context/` 虚拟路径。
2.  **Step 2**: 赋予 Agent `list_context`, `read_context` 工具。
3.  **Step 3**: 停止启动时全量注入，仅注入目录结构引导。
4.  **Step 4**: 拆分 `MEMORY.md` 为 `fact/` 小文件。

---
> **核心价值**: 记忆拥有了物理实体（文件），不再依赖脆弱的上下文窗口。
