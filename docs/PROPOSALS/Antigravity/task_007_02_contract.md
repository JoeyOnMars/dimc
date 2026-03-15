# Task 007-02 Contract: Extraction Pipeline 升级与因果引擎传参适配

## 1. 目标 (Goal)
升级 `ExtractionPipeline`，在生成/提取 `Event` 实体时，将 `ChunkRecord` 中的 `session_id` 正确注入到 `Event.metadata` 中。这将为 `CausalEngine.link_causal` 提供必备的拓扑锚点，使得新创建的因果边能够平滑通过 `TopologicalIsolationError`（防线 B）的结构孤岛拦截验证。

## 2. 授权修改范围 (Scope)

### [MODIFY] src/dimcause/extractors/extraction_pipeline.py
*   **方法**: `ExtractionPipeline._make_event`
    *   **改动**: 在实例化 `Event` 的参数中，显式添加 `metadata={"session_id": chunk.session_id}`。
*   **方法**: `ExtractionPipeline._run_l2`
    *   **改动**: 在遍历大模型返回的 `events` 列表重写 ID 的阶段，追加对 `metadata` 的初始化与 `session_id` 写入逻辑：
        ```python
        if ev.metadata is None:
            ev.metadata = {}
        ev.metadata["session_id"] = chunk.session_id
        ```

### [MODIFY] tests/test_extraction_pipeline.py
*   **方法**: `test_link_causal_edges_triggered`
    *   **改动**: 
        1. 调整原本均为 `DECISION` 的源事件与目标事件，使其符合本体关系校验（例：`INCIDENT` triggers `DECISION`）。
        2. 给事件注入合法的 `metadata={"session_id": "test_sess"}`。
        3. 验证触发真实建边逻辑时，`TopologicalIsolationError` 能够被防线 B 拦截网络正常接纳（因为交集不再为空），同时验证如果强行模拟差异 session_id 时，Pipeline 的容错 catch 块正确拦截 warning 而不导致整体 crash。

## 3. 验收标准与验证计划 (Verification Plan)
*   执行 `pytest tests/test_extraction_pipeline.py -v` 必须 100% 通过。
*   无形隐患拦截：即使是真实建边，也不会由于缺少 `session_id` 发生崩溃。

## 4. API 契约声明 (API Contracts)
*   **无变更**。遵循 `docs/api_contracts.yaml` 中现有定义：`ExtractionPipeline` 内部调用 `CausalEngine.link_causal` 发生时受保护的隔离拦截策略将被遵守。

## 5. M 专家执行指令 (Execution Instructions)
1. **核心逻辑**：修改 `src/dimcause/extractors/extraction_pipeline.py` 和 `tests/test_extraction_pipeline.py`，如第 2 节 "授权修改范围" 所述。
2. **测试防线验证 (仅限增量测试)**：
   修改完成后，**只允许** 运行 `pytest tests/test_extraction_pipeline.py -v` 确保 `100% Passed`。
   （注：当前全局有 103 个历史 Fail 属于 Task 3.1 范围，严禁你去跑全量测试或尝试修复它们！）
3. **原子提交与推送**：
   所有测试通过后，提交 `git commit -m "feat(core): implement task 007-02 session_id injection to event metadata"`，然后推送到远程。
4. **交接**：
   完成后，请向 User 回复 `[PR_READY]`。

---
**审批状态**: Approved/已确认
