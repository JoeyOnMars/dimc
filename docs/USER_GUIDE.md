# DIMCAUSE 用户指南

**状态**：当前有效
**定位**：说明当前仓库里已经落地的用户入口，包括 CLI、MCP 和本地工具接线。
**不包含**：未实现命令、历史阶段设计稿、平台化设想。

## 1. 当前可用的 3 类入口

1. **CLI**
   - 在终端执行 `dimc <command>`。
   - 适合会话管理、检索、分析、索引和本地维护。

2. **MCP**
   - 先运行 `dimc mcp serve`。
   - 然后由 Claude Code、Cursor 等 MCP 客户端通过自然语言调用当前已暴露的资源与工具。

3. **本地工具接线**
   - 通过 `dimc detect`、`dimc config enable`、`dimc config set` 把 Claude、Cursor、Windsurf、Continue.dev、Antigravity 等工具接到当前项目。
   - 后台 watcher 和 daemon 属于本地增强能力，不是独立平台。

## 2. CLI 常用命令

### 2.1 会话管理

| 命令 | 作用 | 典型场景 |
|:---|:---|:---|
| `dimc up` | 开工，恢复上下文 | 开始一天的开发 |
| `dimc down` | 收工，生成结束日志并执行收口流程 | 结束当前工作段 |
| `dimc job-start` | 开始一个具体任务 | 切入子任务 |
| `dimc job-end` | 结束一个具体任务 | 子任务收口 |

### 2.2 检索与分析

| 命令 | 作用 | 典型场景 |
|:---|:---|:---|
| `dimc search` | 搜索历史事件和材料 | 找以前的讨论、决策、记录 |
| `dimc timeline` | 看时间线 | 回顾最近发生了什么 |
| `dimc history` | 看文件或对象历史 | 追一个文件怎么演变成现在这样 |
| `dimc graph show` | 浏览图谱 | 看结构关系和依赖 |
| `dimc why` | 解释原因 | 问“为什么会有这次改动” |
| `dimc audit` | 做规则审计 | 提交前检查合规性 |
| `dimc trace` | 追踪变更链 | 看一个问题是怎么传导出来的 |

### 2.3 导入、索引与维护

| 命令 | 作用 | 典型场景 |
|:---|:---|:---|
| `dimc data-import <path>` | 导入本地目录或文件 | 批量导入历史材料 |
| `dimc index --rebuild` | 重建索引 | 索引失真或需要全量刷新 |
| `dimc scan` | 扫描敏感信息 | 发布前安全检查 |
| `dimc daemon start/status/stop` | 管理后台 daemon | 持续接收 watcher 数据 |
| `dimc detect` | 探测本机工具目录 | 准备接线 Claude/Cursor 等工具 |
| `dimc config enable <tool>` | 写入指定工具的最小配置 | 启用 watcher 或导出目录 |
| `dimc config set <key> <value>` | 细化配置键 | 手工修 watcher 路径或模型参数 |
| `dimc mcp serve` | 启动 MCP 服务 | 让 IDE / Agent 客户端接入 |

## 3. MCP 当前已暴露的能力

先启动：

```bash
dimc mcp serve
```

当前 live MCP 面包括：

### 3.1 资源

| 资源 | 作用 |
|:---|:---|
| `dimcause://events/recent` | 返回最近 20 条事件 |
| `dimcause://graph/summary` | 返回当前图谱概览和类型分布 |

### 3.2 工具

| 工具 | 作用 |
|:---|:---|
| `add_event` | 记录一条新事件 |
| `search_events` | 搜索事件 |
| `get_causal_chain` | 追某个事件或对象的因果链 |
| `audit_check` | 运行规则审计 |

## 4. 本地工具接线

### 4.1 工具探测

```bash
dimc detect
```

这一步只回答两件事：
1. 目录是否被探测到；
2. 当前实现是否支持启用。

### 4.2 启用工具

例如启用 Cursor：

```bash
dimc config enable cursor
```

例如启用 Antigravity 并显式指定导出目录：

```bash
dimc config enable antigravity --path ~/Documents/AG_Exports
```

### 4.3 细化配置

例如手工修改 Cursor watcher 路径：

```bash
dimc config set watchers.cursor.path "/custom/path"
```

例如手工修改 Continue.dev watcher 路径：

```bash
dimc config set watchers.continue.path "/custom/continue/sessions"
```

## 5. 当前 watcher / 本地接线边界

1. daemon 当前会初始化：
   - Claude watcher
   - Cursor watcher
   - Windsurf watcher
   - Continue.dev watcher
   - State watcher
2. Antigravity 当前通过 `export_dir` 接入导出目录，不属于 daemon 内部 watcher 列表。
3. Git 相关摄取属于导入/流水线能力，不是 daemon 当前公开的独立 watcher。

## 6. 配置文件

1. 当前项目配置文件名是 `.logger-config`。
2. 它是 JSON 文件，不是 TOML。
3. `dimc init` 会创建最小配置。
4. `dimc config enable` 和 `dimc config set` 会继续向这个文件写入工具接线配置。

## 7. 相关文档

1. 工具接线细节：
   - `docs/IDE_INTEGRATION.md`
2. MCP 接线：
   - `docs/guides/MCP_SETUP.md`
3. 当前项目状态与欠债：
   - `docs/STATUS.md`
   - `docs/dev/BACKLOG.md`
   - `docs/dev/V6.0_ROADMAP.md`

## 8. 维护规则

1. 只有在 CLI 命令面、MCP 暴露面或本地工具接线能力发生变化时，才更新本文。
2. 未来命令、伪代码模型、平台化设想和阶段草图，一律不进入这份 live 指南。
