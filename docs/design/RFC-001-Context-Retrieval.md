# RFC-001: 会话上下文检索策略与局限性 (Session Context Retrieval Strategy & Limitations)

## 1. 摘要 (Summary)
本 RFC 记录了关于从 IDE 内存/GUI 中自动检索完整会话历史 (Session Context) 的可行性技术分析，以及最终决定采用基于手动导出的 "智能扫描" (Smart Scan) 方案的决策过程。

## 2. 问题陈述 (Problem Statement)
`dimc` CLI Agent 运行在一个受限的进程能力范围内。它缺乏直接访问 IDE (Gemini/Antigravity) 内部内存或操作系统 GUI 层的权限。然而，用户需要一种无缝的方式将完整的会话上下文归档到项目的 `docs/logs` 目录中，而无需繁琐的手动操作 (例如重命名文件、手动复制)。

## 3. 技术约束 (Technical Constraints)

### 3.1 进程隔离 (Process Isolation)
- **Agent 环境**: 作为容器化或受限用户空间内的子进程 (shell/python) 运行。
- **IDE 环境**: 作为独立的宿主进程运行，将会话状态对象保存在 RAM 中。
- **障碍**: 现代操作系统的进程隔离机制阻止 Agent 读取 IDE 的内存空间。IDE 没有公开 API 供程序调用以将当前聊天记录 "转储" (dump) 到磁盘文件。

### 3.2 GUI 隔离 (GUI Isolation)
- Agent 无法访问宿主操作系统的窗口管理器。
- 它无法模拟鼠标点击或键盘事件来触发 IDE 的 "Export" 按钮，也无法滚动聊天窗口进行 OCR/爬取。
- 浏览器工具仅限于控制一个 *新的* 无头浏览器实例，而不是 *宿主* IDE 窗口。

### 3.3 文件系统可见性 (File System Visibility)
- 对 `.gemini/antigravity/brain/...` 的调查显示，对话期间没有实时日志 (例如 `current_session.log`) 写入磁盘。
- 在显式触发导出之前，IDE 可能使用加密数据库或纯内存结构。

## 4. 提议方案: 智能扫描 (Smart Scan)

鉴于我们无法绕过 "Export" 按钮的点击 (物理安全密钥)，我们将优化点击 *之后* 的所有流程。

### 4.1 工作流 (The Workflow)
1.  **用户操作**: 用户在 IDE 中点击 "Export to Markdown"。
2.  **系统操作**: 执行 `dimc down`。
3.  **智能扫描逻辑**:
    -   **锚点**: 从 `docs/logs/.../01-start.md` 读取 `session_start_time`。
    -   **发现**: 扫描配置的导出目录（默认 `~/Documents/AG_Exports/*.md`）。
    -   **过滤**: 选择 `mtime >= session_start_time` 的文件。
    -   **摄取**: 自动将内容复制到 `docs/logs/YYYY/MM-DD/XX-end.md`。

### 4.2 权衡 (Trade-offs)
- **优点**:
    - 100% 可靠性 (用户验证内容)。
    - 零 "幻觉" (数据来自源头)。
    - 在当前权限下技术上可行。
- **缺点**:
    - 每通过一次会话需要 1 次手动点击。

## 5. 决策 (Decision)
我们将 **不** 尝试 Hack/逆向工程 IDE 内存或 GUI。我们将实施 **Task 2.0 (智能扫描)** 作为 V6.0 的标准解决方案。

---

## 6. 改进: 两阶段 `dimc down` (Two-Phase Down)

> 2026-02-18 补充。解决导出文件缺少内嵌时间戳、Smart Scan 只能依赖 mtime 的局限性。

### 6.1 问题分析

1.  Antigravity 导出的 `.md` 文件**不包含**标准时间戳 (`YYYY-MM-DD HH:MM:SS`)。
2.  `log_parser.extract_log_time_range()` 无法从导出文件中提取对话起止时间，只能 fallback 到 `mtime`。
3.  当前 `dimc down` 是**一次性执行**：先生成 `end.md`，再扫描导出文件。但用户需要在 `down` 过程中**暂停导出对话**，导致时序冲突。

### 6.2 方案: 两阶段执行

将 `dimc down` 拆分为两个阶段：

```
阶段 1 (标记 + 暂停)
├── 记录 end_timestamp = datetime.now()
├── 写入 end_timestamp 到 start.md 或临时状态文件
├── 打印: "⏱️ Session End: 2026-02-18 15:00:34"
├── 打印: "📤 请现在导出对话到 AG_Exports，然后按 Enter 继续..."
└── ⏸️ 等待用户按 Enter

阶段 2 (归纳 + 提取)
├── Smart Scan: 用 [start_timestamp, end_timestamp] 窗口精确匹配导出文件
├── 提取事件 (EventExtractor)
├── 更新索引 (EventIndex)
├── 生成 end.md (含会话总结)
├── Job 摘要注入
└── Git commit (可选)
```

### 6.3 时间窗口匹配逻辑

```python
# 精确匹配: start_time <= file.mtime <= end_time + tolerance
session_window = (session.start_time, end_timestamp + timedelta(minutes=5))

for log_file in ag_exports.glob("*.md"):
    if session_window[0].timestamp() - 3600 <= log_file.stat().st_mtime <= session_window[1].timestamp():
        # 候选文件
        candidates.append(log_file)
```

### 6.4 时序保证

| 步骤 | 时间 | 动作 |
|:---|:---|:---|
| T0 | 12:50 | `dimc up` → 记录 `start_timestamp` |
| T1 | 15:00 | `dimc down` Phase 1 → 记录 `end_timestamp` |
| T2 | 15:01 | 用户点击 "Export to Markdown" → 文件 mtime ≈ T2 |
| T3 | 15:02 | 用户按 Enter → Phase 2 开始 |
| 匹配 | - | `T0 - 1h <= mtime(T2) <= T1 + 5min` ✅ |

## 7. 实现计划 (下一个 Session)

### 7.1 修改文件清单

| 文件 | 改动 |
|:---|:---|
| `src/dimcause/cli.py` (`down()`) | 拆分为 Phase 1 / Phase 2，中间插入 `input()` 暂停 |
| `src/dimcause/core/state.py` | 新增 `record_session_end_timestamp()` 方法 |
| `src/dimcause/extractors/log_parser.py` | 优化 `extract_log_time_range()` 增加对路径引用中日期的过滤 |

### 7.2 验收标准

- [ ] `dimc down` 执行后，在 Phase 1 暂停并等待用户输入
- [ ] 暂停期间用户导出对话，按 Enter 后 Phase 2 正确扫描到导出文件
- [ ] `end.md` 包含精确的 `start_time` 和 `end_time`
- [ ] Smart Scan 使用时间窗口而非仅 mtime 进行匹配
