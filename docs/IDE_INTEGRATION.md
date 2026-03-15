# IDE & CLI 集成指南

**版本**: V6.2  
**创建日期**: 2026-02-15  
**状态**: ✅ Active

---

## 概述

DIMCAUSE 支持多种 AI 辅助开发工具的自动集成，通过预设常见工具的对话历史路径，实现零配置或最小配置的自动数据捕获。

> **Superset 优势**: 不同于传统笔记工具需要手动复制粘贴，Dimcause 作为一个 **"DevOps 侧的 Second Brain"**，直接挂载到你的生产力流水线上，自动捕获上下文。


---

## 支持的工具列表

### 1. Cursor

**类型**: IDE  
**官网**: cursor.sh  
**自动化程度**: ✅ 100%自动

#### 默认路径配置

| 平台 | 对话历史路径 |
|------|-------------|
| macOS | `~/.cursor/history/` |
| Linux | `~/.cursor/history/` |
| Windows | `%APPDATA%\Cursor\history\` |

#### 文件格式
```json
{
  "id": "chat_xxx",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "timestamp": "2026-02-15T00:00:00Z"
}
```

#### 配置示例
```toml
# ~/.dimcause/config.toml
[watchers.cursor]
enabled = true
path = "~/.cursor/history/"
file_pattern = "*.json"
debounce_seconds = 1.0
```

---

### 2. Claude Code (CLI)

**类型**: Desktop App  
**官网**: claude.ai  
**自动化程度**: ⚠️ 部分自动（需配置导出）

#### Claude Desktop (GUI) 默认路径配置

| 平台 | 对话历史路径 |
|------|-------------|
| macOS | `~/Library/Application Support/Claude/conversations/` |
| Linux | `~/.config/Claude/conversations/` |
| Windows | `%APPDATA%\Claude\conversations\` |

#### 文件格式
```json
{
  "uuid": "conversation_xxx",
  "name": "Project Discussion",
  "created_at": "2026-02-15T00:00:00Z",
  "chat_messages": [...]
}
```

#### 配置示例
```toml
[watchers.claude_code] # 这里的命名需注意：实际监控的是 Desktop 版导出
enabled = true
path = "~/Library/Application Support/Claude/conversations/"
file_pattern = "*.json"
debounce_seconds = 2.0
```

**注意**: Claude Code 主要通过 MCP 协议集成。
请参考 [MCP 配置指南](./guides/MCP_SETUP.md) 进行配置。

对于 Claude Desktop (GUI App)，默认不导出，需要：
1. 设置 → Conversations → Enable auto-export
2. 或手动点击 "Export Conversation"

---

### 3. Antigravity (Google DeepMind)

**类型**: IDE Extension  
**官网**: deepmind.google/antigravity  
**自动化程度**: ⚠️ 手动导出

#### 默认路径配置

| 平台 | 导出目标路径 |
|------|-------------|
| macOS | `~/Documents/AG_Exports/` (用户自定义) |
| Linux | `~/Documents/AG_Exports/` (用户自定义) |
| Windows | `%USERPROFILE%\Documents\AG_Exports\` |

#### 文件格式
```markdown
# Conversation Export

Date: 2026-02-15
ID: conv_xxx

## Messages

