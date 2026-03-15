# Task 013 Audit Report: Auto-Embedding 数据写入链路

**审计人：** G 博士 (Antigravity)
**最终审计时间：** 2026-03-02T19:50（经三轮审核）
**分支：** `feat/task-013-auto-embedding`（最终提交 `e41d19e`）
**审计基线：** `task_013_contract.md` (P + G 联合审定版)

---

## 门禁核查（全部通过）

| 门禁项 | 状态 | 物证 |
|:---|:---|:---|
| `scripts/check.zsh` 0 error | ✅ | 24 passed, 契约校验 0 errors |
| SQL：差集 + LIMIT，无 session_id 绑定 | ✅ | `session_end.py:326-337` |
| 风险 1：event_vectors 不存在安全降级 | ✅ | `CREATE TABLE IF NOT EXISTS` |
| 风险 2：finally 调用 `release_model()` | ✅ | `session_end.py:385-387` |
| `add_batch` 真批量（一次 forward pass） | ✅ | `vector_store.py:90-109` |
| batch 失败降级逐条，单条 try/except 隔离 | ✅ | `session_end.py:367-382` |
| P1-001：`db_path` 使用 `self.config.data_dir` | ✅ | `session_end.py:296-297` |
| P2-001：parse_failures 逐条 warning 日志 | ✅ | `session_end.py:351-353` |
| P2-002：测试覆盖真实 event_vectors 缺失场景 | ✅ | `test_session_end.py:134-171` |
| 4/4 单元测试通过 | ✅ | `1.25s in 4 passed` |

---

## 结论

**整体评估：通过（Pass），批准合并。**

---

## 经过三轮审核修复的问题

| 问题 | 修复状态 |
|:---|:---|
| P1-001：`db_path` 硬编码，与 ExtractionPipeline 路径脱轨 | ✅ 改为 `self.config.data_dir / "index.db"` |
| `Config.data_dir` 属性缺失（pre-existing bug） | ✅ M 在 `config.py` 新增，返回 `Path.home() / ".dimcause"`，与 `index_db` 等属性设计惯例一致 |
| P2-001：parse 解析失败无逐条 warning | ✅ 改为 `logger.warning(f"...{event_id}: {e}")` |
| P2-002：测试覆盖错误路径（mock os.path.exists） | ✅ 改为 temp_db + patch get_config，名实相符 |

---

## 遗留未解决项（需 User 裁决）

**schema 不一致：`event_vectors` 建表字段多了 `created_at`**

- `session_end.py` 内联建表有 `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`
- `VectorStore._init_vector_db()` 建同一张表时无此字段
- 若两处代码都可能在同一 db 上执行，SQLite `CREATE TABLE IF NOT EXISTS` 以先执行者为准，后执行者的 schema 变化被忽略——字段不会被补加，也不会报错

**实际影响：** 取决于哪段代码先跑。若 `session_end.py` 先建（带 `created_at`），之后 `VectorStore._init_vector_db` 中 `CREATE TABLE IF NOT EXISTS` 不会改变已有表，功能正常；反之亦然。目前不会导致错误，但两处 schema 长期不一致是维护隐患。

**建议修复方向（不阻断本次合并）：** `session_end.py` 改为调用 `vector_store._init_vector_db(conn)` 替代内联 DDL，统一由 VectorStore 管理自己的 schema。

---

## `config.py` 越权修改裁定

M 修改了未在契约授权范围内的 `config.py`。

**G 的判定：合规，按 `fix-all-bugs.md §1` 认定为联动修复。**

物证：`git show main:src/dimcause/utils/config.py | grep data_dir` → 零结果。即 `data_dir` 属性在 `main` 分支从未存在，但 `_run_extraction_pipeline`（已在 `main`）已在使用它，这是 pre-existing bug。M 发现并修复，实现与 `index_db` 等现有属性设计惯例完全一致。

---

*G 博士 (Antigravity) @ 2026-03-02T19:50 — 终版*
