# DIMCAUSE (DIMCAUSE) 使用指南

> **5分钟快速上手，掌控工程上下文。**

## 🚀 1. 快速开始 (Quick Start)

### 安装
```bash
# 假设你已经克隆了仓库
pip install -e .
dimc --help
```

### 每日工作流 (The Loop)
DIMCAUSE 的核心理念是伴随你的工作流，而不是在大脑和代码之间切换。

1.  **早晨开工**:
    ```bash
    dimc daily-start
    ```
    *自动恢复昨天的上下文，创建今天的日志文件。*

2.  **工作中记录**:
    *   **快速记录想法**:
        ```bash
        dimc log "决定使用 SQLite 因为它无需服务器配置"
        ```
    *   **开始一个子任务**:
        ```bash
        dimc job-start "refactor-auth"
        ```

3.  **收工**:
    ```bash
    dimc daily-end
    ```
    *自动总结今天的工作，提取关键决策，并在 Git 中提交日志。*

---

## 🛠 2. 核心命令 (Core Commands)

### 🧠 记忆与提取 (Memory)

*   **`dimc extract file <path>`**
    *   **作用**: 利用 LLM (DeepSeek) 从 Markdown 日志中提取 "决策"、"失败尝试" 和 "设计思路"。
    *   **何时使用**: 当你写了一大段复杂的思考笔记后。

*   **`dimc extract diff <commit_range>`**
    *   **作用**: 分析代码变更，反向推导当时的工程决策。
    *   **何时使用**: 代码写完了但忘了记笔记时 (例如补录上周的工作)。

### 🔍 检索与回顾 (Retrieval)

*   **`dimc timeline`**
    *   **作用**: 显示上帝视角的工程时间轴。混合了 **Git 提交** 💾 和 **思维决策** 🧠。
    *   **示例**: `dimc timeline --limit 20`

*   **`dimc trace "<keyword>"`**
    *   **作用**: 追踪某个功能的完整生命周期。
    *   **示例**: `dimc trace "Auth Service"`
    *   **输出**: 关联了该功能相关的代码文件、设计决策和修改记录。

*   **`dimc why <file_path>`**
    *   **作用**: 询问 "为什么这个文件变成了现在这样？"
    *   **示例**: `dimc why src/config.py`
    *   **输出**: 基于历史事件生成的解释报告。

---

## 💡 3. 最佳实践 (Best Practices)

### ✅ Do (推荐)
*   **多用 `dimc log`**: 哪怕只是碎碎念。现在的噪音是未来的线索。
*   **按任务分组**: 使用 `dimc job-start` 和 `dimc job-end` 包裹复杂任务，这能让 `trace` 结果更精准。
*   **信任自动化**: 每天运行 `dimc daily-end`，让 AI 帮你整理和索引。

### ❌ Don't (避免)
*   **不要手动修改 Index**: 让 `EventIndex` 自动维护。
*   **不要提交 API Key**: 确保 `.env` 在 `.gitignore` 中 (DIMCAUSE 默认会帮你检查)。

## 📚 常见问题

**Q: 我的日志存储在哪？**
A: 本地 `docs/logs/` 目录。你是数据的主人。

**Q: 提取事件需要花钱吗？**
A: 如果配置了 OpenAI/Anthropic/DeepSeek API，会消耗少量 Token。本地 Ollama 则免费。
