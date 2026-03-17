# 🎯 DIMCAUSE V6.0 生产就绪修复任务（执行版PROMPT）

```markdown
# 任务背景

你是DIMCAUSE项目的代码维护者。项目已完成V6.0架构开发，但在发布PyPI前发现**5个致命缺陷**阻碍生产部署。

根据2026-02-17的完整审计报告（37文档+5代码文件），你需要在**2-3天内**完成Phase 6.1 Quality & Security Sprint，修复所有P0/P1问题。

---

## 项目状态确认

### ✅ 已完成（无需修改）
- V6.0架构100%对齐（6层设计+本体定义）
- 核心功能90%就绪（WAL+EventIndex+GraphStore+因果推理+MCP）
- 测试框架已搭建

### ❌ 阻塞发布的问题（你的任务）
1. **P0-1**: ChromaDB僵尸依赖（供应链安全风险）
2. **P0-2**: GraphStore.save()语义混乱（API误导用户）
3. **P0-3**: GraphStore.find_related() BFS逻辑bug
4. **P1-1**: MCP Server端口硬编码（多实例冲突）
5. **P1-2**: GraphStore.load_from_db()异常处理不足

---

## Day 1任务：P0修复（必须完成）

### Task 1.1: 移除ChromaDB依赖 [15分钟]

**问题**：`pyproject.toml:42`仍包含`chromadb>=0.4.0`，但V6.0已迁移到sqlite-vec

**修复步骤**：
```bash
# 1. 删除chromadb依赖行
# 文件: pyproject.toml
# 位置: L42 (在full依赖组中)
# 操作: 删除 "chromadb>=0.4.0", 这一行

# 2. 添加废弃注释（在sqlite-vec行后）
# 添加:
    # "chromadb>=0.4.0",  # ⛔ REMOVED 2026-02-17: Replaced by sqlite-vec in V6.0 Phase 4 (STORAGE_ARCHITECTURE.md v1.2)

# 3. 验证
pip uninstall chromadb -y
pip install -e .[full,dev]
pip list | grep -i chroma  # 应为空
pytest tests/storage/test_vector_store.py -v
```

**验收标准**：
- [ ] `pip list`中无chromadb
- [ ] VectorStore测试全部通过
- [ ] `dimc search "test"`命令正常

---

### Task 1.2: GraphStore.save()添加废弃警告 [30分钟]

**问题**：`src/dimcause/storage/graph_store.py:138`的save()方法是空操作但无警告，误导用户

**当前代码**：
```python
def save(self) -> None:
    """
    持久化图
    Deprecated: 在 SQLite 策略下，写入即持久化。
    此方法保留为空以兼容旧代码接口，但不再执行 Pickle dump。
    """
    pass  # ⚠️ 静默无操作，用户无感知
```

**修复代码**（完整替换save()方法）：
```python
import warnings  # 确保文件顶部已import

def save(self) -> None:
    """
    持久化图（已废弃）
    
    .. deprecated:: 6.0
       在SQLite Registry策略下，所有写操作（add_entity/add_relation）
       自动持久化到数据库。此方法调用无效果，保留仅为向后兼容。
       
    Warning:
        调用此方法将触发DeprecationWarning。请移除代码中的save()调用。
        
    See Also:
        - STORAGE_ARCHITECTURE.md Section 4.2 (SQLite Registry Strategy)
        - V6.0_ROADMAP.md Phase 3 (Pickle移除记录)
    """
    warnings.warn(
        "GraphStore.save() is deprecated since V6.0 and has no effect. "
        "Data is automatically persisted on add_entity()/add_relation(). "
        "Remove this call from your code.",
        DeprecationWarning,
        stacklevel=2
    )
```

**添加测试**（新建文件）：
```python
# tests/storage/test_graph_store_deprecation.py
import pytest
from dimcause.storage.graph_store import GraphStore

def test_save_emits_deprecation_warning():
    """测试save()方法触发废弃警告"""
    store = GraphStore()
    with pytest.warns(DeprecationWarning, match="deprecated since V6.0"):
        store.save()
