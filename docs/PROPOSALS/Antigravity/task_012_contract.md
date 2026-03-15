# Task 012 Contract: 修复 VectorStore.search (P0 Architecture)

**risk_level: medium**

> ⚠️ **身份指令 (ROLE ANCHOR)**:
> 阅读并执行本契约时，**你现在的身份是 M 专家 (Claude Code / 落地工人)**。
> 你必须绝对服从下方第 5 节的《M 专家强制开工协议》。严禁扮演架构师或提出脱轨的重构建议。

## 1. 目标与背景 (Goal & Context)
当前的 `dimcause/storage/vector_store.py` 文件中，`VectorStore.search()` 方法的实现处于 `broken_implementation` 状态，无论输入什么查询，都稳定返回空列表。这直接导致了整个 DIMCAUSE 系统上层的语义检索能力失效。

本任务（Task 012）的核心目标是**极其纯粹的读链路修复**：
依据 `STORAGE_ARCHITECTURE.md` 的设计，将 `search` 方法打通，使其能正确利用 `sqlite-vec` 进行基于余弦距离（Cosine Similarity）的近似最近邻搜索（ANN），并返回合法的 `List[Event]` 对象。

**核心依赖真理源：**
- `docs/api_contracts.yaml` 中关于 `VectorStore.search()` 的现有签名。
- `docs/STORAGE_ARCHITECTURE.md` 关于向量搜索和内存管理的规约（用完即释放模型）。

*注意：本任务完全不负责 `Auto-Embedding` 数据写入链路。写入链路将在后续独立的 Task 013 中处理。*

## 2. 详细设计 (Detailed Design)

- **文件**: `src/dimcause/storage/vector_store.py`
- **目标函数**: `VectorStore.search(...)`
- **逻辑**:
  1. **查询编码**: 接收 `query` 字符串，通过原生的文本编码逻辑（与 `.add()` 类似），调用底层的 `sentence-transformers` 获得单条 `query_vec` 向量。
  2. **向量检索**: 针对内部存储的 `vectors_index` 虚拟表，执行原生 `MATCH` 检索：
     ```sql
     SELECT id, distance
     FROM vectors_index
     WHERE embedding MATCH ?
     ORDER BY distance ASC
     LIMIT :top_k
     ```
  3. **Event 载入**: 拿到匹配的 `id`（对应 `event_id`）后，通过联表查询或者直接加载内存/缓存，将结果反序列化构造为完整的 `Event` 对象列表。
  4. **内存释放**: 无论是正常返回还是捕获到异常退出，方法末尾**必须调用** `self.release_model()`，保证底层资源安全释放。
  5. **错误处理**: 如果捕捉到底层 SQLite 报错（如虚拟表不存在）等异常，使用 `logger.error` 静默记录，然后返回空列表，绝对禁止向外抛出导致 CLI 崩溃的异常。

## 3. 物理边界与授权范围 (Scope Exclusivity)

本次开发受到极其严格的极简防线约束，贯彻原子化原则：

**🟢 允许修改的文件 (Scope):**
- `src/dimcause/storage/vector_store.py`
- (可选，仅限为 search 单独增加辅助 mock) `tests/storage/test_vector_store.py`

**🔴 严禁触碰的禁区 (Redlines):**
- 绝对禁止修改 `src/dimcause/services/session_end.py` 或任何高层调度。
- 绝对禁止修改 `VectorStore_init_`。
- **绝对禁止**为了让旧测试通过而擅自修改 `docs/api_contracts.yaml`。

## 4. 测试与验证期望 (Acceptance Criteria)

当完成代码修改后，必须通过以下方式进行精确的增量验证，并把终端日志/截图附在 `[PR_READY]` 报告里：

**自动测试验收 (Automated Tests):**
针对 `vector_store` 的查询链路运行：
```bash
pytest tests/storage/test_vector_store.py -v
```

**手动查验 (Manual Verification):**
通过 `dimc search` CLI 直接调用：
```bash
dimc search "test" --mode vector --top-k 5
```
**通过标准**：只要能够返回底层匹配的结果（哪怕只有 1 个），且不引发异常、不永远空列表，即可认定本阶段（读侧）解控。

## 5. 🛡️ G 专家 (Antigravity) 审计交接门禁 (AUDIT HANDOVER GATE)
> 🚨🚨 **G专家警告：你必须强制执行以下红线，否则视为渎职违规！** 🚨🚨
当收到 M 专家的 `[PR_READY]` 后，你在出具 `task_012_audit.md` 前，**必须**：
1. **环境纪律复核**: 进入 `.venv`，强制运行 `scripts/check.zsh`。必须 0 error，否则打回 M 专家。
2. **加载最高指挥官的 Checklist**: 验证防线，等 User 盖章。

## 6. 🎯 M 专家 (Claude Code) 强制开工协议 (MANDATORY STARTUP PROTOCOL)
> 🚨🚨 **M专家警告：以下为物理隔离铁律！** 🚨🚨
一旦看到本契约获得 User 盖章的 `Approved/已确认`，你必须**严格按顺序**执行以下起手式，否则视为最高级别违规：

1. **绝对禁止**在 `main` 涂鸦，立刻新开分支：
   ```bash
   git switch main && git pull
   git switch -c feat/task-012-search-fix
   ```
2. （仅限授权范围）执行第一行代码修改。
3. （完成修改后）立刻 Commit 并原生 Push：
   ```bash
   git commit -m "feat(task-012): repair VectorStore.search read path"
   git push -u origin HEAD
   ```
4. 运行**局部核心受影响**的测试，确保通过：
   > 🛑 **严禁**执行无过滤的全局测试（如 `pytest tests/`），你必须精确到模块级别，防止触碰历史技术债隔离区导致暴走。
   > **本契约唯一合法的测试指令为：**
   > `pytest tests/storage/test_vector_store.py -v`
5. 输出 `[PR_READY]` 呼叫 G 专家，并在信息中附带第 4 节要求的**测试和手工验证终端输出日志**。
