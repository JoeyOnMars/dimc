# V6.3 Local-First 提取引擎重构方案

## Context

根据 P博士 评审 + G博士 反馈，统一方案已确定：

### 核心理念
- Local-First ≠ Local-Only
- 三层架构：L0(raw) → L1(embedded) → L2(extracted)
- L1 不可跳过（必须先 embedding 用于检索）

### 统一后的关键点
1. L1 必须执行（embedding 用于检索）
2. L2 是可选增强
3. 状态：status + confidence + needs_extraction
4. 落地：先 L0+L1，再 L2

---

## 三个核心模块

### 1. EventLogWatcher
- 监听 Claude Code JSONL、AG Exports 增量
- L0 原始落盘，赋予 source_event_id

### 2. ChunkingManager
- 双层切片：Session（时间）+ Smart Chunk（800-1000 Token）
- L1 执行：embedding + 规则提取

### 3. ExtractionWorker
- 扫描 `status=embedded AND needs_extraction=true`
- 异步调用云端 LLM
- 幂等更新为 extracted/high

---

## 文件变更

| 操作 | 文件 |
|------|------|
| 新增 | `src/dimcause/extractors/event_watcher.py` |
| 新增 | `src/dimcause/extractors/chunking_manager.py` |
| 新增 | `src/dimcause/extractors/extraction_worker.py` |
| 修改 | `src/dimcause/core/session_end.py` |
| 修改 | `src/dimcause/core/data_collector.py` |

---

## 验证

```bash
# 单元测试
pytest tests/test_event_watcher.py
pytest tests/test_chunking_manager.py
pytest tests/test_extraction_worker.py

# 集成测试
dimc up
dimc down --check-extraction

# 降级测试
unset DEEPSEEK_API_KEY
dimc down
```