**User**: ...
**Assistant**: ...
```

#### 配置示例
```toml
[watchers.antigravity]
enabled = true
path = "~/Documents/AG_Exports/"
file_pattern = "*.md"
debounce_seconds = 1.0
```

**工作流程**:
1. 对话结束后，点击 "Export Conversation"
2. 保存到配置的导出目录
3. ExportWatcher 自动检测并处理

---

### 4. Windsurf (Codeium)

**类型**: IDE  
**官网**: codeium.com/windsurf  
**自动化程度**: ✅ 100%自动

#### 默认路径配置

| 平台 | 对话历史路径 |
|------|-------------|
| macOS | `~/.windsurf/history/` |
| Linux | `~/.windsurf/history/` |
| Windows | `%APPDATA%\Windsurf\history\` |

#### 配置示例
```toml
[watchers.windsurf]
enabled = true
path = "~/.windsurf/history/"
file_pattern = "*.json"
debounce_seconds = 1.0
```

---

### 5. GitHub Copilot

**类型**: IDE Extension  
**官网**: github.com/features/copilot  
**自动化程度**: ❌ 不支持（无对话历史）

**说明**: Copilot 主要是代码补全，不提供对话历史导出。如果是 Copilot Chat，可尝试：

#### VS Code + Copilot Chat
```toml
[watchers.copilot_chat]
enabled = true
path = "~/.vscode/copilot_chat/"
file_pattern = "*.json"
```

---

### 6. Continue.dev

**类型**: VS Code Extension  
**官网**: continue.dev  
**自动化程度**: ✅ 100%自动

#### 默认路径配置

| 平台 | 对话历史路径 |
|------|-------------|
| macOS | `~/.continue/sessions/` |
| Linux | `~/.continue/sessions/` |
| Windows | `%USERPROFILE%\.continue\sessions\` |

#### 配置示例
```toml
[watchers.continue_dev]
enabled = true
path = "~/.continue/sessions/"
file_pattern = "*.json"
debounce_seconds = 1.0
```

---

## 配置系统设计

### 配置文件结构

**路径**: `~/.dimcause/config.toml`

```toml
[general]
data_dir = "~/.dimcause"
auto_detect_tools = true  # 自动检测已安装的工具

[watchers]
# 全局开关
enabled = true
scan_interval_seconds = 5

# Cursor
[watchers.cursor]
enabled = true
path = "~/.cursor/history/"
file_pattern = "*.json"
# 支持自定义路径
custom_path = ""  # 留空则使用默认路径

# Claude Code
[watchers.claude_code]
enabled = false  # 默认关闭，因为需要用户配置导出
path = "~/Library/Application Support/Claude/conversations/"
file_pattern = "*.json"
custom_path = ""

# Antigravity
[watchers.antigravity]
enabled = true
path = "~/Documents/AG_Exports/"
file_pattern = "*.md"
custom_path = ""

# Windsurf
[watchers.windsurf]
enabled = false
path = "~/.windsurf/history/"
file_pattern = "*.json"
custom_path = ""

# Continue.dev
[watchers.continue_dev]
enabled = false
path = "~/.continue/sessions/"
file_pattern = "*.json"
custom_path = ""

# 自定义工具
[[watchers.custom]]
name = "my_custom_tool"
enabled = false
path = ""
file_pattern = "*.json"
parser = "json"  # json, markdown, xml
```

---

## CLI 命令

### 自动检测工具

```bash
# 检测当前系统已安装的 AI 工具
dimc detect

# 输出示例
✓ 检测到 3 个 AI 开发工具:
  ✓ Cursor (已启用)
    路径: ~/.cursor/history/
    状态: 最后同步 2 分钟前
  
  ⚠ Antigravity (已启用, 等待导出)
    路径: ~/Documents/AG_Exports/
    状态: 未检测到新对话
  
  ✓ Continue.dev (未启用)
    路径: ~/.continue/sessions/
    建议: 运行 'dimc enable continue_dev' 启用
```

### 配置管理

```bash
# 启用特定工具
dimc config enable cursor
dimc config enable antigravity

# 设置自定义路径
dimc config set watchers.cursor.custom_path "/custom/path"

# 查看当前配置
dimc config show

# 重置为默认配置
dimc config reset watchers.cursor
```

### 手动同步

```bash
# 手动触发同步（不等待 Watcher）
dimc sync cursor
dimc sync antigravity

# 同步所有启用的工具
dimc sync --all
```

---

## 最佳实践

### 场景 1: Cursor 用户（全自动）

```bash
# 安装后一次性配置
dimc init
dimc config enable cursor

# 启动后台守护进程（可选，默认自动运行）
dimc daemon start

# 之后完全自动，无需任何操作
# 每次 AI 对话会自动同步到 DIMCAUSE
```

### 场景 2: Antigravity 用户（半自动）

```bash
# 一次性配置
dimc init
dimc config enable antigravity
dimc config set watchers.antigravity.path ~/Documents/AG_Exports

