# V6.3 架构审查：M 专家 vs G博士 争论记录

**范围**：从定案数量核实（25→31）开始，至 P博士介入拍板前
**参与方**：M 专家（实现审查）、G博士（架构审查）
**日期**：2026-02-23
**状态**：定案 33 待 P博士拍板

---

## 背景

上下文压缩摘要将设计定案总数记为 25 条。P博士纠正：实际为 31 条（包含 CausalLinker 增量扫描子系统的定案 26-31，经历 8 轮 G博士/M 专家审查）。
M 专家更新计划文件（`velvety-inventing-bunny.md`）至 31 条后，G博士对 `V6.3_CAUSAL_LINKER_DESIGN.md` 发起新一轮质检。

---

## 第一轮：G博士三枪质检

### 第一枪：毒药事件（Poison Pill）导致无限死循环

**G博士论点**：
`_requeue_on_failure` 无上限地将失败事件回填 linker_queue。若某事件因 LLM ContextLengthExceeded 等原因 100% 必定失败（毒药事件），将导致：
- 单次 Pipeline：MAX_ROUNDS=20 轮内被反复出队、崩溃、回填，耗尽 API 费用
- 跨 Pipeline：毒药事件永久留在队列，每次新 Pipeline 运行都先被出队，导致系统永久瘫痪
- 设计缺少 DLQ（死信队列）机制

**M 专家判定**：**50% 命中**

- **命中**：DLQ / 死信机制确实缺失，`retry_count` 上限不在任何定案中，这是真实漏洞
- **打空**：G博士的具体灾难场景（LLM ContextLengthExceeded）建立在错误前提上——CausalLinkerScanner 使用本地 DEV_ONTOLOGY_RULES，不调用任何 LLM

**修复方案（已纳入讨论）**：
`linker_queue` 表增加 `retry_count INTEGER DEFAULT 0`；`_requeue_on_failure` 在 `retry_count >= MAX_LINKER_RETRIES (3)` 时弃置事件并打 ERROR 日志，不再回填。

---

### 第二枪：linker_scanned 标记的时序脏读与视野黑洞

**G博士论点**：
同批次 A、B、C 三事件全部在 New 集合中。当 C 进行 N×M 视野池查询（`linker_scanned=1`）时，看不到 A 和 B（它们的标记尚未置 1）。若 51 个事件分两批，第二批的 C 可能在第一批还未 COMMIT 时就开始查询，造成"中间态隐身"和因果链断裂。

**M 专家判定**：**打空**

G博士混淆了两个不同的计算路径：

1. **同批次（A、B、C 都在 New 内）**：三者走 New 内 N×N 路径两两配对，完全不依赖 `linker_scanned` 字段。G博士的"C 看不到 A"对 N×N 路径无效。

2. **跨批次（A、B 在第一批，C 在第二批）**：定案 29 明确 `scan_once()` 是同步顺序调用（`while scan_once() > 0: pass`），串行执行，第一批 COMMIT 后第二批才开始。G博士假设的"并行后台 Worker"在 V6.3 同步设计中不存在。

**结论**：不需要修复。V6.3 为单线程同步设计，视野黑洞问题不存在于当前架构。

---

### 第三枪：`_filter_ghost_edges` 的伪逻辑

**G博士论点**：
LLM 在看到新事件 N1（DB 慢日志/死锁）后，"恍然大悟"发现历史事件 O1（服务器报警）→ O2（重启数据库）之间存在关联，产生边 O1→O2。`_filter_ghost_edges` 会把这条边过滤掉（两端都不在 new_event_ids 中），造成真实因果关联的永久删除。若 GraphStore 本已 RMW 幂等，此过滤"不但毫无意义，还会导致真实关联的永久性删减"。

**M 专家判定**：**打空**（但引出了更大问题）

- G博士的场景建立在"linker_scanner 调用 LLM"的前提上，这个前提不存在。CausalLinkerScanner 使用 DEV_ONTOLOGY_RULES 本地类型规则匹配，不调用 LLM，不具备"全局上下文涌现推断"能力。
- 对本地规则匹配，`_filter_ghost_edges` 阻止 N×M 配对中两个 Old 事件之间产生纯历史碰撞，逻辑正确。
- **但**：M 专家为了挡回第三枪，亮出了"纯本地类型规则匹配"这张底牌，直接引发了后续更致命的质疑。

