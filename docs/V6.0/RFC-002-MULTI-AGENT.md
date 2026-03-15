# RFC-002: Multi-Agent Session Management

**Status**: Proposed
**Date**: 2026-02-15
**Author**: Antigravity (Agent)
**Target Version**: V6.1 (Initial Release Inclusion)

## 1. 背景 (Context)

随着 AI 辅助开发的普及，"Multi-Agent" 协作已成为趋势。在一个项目中，可能同时存在：
- **User**: 人类开发者 (手动执行 CLI)
- **Agent A**: IDE 内置 Agent (e.g. Copilot, Cline)
- **Agent B**: 独立运行的 Agent (e.g. Claude Code, Antigravity)

**需求**:
1.  **并发安全 (Concurrency Safety)**: 多个 Agent 同时启动 Session 时，不能发生 ID 冲突或文件覆盖。
2.  **身份识别 (Identity)**: 日志必须明确记录 "谁" 执行了操作。
3.  **上下文通畅 (Context Continuity)**: Agent B 应能看到 Agent A (或 User) 刚完成的工作，实现无缝接力。

## 2. 核心设计 (Core Design)

### 2.1 共享序列与原子锁 (Shared Sequence & Atomic Lock)

我们维持 **扁平化、基于时间的日志结构**，所有 Agent 共享同一个 Hex ID 序列 (`01`, `02`, ... `FF`)。

- **目录结构 (不变)**: `docs/logs/YYYY/MM-DD/`
- **文件命名 (不变)**: `XX-start.md`, `XX-end.md`

**并发控制机制**:
利用现有的 `FileLock` (`src/dimcause/utils/lock.py`) 实现原子化的 Session 创建：

1.  **Lock**: 获取 `session_creation` 锁 (Scope: Daily Directory)。
2.  **Scan**: 扫描当前目录，找到最大 Hex ID (e.g., `09`)。
3.  **Allocate**: 计算下一个 ID (`0A`)。
4.  **Reserve**: 立即创建空文件 `0A-start.md` (占位)。
5.  **Unlock**: 释放锁。
6.  **Write**: 写入完整的 YAML Frontmatter 和内容。

> **优势**: 保证了全局唯一性和大致的时序性，避免了复杂的分布式 ID 生成器。

### 2.2 Agent 身份识别 (Agent Identity)

引入环境变量 `DIMC_AGENT_ID` 来标识当前运行实体。

- **Default**: `user` (如果未设置)
- **Example**: `DIMC_AGENT_ID=antigravity`, `DIMC_AGENT_ID=claude-code`

**YAML Frontmatter 变更**:
在 `start.md` 和 `end.md` 中增加 `agent` 字段。

```yaml
---
id: "2026-02-15-0A"
type: session-start
agent: "antigravity"  # <--- NEW
created_at: "..."
---
```

### 2.3 全局上下文恢复 (Global Context Restoration)

`dimc up` (Context Restore) 的逻辑从 "恢复**我的**上一个会话" 变更为 "恢复**项目**的最新状态"。

- **逻辑**:
    1.  扫描 `docs/logs/YYYY/MM-DD/` (及前一天)。
    2.  按 `created_at` 倒序排列所有 `session-end` 日志（不分 Agent）。
    3.  读取 **最新的 N 个** `session-end` (e.g., Top 3)，聚合其 `Task Status` 和 `Achievements`。
    4.  生成 Prompt：“Project Context: User just finished X, Agent A finished Y...”

> **优势**: 实现了真正的协作。Agent B 启动时，能立即知道 Agent A 刚修好了一个 Bug，而不是仅仅看到自己的历史。

## 3. 实施计划 (Implementation Plan)

### Phase 1: 基础设施 (Inventory)
- [ ] 确保 `src/dimcause/utils/lock.py` 可用且健壮。
- [ ] 修改 `src/dimcause/core/config.py` 读取 `DIMC_AGENT_ID`。

### Phase 2: 并发改造 (Concurrency)
- [ ] 修改 `src/dimcause/core/state.py`:
    - `resolve_session_path` 增加 `with_lock` 保护。
    - 实现 "Reserve File" (占位) 逻辑。

### Phase 3: 上下文增强 (Context)
- [ ] 修改 `src/dimcause/cli.py` (`_rebuild_context`):
    - 读取并展示 `agent` 字段。
    - 聚合多源日志。

## 4. 风险 (Risks)

- **锁争用**: 如果 Agent 极其频繁地创建 Session (e.g. 每秒一个)，可能导致性能瓶颈。
    - *Mitigation*: Session 设计为 "工作单元" (15min - 数小时)，不仅仅是单次对话，争用概率极低。
- **文件系统延迟**: 在网络文件系统 (NFS) 上锁可能不可靠。
    - *Assumption*: 开发环境通常是本地文件系统。
