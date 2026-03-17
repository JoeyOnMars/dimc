# Post-Phase 3 Code Audit Report

**状态**: 历史阶段审计；仅反映当时 Phase 3 之后的代码状态，不直接代表当前实现。

## 1. 结论概要 (Executive Summary)

- **整体评估**: **可接受 (Pass with Warnings)**
- **主要发现**:
    - 核心存储逻辑 (`GraphStore`, `EventIndex`) 健壮，Schema 管理和外键约束实现正确。
    - 敏感信息未发现泄漏，API Key 均通过环境变量管理。
    - 存在少量硬编码阈值和路径约束，影响灵活性但不影响功能正确性。
    - 遗留少量 TODOs 需要排期清理。

## 2. 问题清单 (Issues List)

### P0 / 阻断级 (Blocker)
*无*

### P1 / 高优先级 (Critical)
*无*

### P2 / 建议优化 (Warning)

1.  **Hardcoded Semantic Threshold**
    - **位置**: `src/dimcause/reasoning/engine.py:39`
    - **描述**: `threshold=0.85` 硬编码在代码中。
    - **风险**: 难以针对不同模型或数据分布调整敏感度。
    - **建议**: 移至 `ReasoningConfig` 并通过 env var 或配置文件控制。

2.  **Rigid Path Constraints in EventIndex**
    - **位置**: `src/dimcause/core/event_index.py:636`
    - **描述**: 强制检查 `docs/logs` 和 `~/.dimcause/events` 路径。
    - **风险**: 限制了用户自定义数据目录的能力 (e.g. CLI `--data-dir`)。
    - **建议**: 改为从 `Authentication/Config` 注入 Base Path，而非硬编码绝对路径片段。

3.  **CLI Output using `print`**
    - **位置**: `src/dimcause/core/event_index.py:765, 784, 807`
    - **描述**: `migrate_v4` 使用 `print` 而非 `logger` 或 `rich.console`。
    - **风险**: 无法被结构化日志系统捕获，且在非 CLI 环境引用时污染 stdout。
    - **建议**: 注入 `console` 对象或使用 `logging`。

4.  **Legacy TODOs**
    - **位置**: `src/dimcause/core/event_index.py:347` (`TODO: refactor to reuse filter logic`)
    - **描述**: `count` 方法存在代码重复。
    - **风险**: 维护成本增加，逻辑不一致风险。
    - **建议**: 提取通用 `_build_query` 方法。

## 3. 与设计/文档一致性 (Consistency)

- **GraphStore Schema**: 与 `P3_GRAPH_STORE_DESIGN.md` 一致。
- **Migration**: `dimc migrate v4` 实现了设计中的全量迁移逻辑。
- **Embedding Model**: `Environment-Setup.md` 已更新以反映 `DIMCAUSE_EMBEDDING_MODEL` 的支持，代码实现 (`config.py`) 与其一致。

## 4. 商业化视角建议 (Commercial Readiness)

- **Performance**: SQLite WAL 模式已启用，适合单机高并发。未来多租户场景需考虑 PostgreSQL 迁移。
- **Traceability**: `graph_edges` 包含 `metadata` 和 `created_at`，但在 Update 时未记录变更历史 (Audit Trail)。建议未来版本增加 `edge_history` 表。
