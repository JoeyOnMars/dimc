# Task 008 Contract: L3 SchemaValidator (P0 Architecture)

**risk_level: high**

## 1. 目标与背景 (Goal & Context)

在现有的 DIMCAUSE V6.1 架构中：
- `CausalEngine` 成功锁死了因果边的写入（时空防线 + 孤岛拦截）。
- `ExtractionPipeline` 具有了外键校验与关系路由（`_link_causal_edges`）。
- **缺失的环节**：目前 `EventIndex` 层面缺乏对 **实体定义**的硬性校验。任何代码（如各种 Importer、CLI 测试用例等）都可以通过 `EventIndex.add()` 强行写入未在 `ontology.yaml` 中定义的垃圾事件类型 (Event Type) 或实体结构，这导致了底层知识库随时面临被非法本体污染的风险。

本契约的目的是在 Layer 3 补齐 **SchemaValidator** 本体防波堤，将其作为 `EventIndex.add()` 等入库方法的硬核前导卡口。

## 2. 详细设计 (Detailed Design)

### 2.1 运行时卡口位置
SchemaValidator 不能仅靠 `ExtractionPipeline` 单点拦截，因为数据入口多。必须在尽可能底层的入口部署。
拦截点定位：
- `src/dimcause/core/event_index.py` 的核心写入方法：
  - `add()`
  - `add_if_not_exists()`

### 2.2 SchemaValidator 的职责
创建 `src/dimcause/core/schema_validator.py`，核心逻辑为：
1. **实体类型拦截 (Entity Type Validation)**：
   - 验证 `Event.type` 是否存在于 `ontology.yaml` 声明的 `classes` 集合中（通过 `Ontology` 获取）。
   - 由于现有的 `EventType` 枚举包含了一些为了兼容旧版（如 diagnostic, ai_conversation 等）而定义的值，我们在拦截时需要做严格过滤。只有在 `ontology.yaml` 中或者由系统向下兼容白名单允许的类型，才能入库。
2. **拒绝策略**：直接抛出结构化的 Schema 异常（例如 `OntologySchemaError`），阻止 `EventIndex` 写入。

### 2.3 物理边界与依赖
- **禁止修改**：`CausalEngine` 和 `GraphStore`。它们主要负责边（Edges）的防护，SchemaValidator 负责节点（Nodes/Events）的防护，职责完全隔离。
- **关联文件**：
  - `src/dimcause/core/schema_validator.py` [NEW]
  - `src/dimcause/core/event_index.py` [MODIFY]
  - `tests/core/test_schema_validator.py` [NEW] 

## 3. 测试与验证期望 (Acceptance Criteria)

1. **红线拦截测试**：在测试用例中强行构造 `Event(type="some_garbage_type")` 并调用 `EventIndex.add()`，系统必须立即抛出 `OntologySchemaError`，且 SQLite `events` 表行数不变。
2. **合法准入测试**：使用 `ontology.yaml` 定义的合法类型（如 `Commit`, `Decision`, `Incident` 等）构造 Event，`EventIndex.add()` 顺畅入库。
3. **老数据兼容**：如果历史 DB 中存在未知类型的脏数据，`EventIndex.get()` 读取时不崩溃，但新的不受信任写入被严厉禁止。

## 4. 授权协议 (Authorization)

一旦 User 审批此契约（盖章 Approved），即可授权 M 专家：
1. 创建 `schema_validator.py` 并定义检查逻辑。
2. 在 `EventIndex.add` 与 `add_if_not_exists` 第一行物理植入该卡口。
3. 编写对应单元测试并保证 `pytest tests/core` 通过。
