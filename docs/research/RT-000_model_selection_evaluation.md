# 本地 AI 模型选型评估报告 (Model Selection Evaluation)

**版本**: V2.0 (基于 V1.0 + 2026-02-12 内存约束讨论更新)  
**评估日期**: 2026-02-12  
**评估目标**: 确定 DIMCAUSE 中 Embedding + Reranker 的最佳模型组合  
**硬件约束**: M4 Mac Mini, **16GB 内存**（实际可用 ~3-6GB）  
**语言约束**: 中英文双语（中文日志 + 英文代码/commit）

---

## 1. 当前状态 ⚠️

| 组件 | 当前使用 | 问题 |
|:---|:---|:---|
| **Embedding** | `BAAI/bge-small-en-v1.5` (384 维, 33MB) | ❌ **仅英文**，中文日志无法正确嵌入 |
| **Reranker** | 无 | ❌ 搜索结果无精排，大量噪音塞给 LLM |
| **Query Expansion** | 无 | 暂无需求 |

> [!WARNING]
> `bge-small-en-v1.5` 是早期临时选择，**不支持中文**。你的日志（daily-end, decision, 讨论记录）全是中文，用这个模型嵌入后搜索质量极差——这就是为什么你之前说搜索效果和 grep 差不多。

---

## 2. Embedding 模型全量对比

