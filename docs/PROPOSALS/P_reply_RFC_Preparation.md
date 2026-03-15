# 给G博士和专家的回复
先把话说清楚：下面这些回答，就是我在写 V6.3 提取 RFC 时要当成“锁死前提”的设计结论。后面 RFC 只是在这些锚点之上展开细节，而不会再摇摆。

***

## 一、chunks 表放哪、物理边界怎么定？

**结论：chunks 表放在现有的 `code.db`（Information 层主库）里，与 EventIndex 和 VectorStore 同库、不同表，不新开独立 DB。** [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

理由与边界：

- `code.db` 当前已经承载：  
  - EventIndex 的元数据表（事件索引）；  
  - `event_vectors` / `vectors_index` 等 sqlite‑vec 虚拟表；  
  - GraphStore 的 `graph_nodes` / `graph_edges` 等结构。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
  这就是 L2 信息层的主库。
- chunks 是「从原始 Session 流到最终 Event 的中间态」，本质上也是信息层的索引数据，而不是新的“仓库”。放在同一个库里：  
  - 可以在同一事务里完成「chunk 状态推进 + EventIndex 更新 + 向量表更新」；  
  - 避免跨库事务和两阶段提交的复杂度。

**清理策略（防止 code.db 变成垃圾场）：**

- 表结构（在 `code.db` 内）：  

  ```text
  chunks(
    chunk_id TEXT PRIMARY KEY,
    source_event_id TEXT,        -- 来自哪个 L0 事件 / 消息
    session_id TEXT,
    status TEXT,                 -- raw / embedded / extracted
    confidence TEXT,             -- low / high
    needs_extraction BOOLEAN,
    embedding_version INTEGER,
    extraction_version INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    last_error TEXT NULL         -- 记录最近一次 L2 失败原因
  )
  ```

- GC 策略（写进 RFC）：  
  - 当满足以下全部条件时，允许后台 GC 定期删除该 chunk 行：  
    - `status = 'extracted'`；  
    - `embedding_version == CURRENT_EMBEDDING_VERSION`；  
    - `extraction_version == CURRENT_EXTRACTION_VERSION`；  
    - `updated_at` 早于 N 天之前（例如 7 或 30 天，可配置）。  
  - 删除的是 **chunk 行及其冗余文本/中间字段**，但最终 Event 本身已经落入 EventIndex + Markdown + GraphStore，不受影响。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
- 若未来有“用于训练/审计的完整流水线回放”需求，可以在 GC 前导出 chunks 到归档文件（例如 NDJSON），但那是「另一个离线过程」，不改变线上 DB 结构。

这样可以回答 G 博士的第一个质询：  
**方案选 B，但做成“同库不同域 + 明确 GC 规则”，而不是把 chunks 变成新的主仓，更不会让它长期膨胀到百万行的只读垃圾。** [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

***

## 二、Event Schema 版本化：按条记录，不搞全局“一刀切”

**结论：Event 与 chunks 都携带 `embedding_version` / `extraction_version` 字段，版本号是 per‑record 的，同时在配置里维护当前版本常量。** [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)

- Dev‑Ontology 已经把 Event 视为 Data 层实例、Relations 为 Information 层的事实。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
  一旦 embedding 或提取算法升级，同一 Event 的“老向量”和“新向量”行为会不同，所以必须能在实例层区分版本。
- 设计：  
  - 在 Event 存储（Markdown front‑matter + EventIndex）中加入：  

    ```yaml
    embedding_version: 1
    extraction_version: 1
    confidence: high|low
    ```

  - 应用配置中维护当前算法版本常量：  

    ```python
    CURRENT_EMBEDDING_VERSION = 2
    CURRENT_EXTRACTION_VERSION = 3
    ```

  - 任何使用向量 / 因果链的高层功能（如 `dimc search` / `dimc why`）可以选择：  
    - 仅使用 `embedding_version == CURRENT_*` 的记录；  
    - 或在需要时触发重建任务，对落后版本的 Event 批次重算 embedding / L2。  

**这解决两个问题：**

- 旧 Event 不会因为新算法上线而变成“不可用黑箱”；  
- 重建可以渐进式进行（按时间 / 按仓库），而不是一次性全库大迁移。

***

## 三、L0 触发方式：首选 Watcher，轮询作为兜底

**结论：L0 监听采用「文件系统 Watcher + 低频轮询」的组合策略：**

- 主路径：  
  - 复用现有的 `FileWatcher` / `ExportWatcher` 设计， 在 L0 增加一个 `EventLogWatcher`，利用 `watchdog` 监听 Claude JSONL / AG_Exports 目录的变更事件。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/d6ab1635-26e3-4d33-b48a-c62b055a9e0d/PROJECT_ARCHITECTURE.md)
  - 每次检测到新增/增长，就从上次 offset 继续读，生成 L0 事件（带 `source_event_id` 和 `session_id`），写入 EventLog / chunks。  
- 兜底路径：  
  - 每隔 N 分钟（例如 5 分钟）做一次轻量级扫描，对比文件 `mtime` 与上次记录的 offset：  
    - 如果 missed（如 watcher 进程挂了），补采丢失部分；  
    - 这可以作为“容错网”，避免因为单纯依赖 Watcher 而导致长时间漏记事件。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/d6ab1635-26e3-4d33-b48a-c62b055a9e0d/PROJECT_ARCHITECTURE.md)