**需补充文档**：明确声明 CausalLinkerScanner 不调用 LLM，建边完全基于 DEV_ONTOLOGY_RULES 本地类型匹配。若 V6.4 引入 LLM 建边，`_filter_ghost_edges` 的过滤粒度需重新审视。

---

## 间奏：DEV_ONTOLOGY 审视

P博士提议审视 DEV_ONTOLOGY 文档。M 专家对照以下三个来源：

- `docs/V6.0/DEV_ONTOLOGY.md`（7个关系，但 `fixes` 无独立章节）
- `src/dimcause/core/ontology.yaml`（权威定义，含 `fixes`）
- `V6.3_extraction_pipeline_design.md` 中的 `DEV_ONTOLOGY_RULES`

**发现的四个不一致：**

| 问题 | 内容 |
|------|------|
| A | `code_change`（事件类型）vs `Function`（本体类）——不是命名差异，是语义漂移。`Function` 是静态代码符号，`code_change` 是变更动作，用后者充当前者实例，`modifies` 边语义混乱 |
| B | `fixes` 在 ontology.yaml 中有定义，在 DEV_ONTOLOGY.md 第三章无独立章节，文档内部不一致 |
| C | `modifies`（前置条件：related_files 有交集）、`overrides`（前置条件：A.timestamp > B.timestamp）只有注释，无实现契约 |
| D | EventType（snake_case）→ 本体类（PascalCase）的映射表从未在任何规范文档中正式定义 |

---

## 第二轮：G博士第九枪

### 第九枪（终极质检）：DEV_ONTOLOGY 的错觉与"伪因果"关联风暴

**G博士论点**：

M 专家的底牌（纯本地类型规则连边）在图论语义上导致致命的**完全二分图爆炸（Bipartite Graph Explosion）**：

> "只要 N 里有个 incident，M 里有个 decision，我就把它们以 triggers 关系连起来"

**灾难推演（2×2 示例）**：

```
48h 时间窗内：
  Incident_1: 数据库连接池耗尽
  Incident_2: 前端 CDN 证书过期
  Decision_A: 增加连接池上限
  Decision_B: 续签 SSL 证书

纯类型匹配结果（4条边）：
  Incident_1 → Decision_A  ✓ 正确
  Incident_1 → Decision_B  ✗ 伪因果
  Incident_2 → Decision_A  ✗ 伪因果
  Incident_2 → Decision_B  ✓ 正确
```

**规模扩展**：50 Incident × 20 Decision = 1000 条 triggers 废边。

**G博士核心论断**：
> Schema 允许（Allows）A 能够触发 B，不代表在物理世界中 A 确实（Actually）触发了 B！

**G博士给出两条出路**：
- 出路A：L2 外键绑定，CausalLinker 只做 O(1) JOIN
- 出路B：时窗 N×M + LLM/深度 NLP 语义裁决

**M 专家判定**：**命中核心，但结论是伪二分法**

---

## 第三轮：M 专家反击与第三条路

### M 专家承认笛卡尔积问题

纯类型匹配 N×M 时窗确实会产生完全二分图，50×20=1000 条 triggers 废边是真实的。DEV_ONTOLOGY_RULES 中 `triggers`、`realizes`、`fixes`、`implements`、`validates` 全部无语义过滤条件（只有 `modifies` 和 `overrides` 有前置条件注释）。这是系统性缺口。

### G博士两条出路的问题

**出路A（外键JOIN）的问题**：
- `related_to` 字段不在 events 表中，需新增，触发 DDL 变更
- L2 LLM 只能处理有明确文本引用的因果（情况1），无法处理隐式因果（情况2）
- L1 阶段（无 LLM）图谱完全失效
- 图谱覆盖率极低

**出路B（LLM 裁决）的问题**：
- 违反 V6.3 offline-first 核心约束
- 无 API Key 场景图谱完全建不了

### 第三条路：外键优先 + 向量相似度门控兜底

