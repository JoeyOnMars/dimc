# 2026-02-17 PHASE 6.1 生产级执行计划 V2 (最终版)

**状态**: 已批准  
**负责人**: Gemini (首席架构师)  
**日期**: 2026-02-17  
**目标**: 以生产级标准修复 P0/P1 审计发现，实施严格的风险隔离、数据完整性检查和规模化测试。

---

## 1. 执行摘要 (Executive Summary)

### 1.1 目标
执行对 P0 (僵尸 ChromaDB、误导性 API、BFS Bug) 和 P1 (安全性、错误处理) 问题的关键修复，同时确保数据零丢失，并在规模化场景下保持系统稳定。

### 1.2 V2 改进点 (对比 V1)
| 维度 | V1 弱点 | V2 改进方案 |
|-----------|-------------|----------------|
| **数据完整性** | 假设 Schema 兼容 | **Schema 验证 + 向前修复 (Fix Forward) 策略** (场景 1 教训) |
| **性能保障** | 小规模 (<1k 节点) 测试 | **规模化测试 (10k+ 节点)** 使用 Barabási-Albert 模型 (场景 2 教训) |
| **风险控制** | 全有或全无的回滚 | **细粒度回滚 + 运行时熔断器** (场景 3 教训) |
| **度量标准** | 绝对阈值 (<0.1s) | **相对阈值** (性能退化 <20%) |

### 1.3 风险评估
- **整体风险**: 中 (通过风险隔离从“高”降低)
- **关键路径**: 任务 1.3 (BFS 修复) - 复杂度高，存在潜在性能因果链。
- **数据风险**: 任务 1.1 (移除依赖) - 存在隐性状态不兼容的可能性。

---

## 2. 飞行前检查清单 (Pre-flight Checklist)

在执行**任何**任务之前，必须运行以下验证步骤。

### 2.1 环境验证
```bash
# 确保严格的环境隔离
source /Users/mini/projects/GithubRepos/dimc/.venv/bin/activate
which python | grep ".venv" || exit 1
python -c "import sqlite_vec; print(f'sqlite-vec ok')" || exit 1
```

### 2.2 依赖审计
```bash
# 验证无僵尸进程或锁
pgrep -f "dimc" && echo "WARNING: dimc running" && exit 1
# 检查现有数据库完整性
if [ -d ".dimcause" ]; then
    echo "Running pre-flight integrity check..."
    dimc audit --mode strict || exit 1
fi
```

### 2.3 快照策略
```bash
# 定义快照 ID
SNAPSHOT_ID="pre_phase6.1_$(date +%Y%m%d_%H%M%S)"
echo "SNAPSHOT_ID=$SNAPSHOT_ID" > .audit_snapshot
```

---

## 3. 任务执行计划 (Task Execution Plan)

**总时间预算**: 12 小时 (1.5 + 0.5 + 4.0 + 2.0 Phase缓冲)

### 任务 1.1: 消除僵尸 ChromaDB 依赖 (P0-1)
**时间预算**: 1.5小时 (备份15min + 卸载5min + 测试30min + 验证15min + 缓冲25min)
目标: 从 `pyproject.toml` 中移除 `chromadb`，并验证 `sqlite-vec` 作为唯一的向量存储正常工作。

**步骤**:
1.  **备份数据与状态**:
    ```bash
    cp -r .dimcause .dimcause.backup.1.1 || echo "No existing data to backup"
    ```
2.  **移除依赖**:
    ```bash
    # (已在 pyproject.toml 中注释掉，验证纯净安装)
    pip uninstall -y chromadb
    pip install -e .  # 重新安装以确保依赖图纯净
    ```
3.  **验证新向量存储**:
    ```bash
    # 运行特定的向量存储测试
    pytest tests/storage/test_vector_store.py
    ```
4.  **Schema 兼容性检查 (关键)**:
    ```bash
    # 验证旧代码连接不会崩溃
    python -c "from dimcause.storage.vector_store import VectorStore; v=VectorStore(); print(v)"
    ```

**验收标准**:
- [ ] `pip freeze | grep chromadb` 返回为空。
- [ ] `pytest tests/storage/test_vector_store.py` 通过。
- [ ] `dimc init` 不再提及 ChromaDB。

**回滚触发器**: 任何测试失败或导入错误。

### 任务 1.2: 废弃 GraphStore.save() (P0-2)
**时间预算**: 0.5小时 (代码修改10min + 测试15min + 文档5min + 缓冲10min)
目标: 在 `save()` 逻辑中添加警告，防止数据持久化假象。

