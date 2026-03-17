# IDE 与 AI 工具集成指南

**状态**：当前有效
**定位**：说明当前仓库里已经落地的工具探测、项目配置写入和 watcher 接线能力。
**不包含**：未实现的同步命令、伪代码配置模型、未来平台化设想。

## 1. 当前已落地的能力

1. `dimc init`
   - 在项目根目录创建 `.logger-config`。
   - 当前工具集成配置也写入这个文件。
2. `dimc detect`
   - 探测本机常见 AI 开发工具目录。
   - 只报告“是否检测到”和“当前是否支持启用”。
3. `dimc config enable <tool>`
   - 把指定工具的最小配置写入当前项目的 `.logger-config`。
4. `dimc config set <key> <value>`
   - 细化修改项目配置，例如 watcher 路径。
5. watcher 运行面
   - 当前 daemon 已能挂载 Claude、Cursor、Windsurf、Continue.dev watcher。
   - Antigravity 当前通过 `export_dir` 接入导出目录。

## 2. 当前工具支持边界

以下边界以当前代码为准：

1. **Claude Code**
   - 工具键：`claude`
   - 当前支持：`detect` + `config enable` + watcher
   - 默认探测路径：`~/.claude/history.jsonl`

2. **Cursor**
   - 工具键：`cursor`
   - 当前支持：`detect` + `config enable` + watcher
   - 默认探测路径优先级：
     - `~/.cursor/logs`
     - `~/Library/Application Support/Cursor/logs`
     - `~/.config/Cursor/logs`
     - `%APPDATA%/Cursor/logs`

3. **Windsurf**
   - 工具键：`windsurf`
   - 当前支持：`detect` + `config enable` + watcher
   - 默认探测路径优先级：
     - `~/.windsurf/logs`
     - `~/Library/Application Support/Windsurf/logs`
     - `~/.config/Windsurf/logs`
     - `%APPDATA%/Windsurf/logs`
     - `~/.codeium/windsurf/logs`

4. **Continue.dev**
   - 工具键：`continue_dev`
   - 当前支持：`detect` + `config enable` + watcher
   - 默认探测路径：
     - `~/.continue/sessions`
     - `%USERPROFILE%/.continue/sessions`

5. **Antigravity**
   - 工具键：`antigravity`
   - 当前支持：`detect` + `config enable`
   - 配置落点：项目 `.logger-config` 中的 `export_dir`
   - 默认目录：
     - 环境变量 `DIMCAUSE_EXPORT_DIR`
     - 否则 `~/Documents/AG_Exports`

6. **GitHub Copilot Chat**
   - 工具键：`copilot_chat`
   - 当前支持：**仅 detect，不支持 enable**
   - 原因：代码里还没有对应 watcher 实现。

## 3. 项目配置文件

1. 当前项目配置文件名是 `.logger-config`。
2. 它是 JSON 文件，不是 TOML。
3. `dimc init` 会创建最小配置。
4. `dimc config enable` 和 `dimc config set` 会继续往这个文件写入工具相关字段。

## 4. 最小使用方式

### 4.1 初始化项目配置

```bash
dimc init
```

执行后会在当前项目根目录创建：

```text
.logger-config
```

### 4.2 检测本机可接入工具

```bash
dimc detect
```

这一步只回答两件事：
1. 目录是否被探测到
2. 当前实现是否支持启用

### 4.3 启用一个已支持的工具

例如启用 Cursor：

```bash
dimc config enable cursor
```

例如启用 Antigravity 并显式指定导出目录：

```bash
dimc config enable antigravity --path ~/Documents/AG_Exports
```

### 4.4 细化修改配置键

例如手工修改 Cursor watcher 路径：

```bash
dimc config set watchers.cursor.path "/custom/path"
```

例如手工修改 Continue.dev watcher 路径：

```bash
dimc config set watchers.continue.path "/custom/continue/sessions"
```

## 5. 当前配置键映射

以下写法会被正规化到当前项目配置：

1. `watchers.cursor.path` → `watcher_cursor.path`
2. `watchers.claude.path` → `watcher_claude.path`
3. `watchers.windsurf.path` → `watcher_windsurf.path`
4. `watchers.continue.path` / `watchers.continue_dev.path` → `watcher_continue_dev.path`
5. `watchers.antigravity.path` → `export_dir`

## 6. 当前不应宣称的能力

以下内容当前**没有**作为稳定 CLI 能力落地，不应再写进共享指南：

1. `dimc sync ...`
2. `dimc config show`
3. `dimc config reset`
4. `dimc config add-custom`
5. “WatchersConfig” 这类未落地的数据模型伪代码
6. 把 Claude Desktop 导出目录说成当前唯一接入路径

## 7. 与 MCP 的关系

1. 本文解决的是 watcher / export_dir / 项目配置接线。
2. MCP 配置是另一条线。
3. Cursor 和 Claude Code 的 MCP 接入，请看：
   - `docs/guides/MCP_SETUP.md`

## 8. 维护规则

1. 只有在 `dimc detect`、`dimc config enable`、`dimc config set` 或实际 watcher 支持发生变化时，才更新本文。
2. 研究性猜想、未来命令和伪代码，一律放到 `docs/research/` 或 RFC，不进入这份 live 指南。