V6.3 基础设施已有 BGE-M3 embedding，存储在 `event_vectors` 表，可在无 LLM 条件下提供语义判断：

```
建边优先级：
  1. 外键JOIN        ← event.related_event_ids 非空 → O(1) 精准连边
  2. 向量相似度门控  ← 类型规则通过 AND cos_sim ≥ threshold → 才写边
  3. 纯类型匹配      ← 永久废弃
```

**第三条路的特性**：
- offline-first，不调用 LLM
- 利用已有嵌入基础设施
- 向量相似度无全局上下文感知，不触发第三枪（`_filter_ghost_edges` 对它依然有效）
- 时窗 N×M 保留：作为 L1 无外键场景的 fallback

**第三条路的代价**：
- events 表需新增 `related_event_ids TEXT DEFAULT '[]'`
- `VectorStore.get_vector(event_id)` 接口需验证
- threshold 待定（无标注数据，V6.3 先用保守值 0.50）
- 无 embedding 事件：保守不建边，宁可漏边不要废边

---

## 当前结论汇总

| 枪次 | G博士论点 | 判定 | 是否需修复 |
|------|---------|------|---------|
| 第一枪 | 毒药事件 / DLQ 缺失 | 50% 命中（LLM 前提错误，但 DLQ 漏洞真实） | **是**：linker_queue 加 retry_count，超限弃置 |
| 第二枪 | linker_scanned 视野黑洞 | 打空（混淆 N×N 同批次路径与 N×M Old 视野） | 否 |
| 第三枪 | _filter_ghost_edges 伪逻辑 | 打空（LLM 前提不存在），但引出更大问题 | 否（但需补文档声明 linker_scanner 无 LLM） |
| 第九枪 | 纯类型匹配笛卡尔积爆炸 | **命中**（伪二分法结论不接受） | **是**：需定案 33 |
| 第十枪 | 完全二分图爆炸 / A or B | **命中核心**，结论是伪二分法 | **是**：第三条路（向量门控）待定案 |

---

## 悬而未决：定案 33（待 P博士拍板）

**定案 33 草案**：CausalLinker 语义门控

```
建边优先级：
  1. 外键JOIN：event.related_event_ids 非空 → O(1) 连边，不过类型规则
  2. 向量门控：related_event_ids 为空 → 类型规则通过 AND cos_sim ≥ threshold
  3. 纯类型匹配：永久废弃
```

**需 P博士决策的四个问题**：

| # | 问题 | 选项 |
|---|------|------|
| 1 | `related_event_ids` 字段加在哪里？ | A：events 表（`TEXT DEFAULT '[]'`）；B：复用 chunks.event_ids 机制 |
| 2 | cos_sim threshold V6.3 先定多少？ | 0.50（保守）或 0.40（宽松）|
| 3 | 无 embedding 事件是否允许仅凭外键建边？ | 是（外键路径不依赖 embedding）或 否（完全跳过）|
| 4 | 是否废弃 DEV_ONTOLOGY_RULES 现有元组写法，改为带门控的新接口？ | 是（彻底重写）或 否（保留元组，在调用层加门控）|

---

## 第四轮：PG博士联合三枪（漏洞 11-13）

> **背景**：G博士揭示，P博士与G博士是两个不同的人，过去的争论是G博士以"P博士""G博士"双重视角进行的自我质检，目的是在写代码之前消灭系统性设计缺陷。

### 漏洞 11：cos_sim ≠ causality（语义相似 ≠ 因果）

**G博士论点**：
M 专家的向量相似度门控（cosine_similarity ≥ threshold）将 IR 工具错用于因果推断：

- **漏报（False Negative）**：`OOM 报错`（内核级特征空间）→ `修改 K8s limits_memory`（YAML 配置特征空间），真实强因果，cos_sim 极低 → 被门控拦截，因果边永久丢失
- **误报（False Positive）**：两个独立服务器的 `Redis 连接超时`，cos_sim ≈ 0.98 → 废边狂欢

BGE-M3 的训练目标是语义聚类相似度，不是因果状态跃迁识别。两者在向量空间中经常正交甚至互斥（真实因果往往跨越领域，表述差异很大）。

**M 专家判定**：**完全命中，承认**