```

**验收标准**：
- [ ] 测试通过：`pytest tests/storage/test_graph_store_deprecation.py -v`
- [ ] 手动验证：运行Python代码调用`store.save()`看到警告

---

### Task 1.3: 修复GraphStore.find_related() BFS逻辑bug [1小时]

**问题**：`src/dimcause/storage/graph_store.py:221-234`的BFS实现有严重逻辑错误，导致仅能搜索1层

**错误代码**：
```python
def find_related(self, entity_name: str, depth: int = 1) -> List[Entity]:
    related = set()
    current_level = {entity_name}
    for _ in range(depth):
        next_level = set()
        for node in current_level:
            next_level.update(self._graph.successors(node))
            next_level.update(self._graph.predecessors(node))
        related.update(next_level)          # ← Bug在这里
        current_level = next_level - related  # ← 立即抵消了上一行
    # ... 转换为Entity
```

**Bug说明**：第1轮循环后，`related`包含了所有邻居，然后`current_level = next_level - related`会变成空集，导致第2轮无法探索。

**修复代码**（完整替换find_related()方法）：
```python
def find_related(self, entity_name: str, depth: int = 1) -> List[Entity]:
    """
    查找相关实体（BFS广度优先搜索）
    
    Args:
        entity_name: 起始实体名称
        depth: 搜索深度（1=直接邻居，2=二度关系...）
        
    Returns:
        相关实体列表（不包含起始实体本身）
        
    Example:
        >>> store.find_related("file.py", depth=2)
        [Entity(name="commit_abc", type="commit"), 
         Entity(name="func_foo", type="function")]
    """
    if self._graph is None or entity_name not in self._graph:
        return []
    
    visited = {entity_name}  # 已访问节点（包含起点）
    current_level = {entity_name}
    
    for _ in range(depth):
        next_level = set()
        for node in current_level:
            # 获取所有邻居（入边+出边）
            neighbors = set(self._graph.successors(node)) | \
                       set(self._graph.predecessors(node))
            # 仅添加未访问过的节点
            next_level.update(neighbors - visited)
        
        if not next_level:  # 无新节点可探索
            break
            
        visited.update(next_level)
        current_level = next_level
    
    # 转换为Entity对象（排除起点）
    entities = []
    for name in visited - {entity_name}:
        node_data = self._graph.nodes[name]
        entities.append(Entity(
            name=name,
            type=node_data.get("type", "unknown"),
            context=node_data.get("context")
        ))
    return entities
```

**添加测试**（新建文件）：
```python
# tests/storage/test_graph_store_bfs.py
import pytest
from dimcause.storage.graph_store import GraphStore
from dimcause.core.models import Entity

def test_find_related_depth_1():
    """测试一度关系搜索"""
    store = GraphStore()
    store.add_entity("A", "file")
    store.add_entity("B", "commit")
    store.add_entity("C", "decision")
    store.add_relation("A", "B", "modifies")
    store.add_relation("A", "C", "realizes")
    
    related = store.find_related("A", depth=1)
    assert len(related) == 2
    assert {e.name for e in related} == {"B", "C"}

def test_find_related_depth_2():
    """测试二度关系搜索"""
    store = GraphStore()
    # 构建图: A -> B -> C
    #           |
    #           v
    #           D
    store.add_entity("A", "file")
    store.add_entity("B", "commit")
    store.add_entity("C", "function")
    store.add_entity("D", "decision")
    store.add_relation("A", "B", "modifies")
    store.add_relation("B", "C", "implements")
    store.add_relation("A", "D", "realizes")
    
    # depth=1: 应返回 [B, D]
    related_1 = store.find_related("A", depth=1)
    assert len(related_1) == 2
    assert {e.name for e in related_1} == {"B", "D"}
    
    # depth=2: 应返回 [B, D, C]
    related_2 = store.find_related("A", depth=2)
    assert len(related_2) == 3
    assert {e.name for e in related_2} == {"B", "D", "C"}

def test_find_related_nonexistent_entity():
    """测试查询不存在的实体"""
    store = GraphStore()
    related = store.find_related("nonexistent", depth=1)
    assert related == []