**步骤**:
1.  **修改代码**:
    - 更新 `src/dimcause/storage/graph_store.py`: 向 `save()` 添加 `DeprecationWarning`。
    - 记录日志警告: "GraphStore uses SQLite auto-commit. save() is a no-op."
2.  **验证副作用**:
    ```bash
    # 运行测试并检查警告输出
    pytest tests/storage/test_graph_store.py -W always
    ```
3.  **更新文档**:
    - `docs/API.md`: 将 `save()` 标记为已废弃 (deprecated)。

**验收标准**:
- [ ] 调用 `save()` 触发日志警告。
- [ ] 图操作无功能回退。

### 任务 1.3: 修复 BFS 逻辑 Bug & 优化 (P0-3) - **关键任务**
**时间预算**: 4.0小时 (基线30min + 实现2h + 测试1h + 文档30min)
目标: 修复 BFS 深度搜索 Bug (`depth=1` 限制) **并且** 确保使用优化后的实现在 10k 节点下性能达标。

**步骤**:
1.  **创建性能基线**:
    ```bash
    # 在当前 (有 bug) 实现上运行基准测试作为基线
    pytest tests/storage/test_graph_performance.py --benchmark-save=baseline
    ```
2.  **实现修复 + 优化**:
    - 使用优化的双向搜索或正确的 NetworkX 用法重写 `find_related`。
    - **防御**: 对已访问节点使用 `set`，避免在循环中重新创建集合。
    - **优化**: 如果纯 Python 太慢，考虑 `scipy.sparse` (如允许)，否则优化 Python 循环。
3.  **规模化测试 (BA 模型测试)**:
    ```bash
    # 运行新的严格性能测试套件 (需要实现)
    # 参见第 5.1 节 tests/storage/test_graph_performance.py
    pytest tests/storage/test_graph_performance.py
    ```

**验收标准**:
- [ ] **功能**: `depth=3` 确实返回 3 度邻居。
- [ ] **性能 (绝对)**: 10k 节点 BFS < 0.5s (硬性限制)。
- [ ] **性能 (相对)**: 相对基线无 > 20% 的退化 (校正因逻辑变更带来的预期增加)。
- [ ] **数据完整性**: 返回的实体具有有效的 `timestamp` 和 `id`。

**决策门 (Decision Gate)**:
- **通过 (Pass)**: 所有测试通过。合并。
- **有条件通过 (Conditional)**: 功能通过，性能 < 1s 但 > 0.5s。**行动**: 合并但添加 `max_depth` 警告。
- **失败 (Fail)**: 性能 > 1s 或数据腐败。**行动**: 触发任务 1.3 回滚。

---

## 4. 回滚策略: "大红按钮 (The Big Red Button)"

### 4.1 主回滚脚本 (`scripts/emergency_rollback.sh`)