# 日常工作流
# 1. 正常使用 Antigravity AI
# 2. 对话结束后，点击 "Export Conversation"
# 3. 保存到配置的目录
# 4. 后台自动处理（或运行 dimc sync antigravity）

# 每日结束
dimc daily-end  # 会检查并提示未导出的对话
```

### 场景 3: 多工具混合使用

```bash
# 启用多个工具
dimc config enable cursor
dimc config enable antigravity
dimc config enable continue_dev

# 查看所有来源的事件
dimc timeline --limit 20

# 按来源过滤
dimc timeline --source cursor
dimc timeline --source antigravity

# 搜索跨工具的决策
dimc search "architecture decision" --mode semantic
```

### 场景 4: 自定义工具集成

```bash
# 添加自定义工具配置
dimc config add-custom my_tool \
  --path ~/my_tool/chat_history \
  --pattern "*.json" \
  --parser json

# 启用
dimc config enable my_tool
```

---

## 实现设计

### 数据模型扩展

**文件**: `src/dimcause/core/models.py`

```python
class SourceType(str, Enum):
    """数据来源类型"""
    # IDE
    CURSOR = "cursor"
    CLAUDE_CODE = "claude_code"
    ANTIGRAVITY = "antigravity"
    WINDSURF = "windsurf"
    COPILOT_CHAT = "copilot_chat"
    CONTINUE_DEV = "continue_dev"
    
    # 手动
    MANUAL = "manual"
    FILE = "file"
    
    # 其他
    GIT = "git"
    CUSTOM = "custom"
```

### 配置模型

**文件**: `src/dimcause/core/config.py`

```python
class WatcherConfig(BaseModel):
    """单个 Watcher 配置"""
    enabled: bool = False
    path: str
    custom_path: Optional[str] = None
    file_pattern: str = "*.json"
    parser: str = "json"  # json, markdown, xml
    debounce_seconds: float = 1.0
    
    @property
    def effective_path(self) -> str:
        """返回实际使用的路径（自定义 > 默认）"""
        return self.custom_path or self.path


class WatchersConfig(BaseModel):
    """所有 Watcher 配置"""
    enabled: bool = True
    scan_interval_seconds: int = 5
    
    cursor: WatcherConfig
    claude_code: WatcherConfig
    antigravity: WatcherConfig
    windsurf: WatcherConfig
    continue_dev: WatcherConfig
    
    custom: List[WatcherConfig] = []
```

### 自动检测逻辑

**文件**: `src/dimcause/watchers/detector.py`

```python
def detect_installed_tools() -> List[str]:
    """检测系统已安装的 AI 工具"""
    detected = []
    
    tools = {
        "cursor": ["~/.cursor/", "C:\\Users\\{user}\\AppData\\Roaming\\Cursor"],
        "claude_code": ["~/Library/Application Support/Claude/"],
        "windsurf": ["~/.windsurf/"],
        "continue_dev": ["~/.continue/"],
    }
    
    for tool, paths in tools.items():
        for path_template in paths:
            path = Path(path_template).expanduser()
            if path.exists():
                detected.append(tool)
                break
    
    return detected
```

---

## 验收标准

### Phase 1: 核心集成（已完成 ✅）
- [x] Cursor 路径检测
- [x] Antigravity ExportWatcher
- [x] 基础配置系统

### Phase 2: 多工具支持（待实现 🚧）
- [ ] Claude Code 集成
- [ ] Windsurf 集成
- [ ] Continue.dev 集成
- [ ] 自动工具检测 `dimc detect`
- [ ] 配置管理命令 `dimc config`

### Phase 3: 高级功能（规划中 📋）
- [ ] 自定义工具适配器
- [ ] 跨工具对话关联
- [ ] 智能去重（同一对话在多个工具）

---

## 参考

- [Cursor Documentation](https://cursor.sh/docs)
- [Claude API](https://docs.anthropic.com/claude/docs)
- [Continue.dev Guide](https://continue.dev/docs)
- [DIMCAUSE Architecture](./PROJECT_ARCHITECTURE.md)