```

**验收标准**：
- [ ] 所有BFS测试通过：`pytest tests/storage/test_graph_store_bfs.py -v`
- [ ] 手动验证：`dimc trace <file>`返回正确的多层关联

---

## Day 2任务：P1修复（提升可用性）

### Task 2.1: MCP Server端口配置化 [1小时]

**问题**：`src/dimcause/protocols/mcp_server.py:270`硬编码端口14243，无法配置

**当前代码**：
```python
def run(transport: str = "stdio"):
    if transport == "http":
        mcp.run(transport="http", host="127.0.0.1", port=14243)  # ⚠️ 硬编码
    else:
        mcp.run()
```

**修复代码**（替换run()函数）：
```python
import os

def run(transport: str = "stdio", port: int = None, host: str = None):
    """启动 MCP 服务器
    
    Args:
        transport: 传输方式 ("stdio" 或 "http")
        port: HTTP端口（默认从环境变量DIMCAUSE_MCP_PORT读取，回退到14243）
        host: HTTP监听地址（默认从环境变量DIMCAUSE_MCP_HOST读取，回退到127.0.0.1）
        
    Environment Variables:
        DIMCAUSE_MCP_PORT: MCP服务器端口（覆盖默认值14243）
        DIMCAUSE_MCP_HOST: MCP服务器监听地址（覆盖默认值127.0.0.1）
        
    Examples:
        >>> # 使用默认端口
        >>> run(transport="http")
        
        >>> # 使用自定义端口
        >>> run(transport="http", port=8080)
        
        >>> # 通过环境变量配置
        >>> import os
        >>> os.environ["DIMCAUSE_MCP_PORT"] = "9000"
        >>> run(transport="http")
    """
    if transport == "http":
        # 优先级: 函数参数 > 环境变量 > 默认值
        port = port or int(os.getenv("DIMCAUSE_MCP_PORT", 14243))
        host = host or os.getenv("DIMCAUSE_MCP_HOST", "127.0.0.1")
        
        logging.info(f"Starting MCP server on {host}:{port}")
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
```

**CLI集成**（如果cli.py中有mcp命令，需更新）：
```python
# 查找 src/dimcause/cli.py 中的 mcp 相关命令
# 如果存在类似 @app.command() def mcp_serve()，需添加port/host参数

@app.command()
def mcp_serve(
    transport: str = typer.Option("stdio", help="Transport mode: stdio or http"),
    port: int = typer.Option(None, help="HTTP port (default: 14243)"),
    host: str = typer.Option(None, help="HTTP host (default: 127.0.0.1)")
):
    """Start MCP server"""
    from dimcause.protocols.mcp_server import run
    run(transport=transport, port=port, host=host)
```

**验收标准**：
- [ ] `dimc mcp serve --transport http --port 9000`工作正常
- [ ] 环境变量生效：`DIMCAUSE_MCP_PORT=8080 dimc mcp serve --transport http`
- [ ] README.md添加端口配置说明

---

### Task 2.2: GraphStore.load_from_db()错误处理增强 [30分钟]

**问题**：`src/dimcause/storage/graph_store.py:93`捕获所有OperationalError并静默，无法调试

**当前代码**：
```python
except sqlite3.OperationalError:
    # 表可能不存在（尚未迁移或初始化）
    pass  # ⚠️ 静默失败
```

**修复代码**（替换load_from_db()方法中的异常处理部分）：
```python
import logging

# 在 load_from_db() 方法中，替换两处 except sqlite3.OperationalError

# 第一处：加载节点时（约L93-95）
except sqlite3.OperationalError as e:
    error_msg = str(e).lower()
    if "no such table" in error_msg:
        logging.info("GraphStore tables not initialized, run 'dimc migrate'")
    elif "database is locked" in error_msg:
        logging.error(f"GraphStore DB locked (timeout): {e}")
        raise  # 锁超时是严重问题，不应静默
    elif "disk" in error_msg or "space" in error_msg:
        logging.critical(f"Disk space issue loading GraphStore: {e}")
        raise  # 磁盘问题必须立即暴露
    else:
        logging.error(f"Unexpected DB error loading nodes: {e}")
        raise