```bash
#!/bin/bash
set -euo pipefail

# 依赖检查
echo "[CHECK] Verifying dependencies..."
which git > /dev/null || { echo "[FATAL] git not found"; exit 1; }
which python > /dev/null || { echo "[FATAL] python not found"; exit 1; }
which sqlite3 > /dev/null || { echo "[FATAL] sqlite3 not found"; exit 1; }

python -c "import sys; assert sys.version_info >= (3, 8)" || { echo "[FATAL] Python 3.8+ required"; exit 1; }
if [ ! -d ".venv" ]; then echo "[FATAL] Virtual environment .venv not found"; exit 1; fi
echo "[OK] All dependencies verified."

# 检查快照 ID
if [ ! -f .audit_snapshot ]; then echo "No snapshot ID found."; exit 1; fi
SNAPSHOT_ID=$(cat .audit_snapshot)
BACKUP_DIR=".dimcause.backup.$SNAPSHOT_ID"
echo "[CRITICAL] Initiating Rollback to Snapshot: $SNAPSHOT_ID"

# 0. 验证备份完整性 (A1.5)
if [ -d "$BACKUP_DIR" ]; then
    if [ -f "$BACKUP_DIR/checksum.sha256" ]; then
        echo "[CHECK] Verifying Backup Checksum..."
        if (cd "$BACKUP_DIR" && shasum -c checksum.sha256 > /dev/null); then
            echo "[OK] Backup checksum verified"
        else
            echo "[FATAL] Backup checksum verification failed!"
            exit 1
        fi
    else
        echo "[WARN] No checksum found. Skipping verification."
    fi
else
    echo "[FATAL] Backup directory not found!"; exit 1
fi

# 1. 停止服务
pkill -f dimc || true

# 2. 恢复代码
git stash push -m "Rollback stash $SNAPSHOT_ID" || true
git reset --hard origin/main 

# 3. 恢复数据
ROLLBACK_FAILED=0
rm -rf .dimcause
cp -r "$BACKUP_DIR" .dimcause || ROLLBACK_FAILED=1

# 4. 清理
if [ $ROLLBACK_FAILED -eq 0 ]; then
    rm -rf build/ dist/ *.egg-info
    find . -name "__pycache__" -exec rm -rf {} +
fi

# 5. 验证与检查
source .venv/bin/activate
if [ $ROLLBACK_FAILED -eq 0 ]; then
    # 5.1 数据完整性 (E3.3)
    BACKUP_DB="$BACKUP_DIR/graph.db"
    RESTORED_DB=".dimcause/graph.db"
    if [ -f "$BACKUP_DB" ]; then
        CNT_B=$(sqlite3 "$BACKUP_DB" "SELECT count(*) FROM entities;")
        CNT_R=$(sqlite3 "$RESTORED_DB" "SELECT count(*) FROM entities;")
        if [ "$CNT_B" -eq "$CNT_R" ]; then
            echo "[OK] Data count matches: $CNT_R"
        else
            echo "[FATAL] Data count mismatch! Backup:$CNT_B vs Restored:$CNT_R"
            ROLLBACK_FAILED=1
        fi
    fi

    # 5.2/5.3 功能验证 (略: GraphStore/VectorStore checks)
    # ... (See actual script for full verification logic) ...
fi

# 结果判定
if [ $ROLLBACK_FAILED -eq 0 ]; then
    echo "[SUCCESS] Rollback Verified."
else
    echo "ROLLBACK CIRCUIT BREAKER TRIGGERED - Manual Intervention Required (Exit 99)"
    exit 99
fi
```

### 4.2 回滚验证清单
- [ ] 代码处于之前的 commit SHA。
- [ ] `.dimcause` 目录与任务前备份完全一致。
- [ ] 系统启动无导入错误 (`dimc --version`)。
- [ ] **数据读取**: 可以读取现有的图实体。

### 4.3 Multi-Agent 回滚演练模板
**日期**: 2026-02-17  
**环境**: 测试分支 `phase-6.1-test-drill`  
**参与 Agent**:  
- `Executor` (Gemini): 执行回滚脚本
- `Auditor` (Perplexity): 验证数据完整性
- `Orchestrator` (Human): 最终决策

**演练步骤**:
1. **备份阶段**: Agent 执行 `cp -r .dimcause ...`，Auditor 验证 SHA。
2. **破坏阶段**: 人工/脚本 注入故障 (e.g., Delete crucial table)。
3. **检测阶段**: Auditor 运行 `dimc audit` 发现故障。
4. **回滚执行**: Executor 运行 `scripts/emergency_rollback.sh`。
5. **验证阶段**: Auditor 运行 `pytest` 和 `dimc trace` 验证恢复。

**成功指标**:
- [ ] 回滚耗时 < 5分钟
- [ ] 数据 100% 恢复
- [ ] Agent 审计日志完整

**Agent 行为日志示例** (`.dimcause/agent_audit/phase_6_1.jsonl`):
```json
{"agent_id":"gemini-production-2.0","timestamp":"2026-02-17T10:05:00Z","action_type":"backup","decision":"pass"}
```


---

## 5. 测试协议 (Testing Protocol)

### 5.1 性能测试套件 (新标准)

#### 快速基线 (CI/Commit)
在 `tests/storage/test_graph_performance.py` 中添加:
```python
@pytest.mark.fast
def test_1k_baseline():
    """快速基线测试（CI每次commit跑）"""
    import networkx as nx
    from dimcause.storage.graph_store import GraphStore
    import time
    
    # Generate smaller graph for quick check
    ba_graph = nx.barabasi_albert_graph(n=1000, m=3)
    store = GraphStore()
    
    for u, v in ba_graph.edges():
        store.add_relation(f"node_{u}", f"node_{v}", "test_relation")
    
    # Find hub node
    degrees = dict(ba_graph.degree())
    hub_node = max(degrees, key=degrees.get)
    
    start = time.time()
    results = store.find_related(f"node_{hub_node}", depth=2)
    duration = time.time() - start
    
    assert duration < 0.1, f"1k baseline too slow: {duration:.3f}s"
    assert len(results) > 0
```

