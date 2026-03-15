# Phase 3 技术设计: GraphStore & TUI

**状态**: 草稿
**作者**: Antigravity (P3 架构师)
**日期**: 2026-02-14

## 1. GraphStore 设计 (P3.1)

### 1.1 目标
将现有的 `NetworkX + pickle` 持久化机制替换为 **基于 SQLite 的图形注册表 (Graph Registry)**。
这确保了：
- **原子性**: 增量更新（无需全文件重写）。
- **可查询性**: 基于 SQL 的路径查找和过滤。
- **互操作性**: 数据可被其他工具访问（不仅限于 Python pickle）。

### 1.2 Schema 设计 (`~/.dimcause/index.db`)

我们将在现有的 `index.db`（目前存储 `events`）中添加两个新表。

#### 表: `graph_nodes`
存储图节点。虽然 `events` 表已存在，但 `graph_nodes` 为图算法提供了统一视图，并包含了非事件节点（如 `Entity` 或 `File`）。

```sql
CREATE TABLE graph_nodes (
    id TEXT PRIMARY KEY,                 -- 节点 ID (例如 "evt_123", "ent_python", "file_src/main.py")
    type TEXT NOT NULL,                  -- "event", "entity", "file", "function"
    data JSON DEFAULT '{}',              -- 属性 (例如 name, summary, confidence)
    last_updated REAL NOT NULL           -- 时间戳
);

CREATE INDEX idx_nodes_type ON graph_nodes(type);
```

#### 表: `graph_edges`
存储因果和结构关系。

```sql
CREATE TABLE graph_edges (
    source TEXT NOT NULL,                -- 源节点 ID
    target TEXT NOT NULL,                -- 目标节点 ID
    relation TEXT NOT NULL,              -- "triggers", "realizes", "modifies", "related_to"
    weight REAL DEFAULT 1.0,             -- 权重 [0.0, 1.0]
    metadata JSON DEFAULT '{}',          -- 来源信息 (例如 "heuristic:time_window", "llm:gpt4")
    created_at REAL NOT NULL,            -- 时间戳
    
    PRIMARY KEY (source, target, relation),
    FOREIGN KEY(source) REFERENCES graph_nodes(id),
    FOREIGN KEY(target) REFERENCES graph_nodes(id)
);

CREATE INDEX idx_edges_source ON graph_edges(source);
CREATE INDEX idx_edges_target ON graph_edges(target);
CREATE INDEX idx_edges_relation ON graph_edges(relation);
```

### 1.3 `GraphStore` API

位置: `src/dimcause/storage/graph_store.py`

```python
class GraphStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
    
    def save_node(self, node: Node):
        """更新/插入 节点"""
        ...
        
    def save_edge(self, edge: Edge):
        """更新/插入 边"""
        ...
        
    def save_graph(self, graph: nx.DiGraph):
        """批量保存整个 NetworkX 图谱"""
        # 使用 executemany 以提升性能
        ...
        
    def load_graph(self) -> nx.DiGraph:
        """加载完整图谱到 NetworkX (用于内存分析)"""
        ...
        
    def get_neighbors(self, node_id: str, direction="out") -> List[Edge]:
        """基于 SQL 的邻居查询 (无需加载全图)"""
        ...
```

---

## 2. 交互式 TUI 设计 (P3.2)

### 2.1 技术栈
- **框架**: `Textual` (Python TUI 框架)
- **库**: `Rich` (用于 Markdown/语法渲染)

### 2.2 布局 (Layout)

```
+----------------+-------------------------------------------+
|   侧边栏       |               主内容区                    |
| (节点列表)     |              (详情视图)                   |
|                |                                           |
| [过滤器]       |  [ 标题: 节点名称 / 类型 ]                |
| > evt_123      |                                           |
| > evt_124      |  摘要: ...                                |
| > ent_python   |  内容: ... (Markdown 渲染)                |
|                |                                           |
|                |  ---------------------------------------  |
|                |  [ 关系 ]                                 |
|                |  <- caused_by evt_000 (置信度: 0.9)       |
|                |  -> triggers evt_999 (置信度: 0.8)        |
+----------------+-------------------------------------------+
| 底部: [q] 退出  [f] 过滤  [enter] 选择  [r] 刷新           |
+------------------------------------------------------------+
```

### 2.3 功能特性
- **列表视图 (List View)**: 可滚动的节点列表，支持按类型过滤 (Event/Entity)。
- **详情视图 (Detail View)**: Markdown 渲染的事件内容展示。
- **导航 (Navigation)**: "点击" (选中) 关联节点可跳转。
- **配置面板 (Config Panel)**: 
    - 实时调整参数 (e.g., `semantic_threshold`)。
    - 触发 `Graph Rebuild` 并在 UI 中观察变化。
- **图谱可视化 (Graph Viz)**: (可选 V2) ASCII 图形展示。

---

## 3. 迁移计划
1. **迁移脚本**: `dimc migrate v4`
   - 创建 `graph_nodes` 和 `graph_edges` 表。
   - 遍历 `EventIndex` 中的所有事件。
   - 提取链接 (从 `SemanticEvent.causal_links`)。
   - 填充数据库表。
2. **兼容性**:
   - `EventIndex` 仍然作为 `Event` 元数据的权威来源。
   - `GraphStore` 成为 *连接关系* 的权威来源。
