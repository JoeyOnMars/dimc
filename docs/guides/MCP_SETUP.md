# Dimcause MCP 配置指南

将 Dimcause 启用为 Cursor 和 Claude Code 的记忆后端。

## 前置条件
确保已安装带 `mcp` 支持的 `dimcause`：
```bash
pip install -e ".[mcp]"
```

验证命令是否正常工作：
```bash
dimc mcp serve --help
```

## 1. Cursor 设置

1. 打开 **Cursor Settings** -> **Features** -> **MCP**。
2. 点击 **+ Add New MCP Server**。
3. 填写详情：
    - **Name**: `dimcause`
    - **Type**: `stdio`
    - **Command**: `/absolute/path/to/your/virtualenv/bin/dimc` (运行 `which dimc` 获取完整路径)
    - **Args**: `mcp serve`

> **注意**: 必须使用虚拟环境 (virtualenv) 内 `dimc` 可执行文件的绝对路径。

### 在 Cursor 中验证
1. 打开 Composer (`Cmd+I`)。
2. 输入: "检查我最近的 Dimcause 事件" (Check my recent Dimcause events)。
3. 验证 Cursor 是否成功调用了 `dimcause` 的 `get_recent_events` 工具。

## 2. Claude Code 设置

编辑 `~/Library/Application Support/Claude/claude_code_config.json`：

```json
{
  "mcpServers": {
    "dimcause": {
      "command": "/Users/yourname/path/to/.venv/bin/dimc",
      "args": ["mcp", "serve"]
    }
  }
}
```

## 可用工具 (Available Tools)
- **read_resource(`dimcause://events/recent`)**: 读取最近的审计日志。
- **call_tool(`add_event`)**: 将思考或对话记录到 Dimcause。
    - 示例: "Save this plan to Dimcause."
- **call_tool(`search_events`)**: 对历史事件进行语义搜索。