RFC 会明确：

- L0 属于 L0 基础设施层（Event 捕获），实现必须满足「崩溃可恢复 + 不丢一行」的 WAL 精神，与项目现有的 WAL / Daemon 策略对齐。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/d6ab1635-26e3-4d33-b48a-c62b055a9e0d/PROJECT_ARCHITECTURE.md)
- Watcher 是性能优化，而非唯一真相源；真相仍然是「文件内容 + offset 记录」。

***

## 四、提取失败重试与熔断策略

**结论：L2 提取失败既不能静默吞，也不能无限重试；要有显式状态与上限。**

在 `chunks` 表里增加两个字段（或在单独表中也可）：  

```text
retry_count INTEGER DEFAULT 0,
last_error TEXT NULL
```

策略：

1. **可重试错误（网络故障、5xx、超时）：**  
   - 每次失败 `retry_count += 1`，记录 `last_error`；  
   - 采用指数退避（如 1min/5min/30min），由 ExtractionWorker 控制下次调度时间；  
   - 超过 `MAX_RETRIES`（例如 3 次）后：  
     - 将 `needs_extraction = false`；  
     - 保留 `status = embedded`、`confidence = low`；  
     - 标记为 `extraction_failed = true`（可新加字段），供 CLI/监控查看。  

2. **硬错误（JSON schema 校验失败、关键字段缺失）：**  
   - 视为「实现 bug 或 prompt 问题」，同样限制重试次数；  
   - 在日志中明确打出「schema validation failed」并附上 chunk_id，方便开发侧修 prompt / parser。  
   - 默认不写入任何半吊子 Event，避免污染 GraphStore / EventIndex。  

3. **人工干预入口：**  
   - 提供一个 `dimc extract --requeue-failed` 命令，将 `extraction_failed = true` 的 chunk 重置为 `needs_extraction = true, retry_count = 0`，在修复 prompt/实现后重跑。  

***

## 五、回答 G 博士的三大“破坏性”质询

### 1. Schema 合并：chunks vs EventIndex/VectorStore

> 破坏性 Schema 合并：新 chunks 表与旧有 EventIndex 及其 VectorStore 的边界在哪里？会不会把现有百万行只读表搅烂？

**边界原则：**

- Markdown + EventIndex + GraphStore + VectorStore 仍然是**最终事实层**：  
  - Markdown 是原文档 / end.md / 事件说明的 Source of Truth；  
  - EventIndex 提供事件元数据索引（时间、类型、路径等）； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
  - VectorStore 存储事件级 embedding； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)
  - GraphStore 维护 DEV_ONTOLOGY 定义的节点与边。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
- chunks 只承担「从 Session 流到 Event 的流水线中间态」，不会被上层 API 直接暴露给用户查询。

**物理设计回答：**

- 选用 **方案 B 的变体**：  
  - chunks 表添加在 `code.db` 中，但：  
    - 有独立命名空间和索引前缀（如 `chunks_*`），不与现有表名冲突；  
    - 不更改现有 EventIndex / VectorStore 表的 schema（除非为版本字段做向前兼容扩展）。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