配置 `pytest.ini`:
```ini
[pytest]
markers =
    fast: marks tests as fast (CI runs on every commit)
    slow: marks tests as slow (nightly builds only)
```

#### 规模化测试 (Nightly)
- 使用 `networkx.barabasi_albert_graph(n=10000, m=3)` 模拟规模。
- 在 **Hub 节点** (度数前 1%) 上测试 `find_related`。
- **阈值**: `duration < 0.5s`。
- **相对检查**: `benchmark(store.find_related, ...)`
- **极限规模 (Extreme Scale)**: 50k 节点测试 (Placeholder existing in `test_graph_performance.py`, B1.3)


### 5.2 数据完整性测试
创建 `tests/storage/test_data_integrity.py`:
- **Schema 检查**: `find_related` 返回的每个实体必须包含: `id`, `type`, `timestamp`, `content`。
- **时间戳健全性**: `timestamp` 必须是标准 ISO 格式，而非 "1970..."。

### 5.3 回滚模拟 (演练)
在合并任务 1.3 PR 之前:
1. 运行 `dimc trace`。
2. 运行 `scripts/emergency_rollback.sh`。
3. 验证 `dimc trace` 再次工作 (即使功能较旧)。

---

## 6. 风险管理与故障处理

### 6.1 决策树 (任务 1.3)
1. **性能检查**: 
   - `10k_node_search` 时间 < 0.5s? 
     - 是 -> 转至 2。
     - 否 -> 是否 < 1.0s? 
       - 是 -> **有条件通过** (设置 `default_depth=2`，警告用户)。
       - 否 -> **失败** (拒绝任务 1.3，如果稳定则回退到 NetworkX 逻辑，或保留 bug 但保持稳定)。
2. **完整性检查**:
   - `Entity` 对象是否缺失任何字段?
     - 是 -> **失败** (需要立即修复，不合并)。
     - 否 -> **通过**。

### 6.2 熔断器 (运行时)
在 `src/dimcause/storage/graph_store.py` 中:
```python
# BFS 安全包装器
MAX_BFS_NODES = 10000
timeout = 2.0 # seconds

start = time.time()
while queue:
    if time.time() - start > timeout:
        logger.error("BFS Timeout - Partial results returned")
        break
    if len(visited) > MAX_BFS_NODES:
        logger.error("BFS Node Limit Reached")
        break
    
    # (完整 BFS 逻辑见 Task 1.3 实现)
    current = queue.popleft()
    for neighbor in graph[current]:
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append(neighbor)
```

---

## 7. 审计轨迹与验证

### 7.1 记录
每个命令都必须记录。使用 `script` 或将完整终端输出复制粘贴到 `docs/logs/2026/02-17/execution_log.md`。

### 7.2 任务后产物
对于每个任务，提交一份报告:
- `docs/audit_reports/task_1_X_evidence.md`
- 包含: `pytest` 输出，性能指标，功能截图。

### 7.3 最终签署
需要检查:
- [ ] `dimc trace` / `dimc audit` 无回退。
- [ ] 所有 P0 问题已解决。
- [ ] 回滚脚本已测试并存在。

### 7.4 Agent 审计表 Schema (未来实现)

**当前 Phase 6.1**: Agent 行为记录到 JSON 文件  
**未来 Phase 7+**: 迁移到 SQLite 表

```sql
CREATE TABLE agent_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_id TEXT NOT NULL,          -- 'gemini-production-2.0', etc.
    agent_role TEXT,                  -- 'executor', 'auditor', 'orchestrator'
    task_id TEXT,                     -- 'phase-6.1-task-1.1'
    action_type TEXT,                 -- 'backup', 'rollback', 'validate'
    action_detail TEXT,               -- 具体操作命令或描述
    decision TEXT,                    -- 'pass', 'fail', 'trigger_rollback'
    rationale TEXT,                   -- Agent决策理由
    context_snapshot TEXT,            -- Agent当时的Context
    signature_hash TEXT,              -- SHA256(agent_id + timestamp + action_detail)
    parent_audit_id INTEGER,          -- 关联父操作（用于追溯因果链）
    FOREIGN KEY (parent_audit_id) REFERENCES agent_audit(id)
);
```

**Phase 6.1 实现**:
- Agent 行为写入 `.dimcause/agent_audit/phase_6_1.jsonl`
- 每行一个 JSON 对象 (格式同上表 Schema)
