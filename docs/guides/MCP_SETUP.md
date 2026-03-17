# DIMCAUSE MCP 配置指南

**状态**：当前有效
**定位**：说明当前仓库里已经落地的 MCP 服务启动方式、真实暴露面和最小接入方法。
**不包含**：客户端私有配置文件路径猜测、未核实的 UI 操作细节、未实现端点。

## 1. 前置条件

1. 安装当前项目：

```bash
pip install -e .
```

2. 验证命令可用：

```bash
dimc mcp serve --help
```

当前 live 命令支持：
- `stdio`（默认）
- `http`（`--transport http`，监听 `127.0.0.1:14243`）
- 非法 `--transport` 会直接报错，不再静默退回默认模式

## 2. 当前服务端启动方式

### 2.1 stdio 模式

适合大多数 MCP 客户端。

```bash
dimc mcp serve
```

或显式写法：

```bash
dimc mcp serve --transport stdio
```

### 2.2 HTTP 模式

适合需要通过本地 HTTP 端口接入的客户端或调试场景。

```bash
dimc mcp serve --transport http
```

当前端口固定为：

```text
http://127.0.0.1:14243
```

## 3. 当前真实暴露面

以下内容以 [`../../src/dimcause/protocols/mcp_server.py`](../../src/dimcause/protocols/mcp_server.py) 为准。

### 3.1 资源

1. `dimcause://events/recent`
   - 返回最近 20 条事件摘要

2. `dimcause://graph/summary`
   - 返回当前图谱概览和类型分布

### 3.2 工具

1. `add_event`
   - 记录新事件

2. `search_events`
   - 对历史事件做语义搜索

3. `get_causal_chain`
   - 追某个事件或对象的因果链

4. `audit_check`
   - 运行规则审计

## 4. 最小客户端接入方式

### 4.1 stdio 客户端示例

如果客户端要求填写命令和参数，最小接入方式是：

```json
{
  "name": "dimcause",
  "command": "/absolute/path/to/venv/bin/dimc",
  "args": ["mcp", "serve"]
}
```

说明：
1. `command` 应使用当前虚拟环境里的 `dimc` 绝对路径。
2. 本文只给出可验证的命令参数，不宣称某个客户端的私有配置文件路径。

### 4.2 HTTP 客户端示例

如果客户端支持 MCP over HTTP，可先手工启动服务：

```bash
dimc mcp serve --transport http
```

再在客户端中指向：

```text
http://127.0.0.1:14243
```

## 5. 最小验证方式

接入后，至少验证以下两项：

1. 读取资源 `dimcause://events/recent`
2. 调用工具 `audit_check`

如果这两项正常，说明：
1. 服务进程已成功启动；
2. 客户端能读资源；
3. 客户端能调工具。

## 6. 与其他文档的边界

1. 当前 watcher / export_dir / `.logger-config` 接线，请看：
   - [`../IDE_INTEGRATION.md`](../IDE_INTEGRATION.md)

2. 当前用户入口总览，请看：
   - [`../USER_GUIDE.md`](../USER_GUIDE.md)

## 7. 维护规则

1. 只有当 `dimc mcp serve` 的参数、传输方式、资源或工具发生变化时，才更新本文。
2. 客户端私有配置路径、截图式教程和第三方 UI 步骤不写进本文；需要时单独引用客户端官方文档。