- 清理策略（见上）：  
  - extracted + 版本匹配 + 超过保留期的 chunk 行会被定期 GC；  
  - 因此不会长期和 EventIndex 一起膨胀到难以维护的体量。  

**对事务的一句话：**

- RFC 会写明：  
  - L2 成功时，一个事务内完成：  
    - 更新 chunks.status / confidence / version；  
    - 写入/更新 Event（Markdown + EventIndex）；  
    - 写入向量表或更新 GraphStore 边。  
  - 失败则整体回滚，不存在“写了一半”的 schema 混乱。

### 2. 图谱断裂：异步侧车如何重建跨 Chunk 的因果边？

> 当 Worker 1 处理报错 Chunk A，Worker 2 很久以后处理决策 Chunk B，它们如何在 GraphStore 里形成 Incident → Decision、Decision → Commit 这些因果边？ [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)

这里要区分两个层次：

1. **L2 Extraction 的职责：生成节点（Event）及其局部证据**  
   - 每个 chunk 的 L2 仅负责从局部文本中抽取：  
     - 事件类型（Incident / Decision / Experiment / Commit 等，来自 DEV‑Ontology 的类）； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
     - 局部属性（summary、rationale、files_changed、command、error_message 等）；  
     - 关键锚点：  
       - `session_id`；  
       - `message_span`（在 Session 内的起止消息/offset）；  
       - 相关文件/函数 URI（如 `dev://function/...`）。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)

2. **因果边的重建由一个「CausalLinker」在第二阶段统一负责**  
   - 现有 GraphStore 已经把「节点/边持久化 + NetworkX 作为计算层」的模式定下来了。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
   - 在 V6.3 中，RFC 会新增一个明确的组件职责（可以是 GraphStore 内部的 service）：  
     - 周期性扫描新生成的 Event（带 `session_id` / timestamp / 类型）；  
     - 基于 DEV‑Ontology 定义的关系和公理，按一套确定性的（+少量 embedding 检索辅助的）规则生成边：  
       - 同一 `session_id` 内，某 Incident X 与后续最近的 Decision Y 之间，有条件地加 `triggers` 边； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
       - 某 Decision Y 与之后包含对应文件/函数的 Commit Z 之间，加 `realizes` / `modifies` 边； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
       - 同一 Session 内一系列尝试 + 最终 Decision，可以产生 `overrides` 等边。  

**关键点：**  

- **LLM 不直接画边，它只帮你识别「候选节点+局部证据」。**  
- 边的生成是：  
  - 使用事件时间戳、session_id、有无共享文件/函数 URI、embedding 相似度等规则，由本地 CausalLinker 统一计算；  
  - 这一步完全可以在本地、离线完成，且可以多次重跑（对准新的本体规则或算法）。  

因此，即便 Chunk A 与 Chunk B 在 L2 中是「不同 Worker、不同时间处理」，最终：

- 只要二者带着同一 `session_id` + 合理的时间顺序 + 文件/函数锚点；  
- CausalLinker 就能在 GraphStore 中把它们连成 Incident → Decision → Commit 这样的因果链。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

**RFC 中会显式增加「因果链接阶段」这一节，把图谱构建从 L2 Extraction 中剥离出去，避免“每个 Worker 自己乱连边”的混乱。**

### 3. 契约与 schema 校验：如何不破坏 api_contracts？

> L2 用云端 LLM，可能吐乱 JSON；L1 的正则也可能产出简陋结构。  
> 是否必须在写入前强制通过 schema 校验？失败是 retry 还是降级保存？ [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)

**这里的红线很清楚：**

1. **所有对外可见的 API / 数据结构，都要通过 `api_contracts.yaml` + schema 模块校验后才能落盘或返回。** [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)
   - sanitize / sanitize_file 已经这样做了；  
   - 新增的 `/chunks`、`/extract` 等内部接口，也要在 `api_contracts.yaml` 中定义签名与返回结构，即便暂时只在内部使用。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)