数据源：[MTEB](https://huggingface.co/spaces/mteb/leaderboard) + [C-MTEB](https://github.com/FlagOpen/FlagEmbedding/tree/master/C_MTEB) 榜单（截至 2026-02）

> 下表中各项数据为近似值（前缀 `~`），基于 MTEB/C-MTEB 2025 早期数据和 HuggingFace 模型卡信息。
> 运行时内存为估算值（基于参数量 × 2字节/参数 + 推理开销），未实测。

### 2.1 候选模型天梯图

| 模型 | 厂商 | 参数量 | 维度 | 模型大小 | 上下文窗口 | 中文检索 NDCG@10 | 英文检索 | 运行时内存 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **GTE-Qwen2-1.5B** | Alibaba | 1.5B | 1536 | ~3.0 GB | 32k | ~71.0 (**SOTA**) | ~69.5 | ~4.5 GB |
| **Stella-mteb-zh-v3** | Stella | 1.5B | 1024 | ~3.3 GB | 8k | ~71.2 | ~67.0 | ~5.0 GB |
| **acge_text_embedding** | TextIn | 330M | 1024 | ~0.6 GB | **1024** | ~70.5 | ~65.0 | ~1.0 GB |
| **Jina-embeddings-v3** | Jina AI | 570M | 1024 | ~1.1 GB | 8k | ~69.5 | ~70.0 | ~1.8 GB |
| **BGE-M3** | BAAI | 567M | 1024 | ~1.1 GB | 8k | ~67.5 | ~68.0 | ~1.8 GB |
| **BGE-large-zh-v1.5** | BAAI | 330M | 1024 | ~0.6 GB | 512 | ~66.0 | ~60.0 | ~1.0 GB |
| **paraphrase-multilingual-MiniLM-L12-v2** | SBERT | 118M | 384 | ~471 MB | 512 | ~58.0 | ~65.0 | ~0.8 GB |
| ~~bge-small-en-v1.5 (当前)~~ | BAAI | 33M | 384 | 33 MB | 512 | ❌ 不支持 | ~62.0 | ~0.2 GB |

### 2.2 淘汰原因

| 模型 | 淘汰原因 |
|:---|:---|
| **GTE-Qwen2-1.5B** | 运行时 ~4.5GB，16GB 机器上会导致严重 swap |
| **Stella-mteb-zh-v3** | 同上，且社区生态弱 |
| **acge_text_embedding** | 上下文窗口仅 1024，无法处理长日志；许可证不明确 |
| **BGE-large-zh-v1.5** | 上下文窗口仅 512，英文支持弱 |
| **bge-small-en-v1.5** | ❌ 不支持中文，已确认不合格 |

### 2.3 入选最终评估的 Embedding

| 模型 | 优势 | 劣势 | 适用模式 |
|:---|:---|:---|:---|
| **Jina v3** | 多语言、Matryoshka 可变维度、8k 窗口 | 需要 `trust_remote_code=True` | 模式 A |
| **BGE-M3** | 工业标杆、稠密+稀疏多向量、无安全风险 | 中文精度略低于 Jina/GTE | 模式 B |
| **GTE-Qwen2** | SOTA 精度、32k 窗口 | 内存 ~4.5GB，需"用完释放" | 模式 C |
| **paraphrase-multilingual-MiniLM** | 极轻量 471MB、多语言 | 精度最低、窗口仅 512 | 备选轻量 |

---

## 3. Reranker 模型全量对比

### 3.1 候选模型

| 模型 | 厂商 | 大小 | 上下文窗口 | 中文支持 | 运行时内存 | 安全风险 |
|:---|:---|:---|:---|:---|:---|:---|
| **bge-reranker-v2-m3** | BAAI | ~2.2 GB | **8k** | ✅ 优秀 | ~3.0 GB | ✅ 无 |
| **jina-reranker-v2-base-multilingual** | Jina AI | ~1.1 GB | **1024** | ✅ 良好 | ~1.5 GB | ⚠️ RemoteCode |
| **bce-reranker-base-v1** | NetEase | ~1.3 GB | 512 | ✅ 优秀 | ~2.0 GB | ✅ 无 |
| **gte-multilingual-reranker-base** | Alibaba | ~1.5 GB | 8k | ✅ 良好 | ~2.2 GB | ✅ 无 |

### 3.2 淘汰原因

| 模型 | 淘汰原因 |
|:---|:---|
| **jina-reranker-v2-base** | 窗口仅 1024，无法处理长日志 Rerank |
| **bce-reranker-base-v1** | 窗口仅 512，且已停止更新 |

### 3.3 入选最终评估的 Reranker

| 模型 | 优势 | 劣势 | 建议 |
|:---|:---|:---|:---|
| **bge-reranker-v2-m3** | 8k 窗口、中文优秀、无安全风险 | 内存 ~3GB | ✅ **统一选择** |
| **gte-multilingual-reranker-base** | 8k 窗口、Apache 2.0 | 内存 ~2.2GB | ✅ 备选 |

**结论**：所有三种模式统一使用 **`bge-reranker-v2-m3`** 作为 Reranker。理由：8k 窗口覆盖所有日志长度，中文精度高，BAAI 生态稳定。

---

## 4. 三模式架构（Tri-Mode Architecture）

### 4.1 模式定义

| 模式 | Embedding | Reranker | 峰值内存 | 适用场景 |
|:---|:---|:---|:---|:---|
| **A: Performance** | Jina v3 (1.1GB) | bge-reranker-v2-m3 (2.2GB) | ~3.0 GB | 个人开发、多语言 |
| **B: Trust** | BGE-M3 (1.1GB) | bge-reranker-v2-m3 (2.2GB) | ~3.0 GB | 信创/安全、政企 |
| **C: Geek** | GTE-Qwen2-1.5B (3.0GB) | bge-reranker-v2-m3 (2.2GB) | ~4.5 GB | 高端工作站、极致精度 |

> 峰值内存 = max(Embedding 运行时, Reranker 运行时)，因为两者不同时运行：
> - **Embedding 建索引**：事件写入后 / `daily-end` 后台空闲时
> - **Reranker 精排**：用户查询时
> - 两个操作不在同一时间段

### 4.2 运行时序：Embedding 和 Reranker 不同时运行

> [!IMPORTANT]
> Embedding 建索引和 Reranker 精排**分属不同的时间段**，不会同时占用内存。
> 16GB 机器上三种模式都可以轻松运行。

```
[后台 / 空闲时]  Embedding 建索引：对新事件编码 → 存入向量表
                 加载 Embedding 模型 (~1.8-4.5 GB) → 完成后释放

[用户查询时]     Step 1: 加载 Embedding → 只编码 1 条查询 (瞬间) → 释放
                 Step 2: 向量搜索 → 50 个候选 (从已有向量表读取，不需要模型)
                 Step 3: 加载 Reranker (~3 GB) → 精排出 3 个 → 释放
```

**内存占用时间线**：

| 阶段 | 操作 | 内存占用 | 持续时间 |
|:---|:---|:---|:---|
| 建索引（后台） | Embedding 编码所有新事件 | ~1.8-4.5 GB | 数秒-数分钟 |
| 查询 Step 1 | Embedding 编码 1 条查询 | ~1.8 GB | <1 秒 |
| 查询 Step 2 | 向量相似度搜索 | ~0 GB（读 SQLite） | <0.1 秒 |
| 查询 Step 3 | Reranker 精排 50 个候选 | ~3.0 GB | ~1 秒 |

### 4.3 默认模式说明

- **代码默认**: Performance 模式（通用默认，见 `models.py` 中 `DEFAULT_MODEL_STACK`）
- **16GB 机器推荐**: Trust 模式（通过 `DIMCAUSE_MODEL_STACK=trust` 环境变量切换）
  - BGE-M3 全栈，峰值仅 ~3 GB
  - 无安全风险（不需要 `trust_remote_code`）
  - 中文精度优秀，生态稳定

---

## 5. Token 成本贡献分析

本地搜索质量直接决定送给 LLM 的上下文量——**控制 60%-80% 的 token 成本**。

| 搜索质量 | 返回事件 | 有用事件 | context tokens | 浪费率 |
|:---|:---|:---|:---|:---|
| 无 Reranker (当前) | 10 个 | ~2 个 | ~5,000 | **80%** |
| 有 Reranker (精排 Top-3) | 3 个 | ~2 个 | ~1,500 | **33%** |
| **节省** | | | **~3,500 tokens/次** | **~70%** |

按 `dimc why` 每天调用 10 次**粗略估算**：
- 无 Reranker: ~50,000 tokens/天
- 有 Reranker: ~15,000 tokens/天
- **每天省 35,000 tokens，月省 ~100 万 tokens**

> [!NOTE]
> 以上为粗略估算，实际数据需上线后追踪。假设基于：每个事件 ~500 tokens、每天 10 次查询。

---

## 6. 安全评估

| 模型 | 许可证 | `trust_remote_code` | 风险等级 |
|:---|:---|:---|:---|
| Jina v3 | Apache 2.0 | ⚠️ **需要** | 中（模式 A 可用，Trust 模式不可用） |
| BGE-M3 | MIT | ✅ 不需要 | 低 |
| GTE-Qwen2 | Apache 2.0 | ✅ 不需要 | 低 |
| bge-reranker-v2-m3 | MIT | ✅ 不需要 | 低 |

---

## 7. 多模态扩展（Future）

选定的三款模型均为纯文本 (Text-Only)。若后续需要图文检索：

| 文本模型 | 视觉搭档 | 备注 |
|:---|:---|:---|
| Jina v3 | `jina-clip-v2` | 零样本图文检索 |
| BGE-M3 | `Visualized-BGE` | 与 M3 向量空间对齐 |
| GTE-Qwen2 | `gme-Qwen2-VL` | 高密度多模态检索 |

---

## 8. 落选方案 FAQ

### Q1: 为什么不选 acge_text_embedding?
C-MTEB 霸榜、体积仅 330MB，但：
- 上下文窗口仅 **1024**，DIMCAUSE 的 daily-end 日志常超 2k token，会被截断
- 许可证不明确，合规风险

### Q2: paraphrase-multilingual-MiniLM 够用吗?
精度显著低于 BGE-M3（58 vs 67.5 NDCG@10），窗口仅 512。作为紧急轻量备选可以，但不推荐作为主力。

### Q3: 为什么 Reranker 不用 Jina?
`jina-reranker-v2` 窗口仅 1024，无法处理长日志 Rerank。bge-reranker-v2-m3 窗口 8k，覆盖所有场景。

---

## 9. 代码对接

### 模型配置入口

```python
from dimcause.core.models import ModelStack, ModelConfig, get_model_config

# 获取配置
config = get_model_config(stack=ModelStack.TRUST)  # 推荐 16GB 用户

# 或通过环境变量
# DIMCAUSE_MODEL_STACK=trust
```

### 模式映射表

| `ModelStack` | Embedding | Reranker | 默认维度 |
|:---|:---|:---|:---|
| `PERFORMANCE` | `jinaai/jina-embeddings-v3` | `BAAI/bge-reranker-v2-m3` | 1024 |
| `TRUST` | `BAAI/bge-m3` | `BAAI/bge-reranker-v2-m3` | 1024 |
| `GEEK` | `Alibaba-NLP/gte-Qwen2-1.5B-instruct` | `BAAI/bge-reranker-v2-m3` | 1536 |

### 行动项

- [ ] 实现 `ModelFactory`，支持三种后端按需加载
- [ ] 将当前默认模型从 `bge-small-en-v1.5` 切换为 `BGE-M3`
- [ ] 在 `dimc setup` 中增加模式选择交互
- [ ] 向量维度变更时的 Schema 迁移（384 → 1024）
- [ ] **全量代码与文档交叉审计**：对项目全部代码和文档做一次完整一致性审计

---

**最后更新**: 2026-02-12 21:52  
**变更记录**: V2.0 — 新增 16GB 内存约束分析、用完即释放策略、Token 成本贡献分析、修正当前状态警告