# 第二处：加载边时（约L110-112）
except sqlite3.OperationalError as e:
    error_msg = str(e).lower()
    if "no such table" in error_msg:
        logging.info("GraphStore edge table not initialized")
    elif "database is locked" in error_msg:
        logging.error(f"GraphStore DB locked loading edges: {e}")
        raise
    elif "disk" in error_msg or "space" in error_msg:
        logging.critical(f"Disk issue loading edges: {e}")
        raise
    else:
        logging.error(f"Unexpected error loading edges: {e}")
        raise
```

**验收标准**：
- [ ] 表不存在时：输出INFO日志（不抛异常）
- [ ] 锁超时时：输出ERROR日志并抛异常
- [ ] 磁盘满时：输出CRITICAL日志并抛异常

---

### Task 2.3: 添加安全工具依赖 [5分钟]

**问题**：`pyproject.toml`的dev依赖缺少安全扫描工具

**修复代码**：
```toml
# 文件: pyproject.toml
# 找到 [project.optional-dependencies] 下的 dev 部分
# 在现有依赖后添加：

dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "bandit>=1.7.0",      # + 静态安全扫描 (SAST)
    "pip-audit>=2.0.0",   # + 依赖漏洞检测 (CVE)
    "safety>=2.0.0",      # + 已知漏洞数据库
]
```

**验收标准**：
- [ ] `pip install -e .[dev]`成功安装所有工具
- [ ] `bandit -r src/ -ll`无HIGH级别问题
- [ ] `pip-audit`无CRITICAL级别漏洞

---

## Day 3任务：P2文档对齐（可选但推荐）

### Task 3.1: 文档状态同步 [1小时]

**涉及文件**：
1. `docs/implementation_plan.md` - 更新Phase 5状态为完成
2. `docs/research/index.md` - 降级RT-002/003优先级为P3
3. `pyproject.toml` - 移除Python 3.13声明

**修复步骤**：
```markdown
# 1. implementation_plan.md
找到 "| 阶段 5: 最终验证 | `[ ]` | 🟡 进行中 |"
替换为 "| 阶段 5: 最终验证 | `[x]` | ✅ 完成 (见 2026-02-17_DESIGN_ALIGNMENT.md) |"

# 2. index.md
找到 "### RT-002: ... **优先级**: P1 - High"
替换为 "### RT-002: ... **优先级**: P3 - Low (V7.0 Feature)"
添加 "**前置条件**: V6.0发布PyPI + Phase 6.1完成"

找到 "### RT-003: ... **优先级**: P1 - High"
替换为 "### RT-003: ... **优先级**: P3 - Low (V7.0 Feature)"
添加 "**前置条件**: RT-002完成"

# 3. pyproject.toml
删除 "Programming Language :: Python :: 3.13",
修改 requires-python = ">=3.10,<3.13"
```

---

## 执行指南

### 1. 环境准备
```bash
cd /Users/mini/projects/GithubRepos/dimc
source .venv/bin/activate
git checkout -b fix/v6.0-production-ready
```

### 2. 逐任务执行
- 按照Day 1 → Day 2 → Day 3顺序
- 每完成一个Task立即运行对应测试
- 每完成一个Day提交Git：
  ```bash
  git add .
  git commit -m "fix(P0): Task 1.1-1.3 完成"
  ```

### 3. 最终验证
```bash
# 完整测试套件
pytest tests/ -v --cov=src/dimcause --cov-report=term-missing

# 安全扫描
bandit -r src/ -ll
pip-audit