2. **L2 的原始 JSON 视为“不可信输入”，必经 schema 校验才能转成 Event。**  
   - 云端 LLM 的返回先进入一个「unsafe JSON」对象；  
   - 再通过严格的 schema（可以由 Pydantic /自定义校验器根据 Dev‑Ontology 生成）进行验证：  
     - 键名必须符合预期；  
     - 缺少关键字段则视为 schema error，不写入 EventIndex / GraphStore。  

3. **失败处理与 FSM 对齐：**

- 若 schema 校验失败：  
  - 记录到 chunks.last_error 中；  
  - `retry_count += 1`，少量重试（例如允许开发者修 prompt 后触发 requeue）；  
  - 超过上限后：  
    - 不写入任何不合规 Event；  
    - chunks 保持 `status = embedded, confidence = low, needs_extraction = false, extraction_failed = true`；  
    - 依靠 L1 的向量检索和粗规则，用户仍然可以「搜到原始语境，但没有高阶结构」。  

- 不会出现“降级保存一堆非法键名的 Event”这种污染存量真源的行为。  

**对 L1 的要求：**

- L1 的输出（规则提取）只在本地使用，生成的结构要么：  
  - 先被 L2 重算覆盖；  
  - 要么也走同一套 schema 校验后，才作为低置信度 Event 写入存储。  
- 这意味着：**哪怕是本地正则提取，也不能直接随意往 EventIndex 里塞“半结构垃圾”；必须通过统一 schema 模块。**

RFC 里会明确：  
> 「任何写入 EventIndex / GraphStore / 对外 API 的结构化数据，必须经过 schema 校验；schema 校验失败的结果一律不写入，仅保留在 chunks 状态机中作为失败记录。」

***

## 六、最后的小结（给你确认用）

你和 G 博士、M 专家抛出的所有关键问题，现在都有了可以落在 RFC 里的硬答案：

- chunks 放在 `code.db`，与 EventIndex/VectorStore 同库，配 GC，属于信息层流水线，不篡位。  
- Event / chunk 按条记录维护 embedding_version / extraction_version，而不是只靠全局配置。  
- L0 采用 watcher+轮询的组合，保证「不丢字节」，和现有 watcher 架构对齐。  
- L2 失败有明确重试/熔断策略，不会无限打 API，也不会写入垃圾结构。  
- Graph 边的生成从异步 Worker 中抽离，由统一的 CausalLinker 基于 Dev‑Ontology 在本地重建因果网络。  
- 所有新旧结构都受 `api_contracts.yaml` + schema 校验约束，L2 只是“候选 JSON 生产者”，不是契约定义者。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/b349eef8-3975-4a24-9822-aae23c0c4799/DIMC_DOWN_FLOW.md)



# 直接回答专家的三个问题，并给出 RFC 里应该写死的结论。

***

## 1. 存储位置：选 B，但“同库不同域 + 有 GC”，不是粗暴侵入

**问题重述**：  
- A：新建独立 SQLite（Broker）；  
- B：把 chunks 丢进现有 event_index.db / code.db，担心搅乱百万行旧数据。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

**结论（写进 RFC 的版本）：**

- **选择方案 B 的变体**：  
  - `chunks` 表放在现有 `code.db`（Information 层主库）中，与 `events` / `event_vectors` / `graph_nodes` 等并列。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
  - 理由：  
    - 让「Chunk FSM → EventIndex → VectorStore → GraphStore」可以在同一个事务内完成，避免跨库分布式事务。  
    - 避免多 DB 带来的部署和备份复杂度（已有设计就是 “Markdown + 单 SQLite 主库 + 附属 graph.db”）。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

- **边界与不变量**：  
  - 现有表（`events`、向量表、图表）的 schema 不做破坏性变更，只允许向前兼容式增加列（如 version 字段）。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)
  - `chunks` 只承担「流水线中间态」，**不会被任何对外 API 暴露为“可查询主表”**，不会取代 EventIndex/VectorStore 的角色。

