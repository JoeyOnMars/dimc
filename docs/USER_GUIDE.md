# DIMCAUSE 用户指南 (User Guide)

**版本**: V6.2  
**状态**: ✅ Active  
**受众**: 最终用户 (开发者)

---

本指南为您列出 DIMCAUSE 系统的 **3 大核心入口**：命令行 (CLI)、IDE 插件 (MCP)、后台自动化 (Watchers)。

## 1. 命令行入口 (CLI Entry Points)
**操作方式**: 在终端运行 `dimc <command>`。

| 分类 | 常用命令 | 功能描述 | 典型场景 |
|:---|:---|:---|:---|
| **会话管理** | `dimc up` | **开工**。拉代码、查待办、恢复上下文 | 每天早上第一件事 |
| | `dimc down` | **收工**。生成日报、提交代码、导出记忆 | 每天下班最后一件事 |
| | `dimc job-start/end` | **任务切换**。开始/结束一个具体的 Agent 任务 | 切换上下文时 |
| **查询/检索** | `dimc search` | **语义搜索**。支持中文简繁混搜 | "搜一下之前的内存优化方案" |
| | `dimc timeline` | **看历史**。按时间线查看事件 | "回顾昨天的改动" |
| | `dimc history` | **查文件史**。查看某个文件的演变 | "这个文件怎么改成这样的" |
| | `dimc graph show` | **看图谱**。TUI 界面浏览因果图 | "宏观查看项目结构" |
| **深度分析** | `dimc why` | **问原因**。AI 分析代码变更的根本原因 | "为什么改了这几行代码？" |
| | `dimc audit` | **查合规**。检查是否违反开发规则 | "提交前自查" |
| | `dimc trace` | **追变更**。分析代码修改路径 | "追踪 bug 是哪里引入的" |
| **维护/工具** | `dimc index --rebuild` | **重建索引**。强制刷新知识库 | 发现搜不到最新内容时 |
| | `dimc scan` | **安全扫描**。检查敏感信息 (Key/Secret) | 定期安全检查 |
| | `dimc mcp serve` | **启动服务**。供 Claude/Cursor 连接 | 让 IDE 变聪明 |

---

## 2. IDE / Agent 入口 (MCP Protocol)
**操作方式**: 在 Claude Desktop / Cursor 中直接用自然语言提问。你需要先运行 `dimc mcp serve`。

| 工具名称 (Tool) | 你问 Agent 的话 (Prompt) | Agent 实际干的事 | 返回结果 |
|:---|:---|:---|:---|
| `search_events` | "搜一下最近关于数据库的讨论" | 语义搜索 Vector Store | 相关事件列表 (含时间、摘要) |
| `get_recent_events` | "我最近都做了什么？" | 查询最新 20 条记录 | 时间线摘要 |
| `get_causal_chain` | "这个 commit 是因为什么？" | 追溯因果图谱 (GraphStore) | 上游决策 -> 下游变更链条 |
| `audit_check` | "检查一下最近的改动合规吗？" | 运行公理验证器 (Validator) | ✅ 通过 / ❌ 违规项列表 |
| `get_graph_context`| (Agent 自动调用) | 获取当前实体的上下文 | 邻居节点信息 |
| `add_event` | "帮我记一下这个想法..." | 写入 Markdown + 索引 | "Event logged: evt_123" |

---

## 3. 自动化入口 (Watchers)
**操作方式**: **无**。后台静默运行，你只需要 "做你的事"。

| Watcher 名称 | 监听对象 | 触发条件 | 自动生成的数据 |
|:---|:---|:---|:---|
| **StateWatcher** | 文件系统 | 文件保存 (`Ctrl+S`) | "File Modified: src/main.py" |
| **GitImporter** | Git 仓库 | `git commit` | "Commit: fix bug (Hash: abc123)" |
| **ExportWatcher**| 导出目录 | 发现新 `.json/.md` 导出文件 | "Conversation: Refactoring Plan" |

---

## 4. 导入外部数据 (Import Data)
**操作方式**: `dimc data-import <path>`

用于将现有的本地文档、代码库或资料库（非 Git 托管内容）批量导入到 Dimcause 记忆中。

| 命令 | 说明 | 支持格式 |
|:---|:---|:---|
| `dimc data-import ./docs` | 递归导入 `docs` 目录下的所有文件 | `.md`, `.txt`, `.pdf`, `.docx`, `.pptx`, `.html` |
| `dimc data-import file.pdf` | 导入单个文件 | 同上 |

> [!TIP]
> 导入的数据会立即被 **各种索引器 (Indexer)** 处理：
> 1. **MarkdownStore**: 存储原始内容
> 2. **VectorStore**: 生成向量嵌入 (Embeddings) 用于语义搜索
> 3. **GraphStore**: (部分文本) 提取实体关系

---

## 5. 交互流程图 (User Interaction Flow)

该图展示了数据在您的开发环境与 Dimcause 核心之间的流转路径。

```mermaid
graph TD
    User((User))

    subgraph CLI ["CLI 终端 (Terminal)"]
        Session["会话管理 (up/down)"]
        Query["查询与分析 (search/why)"]
        Audit["合规审计 (audit)"]
    end

    User --> Session
    User --> Query
    User --> Audit

    subgraph IDE ["IDE (VS Code / Cursor)"]
        Editor["编辑器"]
        StateWatcher["StateWatcher"]
        Git["Git 系统"]
        GitImporter["GitImporter"]
        MCP_Client["MCP 客户端"]
        MCP_Server["MCP Server"]
    end

    User -->|写代码| Editor
    Editor -.->|自动保存| StateWatcher
    User -->|Git Commit| Git
    Git -.->|Post-commit| GitImporter
    
    User -->|@dimcause 提问| MCP_Client
    MCP_Client <-->|MCP 协议| MCP_Server

    subgraph Core ["Dimcause Core"]
        Engine["核心引擎"]
    end

    Session --> Engine
    Query --> Engine
    Audit --> Engine
    StateWatcher --> Engine
    GitImporter --> Engine
    MCP_Server <--> Engine
    
    style User fill:#e1f5fe
    style MCP_Server fill:#fff9c4
```
