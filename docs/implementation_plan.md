# 日志命名与架构重构计划 (v3)

## 核心原则 (Core Principle)
**一个会话 (Session) = 一个原子单元。**
无论会话何时结束，其所有产出（Start Log, End Log, Job Logs）都必须存放在**会话启动时**创建的目录中。

## 命名规范 (Naming Convention)

### **Hexadecimal (16进制) 序列号**
- **格式**: `XX-start.md` (2位 16进制，大写)
- **范围**: `01` ... `09` -> `0A` ... `0F` -> `10` ... `FF` (支持单日 255 个会话)
- **排序安全性**: **完全安全**。
  - 计算机使用 ASCII 排序：数字 `0-9` (ASCII 48-57) 小于 字母 `A-F` (ASCII 65-70)。
  - 顺序保证：`09` < `0A` < `0F` < `10`。
  - 搜索兼容性：`0A` 是标准字符串，不会触发特殊字符问题（不同于 `\n`）。

### 2.5 验证
- [x] 验证 Hex 序列生成逻辑 (`tests/verify_hex.py`).
- [ ] 验证跨午夜场景
- [ ] 验证恢复提示词生成

### 场景规范 (Scenario Specs)

#### 跨午夜场景 (The Midnight Crossing)
- **Start**: 2026-02-14 23:00 -> 创建 `docs/logs/2026/02-14/0A-start.md`
- **End**: 2026-02-15 02:00 -> **必须创建于 `docs/logs/2026/02-14/0A-end.md`**

### 日志头部规范 (Header Specs)
**标准**: 使用 YAML Frontmatter (被 Jekyll, Obsidian, Hugo 等广泛支持)。
**新增字段**:
```yaml
---
id: "2026-02-14-0A"                # 唯一 Session ID (YYYY-MM-DD-HEX)
type: "daily-start"                # 类型 (daily-start, daily-end, job-start)
created_at: "2026-02-14T23:00:00+08:00" # ISO 8601 精确时间戳 (用于搜索/排序)
status: "active"                   # 状态
---
```
> **优势**: ISO 时间戳天然可排序，ID 唯一标识会话，YAML 格式通用且易于机器解析。

### Context Restoration (上下文恢复机制)
**设计变更**: 移除 `end.md` 尾部的硬编码提示词。
**新逻辑 (Reader-Generator Pattern)**:
1.  **Session A 结束**: `dimc daily-end` 生成纯净的 `end.md` (只包含结构化事实：Diff, Tasks, Decisions)。
2.  **Session B 开始**: 用户执行 `dimc daily-start`。
3.  **动态生成**: 命令会自动读取上一个 Session 的 `end.md`，并在**终端输出** (或写入临时文件)一段构建好的 Recovery Prompt。

> **优势**: `end.md` 保持纯净 (Single Source of Truth)，避免了“文件内容”与“文件内的提示词”不一致的风险。恢复逻辑由代码控制，随版本迭代。

## 代码变更 (Code Changes)

## 代码变更 (Code Changes)

### [MODIFY] [src/dimcause/core/state.py](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/core/state.py)

#### 1. `get_log_path()` 逻辑增强
- **Sequence Generation**:
    - 扫描当前目录所有 `[0-9A-F]{2}-start.md`。
    - 解析最大 Hex 值，+1，格式化为 `{:02X}`。
- **End Path Resolution**:
    - 查找当前活跃 Session 的 `start` 文件路径。
    - 保持相同的 Hex 序号。

#### 2. `get_active_session()` (新增)
- 扫描最近 24-48 小时内的文件夹。
- 寻找有 `XX-start.md` 但没有 `XX-end.md` 的最新会话。

### [MODIFY] [src/dimcause/cli.py](file:///Users/mini/projects/GithubRepos/dimc/src/dimcause/cli.py)

#### `daily-end` 命令
- **新逻辑**: 
    1. 调用 `get_active_session()`。
    2. 如果找到活跃会话 (e.g. `02-14/0A-start.md`) -> 在同目录下写入 `0A-end.md`。
    3. 如果未找到 -> 降级为在今日目录写入 `01-end.md`。

## 验证计划
1. **Mock 测试**: 模拟 Hex 序列递增 (`09` -> `0A`)，验证文件名生成正确。
2. **跨天测试**: 模拟跨午夜写入，确保目录不漂移。