- **GC / 清理策略**（防止 code.db 被垃圾填满）：  
  - `chunks` 字段（核心）：  

    ```text
    chunk_id TEXT PRIMARY KEY
    source_event_id TEXT
    session_id TEXT
    status: raw / embedded / extracted
    confidence: low / high
    needs_extraction: BOOLEAN
    embedding_version: INTEGER
    extraction_version: INTEGER
    retry_count: INTEGER
    last_error: TEXT
    created_at, updated_at: DATETIME
    ```  

  - 周期性 GC 规则：  
    - 满足以下全部条件时允许删除该 chunk：  
      - `status = 'extracted'`；  
      - `embedding_version == CURRENT_EMBEDDING_VERSION`；  
      - `extraction_version == CURRENT_EXTRACTION_VERSION`；  
      - `updated_at` 早于 N 天（如 7/30，配置项）。  
    - 删除仅影响 chunks；对应 Event 已经落入 Markdown + EventIndex + GraphStore + VectorStore，不会丢事实数据。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/685c7b94-ef7c-41fe-9330-1b8ac8df3ede/STORAGE_ARCHITECTURE.md)

> 写在 RFC 里的话：**“chunks 表位于 code.db，同库不同域；已提纯且版本对齐的 chunk 将按保留期 GC，不与 EventIndex 竞争主存储角色。”**

***

## 2. 异步因果边：LLM 只造节点，因果关系由本地 CausalLinker 二阶段重建

**问题重述**：  
- 旧版一次性喂 3MB，是为了在同一大上下文里直接问 LLM：`<Command> → <Error> → <Decision>`，顺手把因果也算出来。  
- 现在切成 800 token chunk，Worker1 先处理报错 A，Worker2 很久后处理决策 B，如何在 GraphStore 中画出 Incident → Decision / Decision → Commit 等边？ [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/b349eef8-3975-4a24-9822-aae23c0c4799/DIMC_DOWN_FLOW.md)

**结论（架构上必须改的理念）：**

1. **LLM 的职责下沉为“节点构造 + 局部证据提取”，不再直接画因果边。**  
   - L2 ExtractionWorker 对每个 chunk 只负责：  
     - 判断事件类型（Incident / Decision / Experiment / Commit…），对齐 DEV_ONTOLOGY 里的类。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
     - 填充该事件的本地属性（summary、rationale、command、error_message、files_changed、related_functions 等）。  
     - 记住锚点：  
       - `session_id`；  
       - 时间戳 / 在会话中的顺序（message_span）；  
       - 相关 URI（文件、函数、需求、事故 ID 等）。 [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
   - 这些结果写入 Event（Markdown + EventIndex + GraphStore 节点），但**不直接创建 triggers/realizes/overrides 等关系边。**

2. **因果边统一由本地 CausalLinker 在第二阶段生成**（GraphStore 层的“投影/投影器”）： [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
   - 新增或扩展一个组件（可在 `graph_store.py` 内，或单独 `causal_linker.py`）：  
     - 定期扫描：最近 N 小时 / N 天内新增 / 更新的 Event；  
     - 使用：  
       - session_id；  
       - 时间顺序；  
       - 共享实体（文件、函数、Incident/Decision ID 等）；  
       - 必要时的 embedding 相似度；  
     - 按 DEV_ONTOLOGY 公理生成边：  
       - 同一 session 内：  
         - Incident 之后最近的 Decision → `triggers`； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
         - Decision 之后修改对应函数/文件的 Commit → `realizes` / `modifies`； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)
         - 一系列相互否定的 Decision → `overrides`。  
   - 这一步完全在本地、离线执行，**可以多次重跑**（Schema 升级或算法改进时，只要重算 CausalLinker 即可），不依赖云。

3. **跨 chunk 串联因果的关键在于“稳定标签”，而不是“Worker 同步处理”：**

   只要 Worker1/2 在写节点时，保证：  

   - 统一的 `session_id`；  
   - 正确的时间戳/序号；  
   - 对同一 Incident / 需求 / 函数使用一致的 URI（例如 `dev://incident/INC-042`、`dev://function/auth_py#get_connection`）； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/27881c14-60bc-4bf3-b2c2-4cc7df3f60e2/DEV_ONTOLOGY.md)

   那么 CausalLinker 就能事后把 A 和 B 关联起来；  
   Worker 是否并行、何时处理已经不重要，**顺序由事件时间线和标识符保证，而不是由“单次 LLM 大上下文”保证。**  