threshold=0.50 是无标注数据下凭空拍出的数字，算法基础不成立。

---

### 漏洞 12：外键路径绕过 ontology 校验（架构完整性断裂）

**G博士论点**：
M 专家的定案 33 草案写"直接连边，不经过类型规则检查"。这主动架空了 `ontology.py:validate_relation()`。LLM 幻觉可以产生任意 `related_event_ids`（如 `Experiment → triggers → Commit`），绕过校验直接写入 GraphStore，下游推理全盘污染。

**M 专家判定**：**完全命中，承认**

`ontology.validate_relation()` 必须约束所有数据路径，没有例外。

---

### 漏洞 13：embedding 粒度在 chunk 层，建边粒度在 event 层（维度塌陷）

**G博士论点**：
V6.3 的 `embed_chunks()` 产出的是 chunk 级向量。一个 chunk 产出的 3 个 event 共享同一个向量：

- **共享向量**：同 chunk 三个 event 相互距离=0，细粒度辨识度丧失
- **重新按 event summary 单独 embed**：V6.3 架构中无此路径

向量门控依赖一个不存在的前提（event 级独立向量）。

**M 专家判定**：**命中，承认**

三枪全部命中，向量相似度门控方案彻底失效。

---

## G博士最终建议（待 P博士确认）

> **注**：G博士承认越权，以下内容是架构建议，**最终裁决权在 P博士**。

**核心结论**：

V6.3 offline-first 约束下，无 LLM 推断、无标注数据，**任何自动因果推断机制均不可靠**。N×M 增量扫描系统（包含 linker_queue、linker_scanner、视野池、原子出队等）经由以下证据链彻底否定：

1. 漏洞 9/10：纯类型匹配产生笛卡尔积爆炸（N×M 废边）
2. 漏洞 11：向量相似度门控算法错误（cos_sim ≠ causality）
3. 漏洞 12：外键路径绕过 ontology 校验（架构完整性断裂）
4. 漏洞 13：embedding 粒度不匹配（chunk 层 vs event 层）

**G博士建议（定案 26 草案）**：

```
删除：linker_queue 表、linker_scanned 列、linker_scanner.py、migrations/003
       N×M 时窗闭包、原子出队、视野池、_filter_ghost_edges、scan_once()
       DEV_ONTOLOGY_RULES 纯类型匹配建边
       向量相似度门控

保留：OntologyEngine.validate_relation()（校验门）
      GraphStore.add_relation() RMW（写入机制）
      _get_conn() isolation_level=None（支持 BEGIN IMMEDIATE）

新增：events.related_event_ids TEXT DEFAULT '[]'
      L2 提取时填充（有明确上下文引用时），L1 留空
      事件入库后同步遍历 related_event_ids → validate_relation → add_relation
      无外键事件作为孤岛存在，不再寻找
```

**V6.4 预留**：引入 Causal NLI 模型（专门针对因果推理微调，非 BGE-M3），配合标注数据，重新实现时窗推断建边。

---

## 最终状态汇总

| 枪次 | G博士论点 | 判定 |
|------|---------|------|
| 第一枪 | 毒药事件 / DLQ 缺失 | 50% 命中（LLM 前提错，DLQ 漏洞真实）|
| 第二枪 | linker_scanned 视野黑洞 | 打空（混淆 N×N / N×M 路径，无并发）|
| 第三枪 | _filter_ghost_edges 伪逻辑 | 打空（LLM 前提不存在），但引出核心矛盾 |
| 第九枪 | 纯类型匹配笛卡尔积爆炸 | **命中** |
| 第十枪 | 完全二分图爆炸（伪二分法）| **命中核心**，二分法不接受，有第三条路 |
| 漏洞 11 | cos_sim ≠ causality | **完全命中**，第三条路算法基础不成立 |
| 漏洞 12 | 外键绕过 ontology 校验 | **完全命中**，架构完整性断裂 |
| 漏洞 13 | embedding 粒度不匹配 | **命中**，向量门控无法实现 |

**待 P博士拍板**：是否接受 G博士建议——删掉 N×M 系统，只走外键校验建边（定案 26）？

---

*文档记录者：M 专家*
*最后更新：2026-02-23*