# 手动功能验证
dimc graph stats
dimc mcp serve --transport http --port 9000 &
curl http://localhost:9000/health  # 假设有health端点
```

### 4. 交付物
- [ ] 所有P0/P1测试通过
- [ ] Git commit历史清晰（每个Task一个commit）
- [ ] 创建Pull Request标题："V6.0 Production-Ready Sprint (Phase 6.1)"
- [ ] PR描述包含：
  - 修复的5个问题清单
  - 测试覆盖率报告
  - 安全扫描结果

---

## 关键约束（必须遵守）

### 来自 DIMCAUSE.SecurityBaseline.ABC.md

1. **禁止破坏核心行为**：
   - Markdown 必须是唯一 Source of Truth
   - WAL 写入顺序不可改变
   - EventIndex 扫描目录不可缩减

2. **禁止擅自修改既有契约**（来自dimcause-ai-system.md）：
   - 不得为"让测试通过"随意改函数签名
   - docs/api_contracts.yaml 是函数契约唯一真相源

3. **默认扮演审计员角色**：
   - 发现契约/代码/测试不一致时，报告冲突但不擅自修改

### 虚拟环境强制要求
```bash
# 每次操作前必须激活
source /Users/mini/projects/GithubRepos/dimc/.venv/bin/activate
```

---

## 预期输出

完成所有任务后，你应该能够回答：

1. **chromadb是否已彻底移除？** 
   - 运行：`pip list | grep -i chroma`
   - 预期：无输出

2. **GraphStore.save()是否触发警告？**
   - 运行：`python -c "from dimcause.storage.graph_store import GraphStore; GraphStore().save()"`
   - 预期：看到DeprecationWarning

3. **BFS是否修复？**
   - 运行：`pytest tests/storage/test_graph_store_bfs.py -v`
   - 预期：所有测试通过

4. **MCP端口是否可配置？**
   - 运行：`dimc mcp serve --transport http --port 9000`
   - 预期：服务启动在9000端口

5. **安全基线是否达标？**
   - 运行：`bandit -r src/ -ll && pip-audit`
   - 预期：无HIGH/CRITICAL问题

---

## 遇到问题时

### 如果代码结构与描述不符
1. 运行`find src/ -name "*.py" | xargs grep -l "def save"`定位实际文件
2. 报告差异："预期在X位置，实际在Y位置"
3. 根据实际位置调整修复

### 如果测试失败
1. 复制完整错误信息
2. 报告："Task X.Y测试失败，错误：..."
3. 不要擅自修改测试用例以"让它通过"

### 如果不确定某个修改
1. 标记："不确定点：..."
2. 说明需要哪些额外信息
3. 不要给出"肯定能"这类绝对结论

---

## 时间估算
- Day 1: 2小时（P0修复）
- Day 2: 1.5小时（P1修复）
- Day 3: 1小时（文档对齐）
- **总计**: 4.5小时净工作时间

---

# 开始执行

请从**Task 1.1: 移除ChromaDB依赖**开始，完成后报告：
- [ ] 修改了哪些文件
- [ ] 运行了哪些测试
- [ ] 测试结果（通过/失败）
- [ ] 下一步建议

**记住**：每个Task完成后立即commit，不要等到全部完成再commit。

祝你好运！🚀
```

***

## 使用说明

### 方式1: 直接复制（推荐）
1. 复制上述整个代码块（从"# 任务背景"到最后的"祝你好运！"）
2. 粘贴到你的AI对话框（Claude/ChatGPT/Cursor等）
3. AI会开始执行Task 1.1

### 方式2: 保存为文件
```bash
# 保存为markdown文件
cat > DIMCAUSE_V6_EXECUTION_PROMPT.md << 'EOF'
... (上述内容) ...
EOF

# 然后发给AI：
# "请阅读附件 DIMCAUSE_V6_EXECUTION_PROMPT.md 并开始执行Task 1.1"
```

### 方式3: 分段发送（适合token限制严格的AI）
```
第一段: "任务背景" + "项目状态确认"
第二段: "Day 1任务：P0修复"
第三段: "Day 2任务：P1修复"
...依此类推
```

***

## PROMPT优势
- ✅ **零歧义**：每个Task都有完整代码，AI不需要"理解"
- ✅ **可验证**：每步都有明确的验收标准
- ✅ **防护栏**：包含SecurityBaseline约束，防止AI破坏核心逻辑
- ✅ **可恢复**：每个Task独立commit，出错可回滚
- ✅ **时间可控**：总计4.5小时，适合1-2天完成