> 写在 RFC 里的话：  
> “V6.3 将因果边生成从 L2 Extraction 中抽离，改由 GraphStore 上的 CausalLinker 统一负责。Extraction 仅产生活动节点和局部证据；triggers/realizes/overrides 等关系由本地规则 + 时间/URI/embedding 统一重建，支持全库重算。”

***

## 3. Schema 冲突：强制校验，失配不落盘，只在 chunks 中标记失败 + 有限重试

**问题重述**：  
- `api_contracts.yaml` 已经为 sanitize / sanitize_file / search 等函数定义了输入输出契约； [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)
- 新的 L2 云端提纯返回 JSON 可能键名乱飞；L1 正则产物也可能结构简陋。  
- 问题：  
  - 是否必须强制 schema 校验？  
  - 校验失败是无限重试、还是带错误降级存表？

**结论（这是红线）：**

1. **所有进入核心存储层（EventIndex / GraphStore / VectorStore）的结构化数据，必须在本地通过 schema 校验，schema 来源受 `api_contracts.yaml` 约束。** [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/8547617/1e6e6b27-203b-4955-bf70-526f3aa18856/api_contracts.yaml)
   - 新增 `/chunks`、`/extract` 等内部接口时，同样要在 `api_contracts.yaml` 里登记签名和返回结构；  
   - 可以用 Pydantic 或自定义 `schema.py` 读取 contract 生成校验器，但**绝不能直接把 LLM 的 raw JSON 写进 Event**。  

2. **L2 的返回视为“不可信 JSON”，先 parse，再按 Schema 校验：**  

   - 步骤：  
     1. ExtractionWorker 调云端 LLM，拿到字符串；  
     2. 本地尝试 `json.loads` / 结构提取，得到 Python dict；  
     3. 将 dict 喂入 schema 校验器：  
        - 键名、字段类型、必填字段缺失、非法枚举一律在此被拦截；  
     4. 只有通过校验的结构才被转换为 Event 并写入存储。  

3. **校验失败/网络错误，统一走 FSM + 有限重试，不写半吊子 Event：**

   - 可重试错误（网络/5xx/超时）：  
     - `retry_count += 1`；  
     - 低于 `MAX_RETRIES`（如 3）时重试，采用指数退避；  
     - 超过上限：  
       - `needs_extraction = false`；  
       - `extraction_failed = true`（新增字段）；  
       - 保持 `status = embedded, confidence = low`，即只保留 L1 结果。  

   - schema 校验错误（乱键名、缺字段）：  
     - 视为实现问题或 prompt 问题；  
     - 记录 `last_error = 'schema_validation_failed: ...'`；  
     - 同样有限重试（允许开发者修代码后 requeue）；  
     - 任何时候**都不把不合规结构写入 EventIndex / GraphStore**。  

   - 降级含义：  
     - 降级只体现在「停留在 L1，用户只能得到粗结构 + 向量检索」，**不会降级成“写一条畸形 Event 进去”**。  

4. **给运维/开发预留 requeue 通道：**

   - 例如 `dimc extract --requeue-failed`：  
     - 将 `extraction_failed = true` 的 chunk 重置为 `needs_extraction = true, retry_count = 0`，在修好 prompt/schema 后重跑。  

> RFC 里的话：  
> “任何写入 EventIndex / GraphStore 的 L2 产出，必须在本地通过依据 api_contracts.yaml 派生的 schema 校验，校验失败的结果一律不入库，仅记录在 chunks 状态机中并按重试策略处理；系统不接受任意形态的‘幻觉 JSON’污染真源。”

***

## 总结成一句可以写在 RFC 开头的承诺

> **V6.3 的 Local‑First 提取引擎，在物理上不引入新的主库，只在现有 code.db 内增设可 GC 的 chunks 流水线表；在语义上把 LLM 职责限定为“节点+局部证据”，将因果边重建统一下沉到本地 CausalLinker；在契约层强制通过 api_contracts.yaml + schema 校验，任何不合规 JSON 不会写入核心事件/图谱存储。**

这三点写清楚，才算真正消除了你说的那三个“会破坏现有系统完整性”的隐患。