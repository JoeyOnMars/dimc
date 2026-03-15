# DIMCAUSE V6.3: Local-First 流式提取架构 (The 26 Ironclad Defenses)

> **基础定言**: Local-First = 数据真实的源头在这个本地机器闭环，流式处理各种宕机和API失败，绝不丢数据。
> **锁死版本**: 历经 13 轮极端的架构审查，基于 ADR-CL-001 v3.0 定案（外键校验建边），废除一切 N×M 增量扫描和图谱自动推断幻觉。**此为唯一合法的架构图床**。

---

## 一、 基础设施防线 (chunks.db 纯粹落入流)

| # | 机制 | 描述与契约 |
|---|---|---|
| 1 | Deterministic Chunk | `chunk_id = "chk_" + sha256(f"{source_event_id}:{content[:64]}").hexdigest()[:16]` |
| 2 | 独立高频池 | 建立专属文件 `~/.dimcause/chunks.db`，使用 WAL + 5000ms BusyTimeout 隔离于主图谱。 |
| 3 | Session Anchor | `session_id` 必须是 chunks 库的一等公民列（TEXT NOT NULL），为图谱边界定锚。 |
| 4 | Event Pointers | `event_ids` 列存放该 chunk 生成事件 ID 的 JSON 数组（初始 `[]`）。 |
| 5 | ID 分源隔离 | `evt_l1_` / `evt_l2_` 通过加盐前缀 `sha256(chunk_id:lX:index)` 生成，粉碎主键冲撞幻觉。 |
| 6 | 线程本地池 | `ChunkStore` 连接池使用 `threading.local()` 防止跨线程 SQLite 串台。 |
| 7 | 多维版本针 | 独立使用 `embedding_version` 与 `extraction_version`。 |
| 8 | 拔除覆盖标志 | 绝对废弃软替换列（移除事件流中的 `superseded_by`）。 |
| 9 | 溯源脐带 | `events` 表新增 `source_chunk_id TEXT DEFAULT NULL`。 |
| 10| 命名隔离 | `events` 表新增 `source_layer TEXT DEFAULT NULL CHECK(source_layer IS NULL OR source_layer IN ('l1', 'l2'))`。 |

---

## 二、 读写与并发防线 (幂等与幽灵消除)

| # | 机制 | 描述与契约 |
|---|---|---|
| 11| L1 兜底与幂等 | L1 持坚定写入，强制使用 `INSERT OR IGNORE` 防止重跑重复。 |
| 12| L2 组级净化 | L2 提取在单库事务内 `DELETE WHERE source_chunk_id=:id AND source_layer='l2'` 再 `INSERT` 新批次，消灭残留并发幽灵。 |
| 13| Per-Chunk 防混血| CausalLinker 代表事件：每个 chunk 每种 event_type 取一个代表（L2 > L1）。 |
| 14| 双路折叠查询 | `EventIndex.query` 使用 `UNION ALL` 两路合并过滤。 |
| 15| 跨库写时序序列 | 先写 `event_index.db`，成功后再更新 `chunks.db`。 |
| 16| 内部数组包裹 | `event_ids` 字段更新封装在 ChunkStore 内部。 |
| 17| 存活与 GC | L1 GC 推迟至 V6.4。 |
| 18| COALESCE 过滤 | EXISTS/NOT EXISTS 消除同时点上的 L1 展示。 |
| 19| 纯历史逃生通道 | `source_chunk_id IS NULL` 的长远历史事件走无过滤独立扫描分支。 |
| 20| Causal 最小粒度 | per-chunk per-type。 |

---

## 三、 图谱防线与 L2 并发死锁解除 (资金与图谱保卫)

| # | 机制 | 描述与契约 |
|---|---|---|
| 21| COALESCE 辅助索引| `idx_chunk_layer`：`ON events(source_chunk_id, source_layer, updated_at DESC)`。 |
| 22| Schema 层软隔离 | CHECK CONSTRAINT NULL 安全写法：`IS NULL OR source_layer IN ('l1', 'l2')`。 |
| 23| DDL 空值免疫 | 所有含 NULL 合法值的枚举约束均采用 NULL 安全写法。 |
| 24| 物理主键收紧 | `graph_edges` 字段名：`source`/`target`/`relation`。 |
| 25| **RMW**| 图谱加边决不能 `INSERT OR REPLACE`。必须在 `BEGIN IMMEDIATE` 下做 **读-改-写 (RMW)**。`weight` 取 MAX，`metadata` 列表去重追加，`created_at` 首次写入后不变。 |

---

## 四、 增量扫描终结 (定案 26：外键校验建边)

经由 G博士 与 M专家的最终战役，ADR-CL-001 v3.0 彻底废弃了一切 `N×M` 或 `N*N` 的自动扫描与增量建边尝试，避免了引发 O(M²) 和笛卡尔积爆炸。

| # | 机制 | 描述与契约 |
|---|---|---|
| 26| **外键直连网关** | 不再维护脏页与时间窗。要求 `events` 新增 `related_event_ids TEXT DEFAULT '[]'`。建边逻辑改为事件入库后读取显式外键，送入 `OntologyEngine` 门禁（_infer_directed_relation 双向查询翻转）。校验通过者写图谱，失败或无外键事件作为孤岛安全隔离。此举连根拔除了 `linker_scanner.py` 与 `linker_queue` 表的祸患。 |
