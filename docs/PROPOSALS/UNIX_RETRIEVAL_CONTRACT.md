# UNIX Retrieval Contract for DIMCAUSE

> 类型：设计契约 / 实施约束
> 状态：Draft
> 日期：2026-03-07
> 目标：将当前 `SearchEngine` 的 `unix` 通道从“Markdown 事件库 grep”升级为“可执行、可扩展、可审计的 UNIX-native 精确检索层”

---

## 1. 问题定义

DIMCAUSE 当前已经具备四类检索/推理相关能力的雏形：

1. `Vector Local`：`VectorStore.search()`
2. `Graph Global`：`GraphStore` / `get_causal_chain()` / BFS
3. `Text`：基于现有文本召回
4. `UNIX`：`SearchEngine._unix_search()`

但当前 `UNIX` 通道的真实实现非常窄：

1. 仅扫描 `markdown_store.base_dir`
2. 仅扫描 `*.md`
3. 仅返回 `Event`
4. 实质上是“事件库 grep”，不是更底层的 UNIX-native retrieval layer

这和项目讨论中形成的原始设想有明显差距。

原始设想不是“再加一个 grep 小功能”，而是：

**为 DIMCAUSE 提供一条零 embedding 依赖、零语义幻觉、零图谱前提的精确检索底座。**

这条底座应服务于：

1. 精确字符串检索
2. 文件路径 / 符号名 / 错误码 / 配置键的快速命中
3. 为 hybrid search 提供高精度候选召回
4. 为 `trace / why / audit / scheduler` 等上层能力提供 deterministic primitive

---

## 2. 设计目标

### 2.1 Primary Goals

1. 将 UNIX 通道升级为 **多源精确检索层**
2. 明确 `code / docs / events` 三类源的扫描与召回规则
3. 为 hybrid search 提供统一、可融合的候选结果
4. 在 `rg/fd` 缺失时提供可控降级，而不是崩溃
5. 保持项目“本地优先、单机优先、可审计”的风格

### 2.2 Secondary Goals

1. 让 `UNIX` 通道可被 `search/trace/why/audit` 复用
2. 为后续 source-aware reranking 和 candidate fusion 铺路
3. 为将来接入 `fd`, `git grep`, `jq`, `sqlite3` 等 UNIX primitives 预留接口

### 2.3 Non-Goals

1. 不用 shell pipeline 取代核心业务逻辑
2. 不把图谱推理、因果推理、实体语义建模搬进 shell
3. 不在第一阶段引入复杂 daemon / cache server / external indexer
4. 不在第一阶段处理 entity embedding / relation embedding

---

## 3. 核心原则

### 3.1 分层原则

DIMCAUSE 的检索与推理体系应维持三层分工：

1. **UNIX Precision Layer**
   - 负责快速、确定性、低假阳性的候选召回
   - 工具：`rg`, `fd`, `git diff`, `find` 等

2. **Semantic / Graph Layer**
   - 负责语义近邻、图谱遍历、关系补全
   - 工具：`sqlite-vec`, `GraphStore`, reranker

3. **Reasoning Layer**
   - 负责因果解释、叙事整合、审计输出
   - 工具：`dimc why`, `LLMLinker`, 上层组合逻辑

一句话：

**UNIX 通道做“精确召回”，不是做“智能推理”。**

### 3.2 多源原则

UNIX 通道不能只绑定事件库 Markdown。

它必须至少支持三类源：

1. `events`
   - DIMCAUSE 事件 Markdown / 原始事件文件
2. `docs`
   - `docs/`，以及其他被当前 workspace/profile 显式纳入的正式文档目录
3. `code`
   - `src/`, `tests/`, `scripts/`, 必要时含 `.agent/`

### 3.3 可控降级原则

1. `rg` 不存在时，UNIX 通道不能崩溃
2. 单个源扫描失败时，不能拖垮整个 hybrid search
3. 降级必须可见、可记录、可调试

### 3.4 结果统一原则

不同源类型的命中结果，必须先归一成统一结构，再进入 hybrid merge。

否则：

1. `Event`
2. 代码文件命中
3. 文档段落命中

这三类结果会在上层 API 中语义漂移，导致 merge/rerank 变成 ad-hoc 拼接。

---

## 4. 当前实现与目标实现的差距

### 4.1 当前实现

当前 `_unix_search()` 见：
[engine.py](/Users/mini/projects/GithubRepos/dimc/src/dimcause/search/engine.py:238)

现状：

1. 搜索器：`rg --files-with-matches`
2. 搜索范围：`markdown_store.base_dir`
3. 文件过滤：仅 `*.md`
4. 命中结果：加载回 `Event`
5. 融合方式：作为 `hybrid` 的一个 channel，权重 `0.8`

### 4.2 差距清单

1. **搜索范围过窄**
   - 只有事件库，没有代码库、文档库

2. **结果类型过窄**
   - 只能返回 `Event`，不能表达“代码命中”“文档命中”

3. **候选发现能力过弱**
   - 只有 `rg`，没有 `fd`/路径约束/源级过滤

4. **融合语义过弱**
   - 现有 merge 只看 channel 权重，不知道 `code/docs/events` 的 source 语义

5. **缺少上层复用接口**
   - 现在是 `SearchEngine` 内部方法，不是清晰的 UNIX retrieval primitive

6. **缺少配置面**
   - 不能声明哪些目录属于 `code/docs/events` 三类源

---

## 5. 目标架构

目标不是在 `SearchEngine` 里继续堆一坨 if/else，而是形成一个更明确的结构：

```text
User Query
  ↓
SearchEngine
  ├── semantic channel
  ├── graph channel
  ├── text channel
  └── unix channel
         └── UnixRetrievalService
               ├── source resolver
               ├── candidate discovery
               ├── content matching
               └── normalized result builder
  ↓
channel fusion
  ↓
optional reranker
  ↓
SearchResult / Event projection / upper-layer reasoning
```

### 5.1 推荐模块形态

推荐新增：

1. `src/dimcause/search/unix_retrieval.py`
2. 或 `src/dimcause/search/unix_channel.py`

职责：

1. 解析源配置
2. 执行 `fd/rg`
3. 构建统一结果
4. 对外暴露纯 Python 接口

不推荐：

1. 直接在 CLI 里拼 shell
2. 在 `SearchEngine._unix_search()` 里继续膨胀所有逻辑

---

## 6. 源模型（Source Model）

### 6.1 Source Types

第一阶段固定三类：

1. `events`
2. `docs`
3. `code`

未来可扩展：

4. `configs`
5. `exports`
6. `logs_raw`

### 6.2 Recommended Source Roots

第一阶段建议默认如下：

#### `events`

候选根：

1. `MarkdownStore.base_dir`
2. 如果为空，则该源禁用

#### `docs`

候选根：

1. `docs/`
2. 其他通过 source config 显式声明的共享文档目录

说明：

1. `tmp/` 默认不属于正式知识面
2. 第一阶段不把本地讨论目录或临时协调目录写入默认 `docs` roots

#### `code`

候选根：

1. `src/`
2. `tests/`
3. `scripts/`
4. 必要时 `.agent/`

说明：

1. `.agent/` 是否纳入，应做开关控制
2. 默认可以先关闭，避免规则文件噪音过大

### 6.3 Source Priority

默认优先级建议：

1. `events`
2. `code`
3. `docs`

原因：

1. `events` 更接近因果记忆主账本
2. `code` 更接近可执行现实
3. `docs` 更接近设计与说明层

---

## 7. 检索策略

## 7.1 Candidate Discovery

候选发现分两步：

1. **源筛选**
   - 先决定查哪些 source
2. **文件筛选**
   - 再用 `fd` 或内置规则缩小候选文件集

### 第一阶段最小策略

可先不强依赖 `fd`，按源固定 include pattern：

#### `events`
- `*.md`

#### `docs`
- `*.md`
- `*.yaml`
- `*.yml`

#### `code`
- `*.py`
- `*.md`
- `*.sh`
- `*.zsh`
- `*.yaml`
- `*.yml`
- `*.toml`

### 第二阶段增强

接入 `fd`：

1. 用 `fd` 做文件发现
2. 用 `rg` 做内容命中

原因：

1. `fd` 做路径过滤和 ignore 处理更自然
2. `rg` 做内容命中更快
3. 两者组合比纯 Python `rglob()` 更符合 UNIX-native 检索层的目标

## 7.2 Content Matching

默认使用：

```bash
rg --files-with-matches --ignore-case --max-count 1 <query> <roots...>
```

必要增强：

1. query 为空时直接返回空
2. 支持 exact/regex/fuzzy 模式扩展
3. 对于明显像路径/符号名的 query，优先 exact-like 行为

### Query Heuristics

第一阶段建议做轻量启发式：

1. **路径型查询**
   - 包含 `/`, `.py`, `.md`, `src/`, `tests/`
   - 处理：降低 ignore-case，偏向精确匹配

2. **符号型查询**
   - 类似 `SearchEngine`, `add_batch`, `IllegalRelationError`
   - 处理：优先查 `code`

3. **错误码/配置键型查询**
   - 类似 `E501`, `DIMCAUSE_SKIP_WATCHER`
   - 处理：优先 `code + docs`

4. **自然语言型查询**
   - 类似“为什么重构登录模块”
   - 处理：UNIX 通道作为辅助，不承担主召回

---

## 8. 统一结果结构（Normalized Result Schema）

UNIX 通道不能直接返回混乱的 `Path` / `Event` / 文本片段组合。

建议新增统一结构：

```python
@dataclass
class RetrievalHit:
    source: Literal["events", "docs", "code"]
    path: str
    kind: Literal["event", "document", "code"]
    title: str | None
    snippet: str | None
    line_no: int | None
    score: float
    raw_id: str | None
```

### 字段说明

1. `source`
   - 三类源之一

2. `path`
   - 命中文件路径

3. `kind`
   - 命中对象的逻辑类型

4. `title`
   - 文档标题 / 事件标题 / 符号名（若能得到）

5. `snippet`
   - 用于上层展示和 rerank

6. `line_no`
   - 若通过 `rg -n` 获取，保留首命中行

7. `score`
   - UNIX channel 内部初始分

8. `raw_id`
   - 对于 `events` 可映射回 event id；其他源可为空

### 为什么需要统一结果结构

因为第一阶段虽然仍可在最终 `search()` 返回 `Event`，但中间层如果没有统一结果结构：

1. source-aware merge 无法做
2. 将来接 code/doc results 会引发接口崩坏
3. reranker 无法统一处理 snippet/title/path 信号

---

## 9. 与现有 `SearchEngine` 的集成策略

### 9.1 第一阶段

目标：

1. 保持 `search()` 现有返回类型尽量不炸
2. 先把 UNIX 通道从“仅 events grep”升级到“多源命中 + events 优先投影”

建议：

1. UNIX channel 先产出 `RetrievalHit`
2. 如果 `source == events` 且可映射成 `Event`，继续回投成 `Event`
3. `code/docs` 命中先只作为 hybrid 辅助候选，不强行暴露给最终 public API

这是一个过渡态，但最稳。

### 9.2 第二阶段

升级 `SearchEngine` 的内部 merge：

1. 接受 `Event` + `RetrievalHit` 混合候选
2. source-aware 去重
3. source-aware 权重分配

### 9.3 第三阶段

统一 public search result schema，让 CLI / MCP / `why` 决定如何渲染：

1. 事件命中
2. 文档命中
3. 代码命中

这时 `dimc search` 才真正变成“GraphRAG 超集检索器”，而不是“事件搜索器 + 若干旁路”。

---

## 10. Hybrid 融合策略

### 10.1 当前策略

当前实现大致是：

1. `semantic` 权重 `1.0`
2. `graph` 权重 `0.9`
3. `unix` 权重 `0.8`
4. `text` 权重 `0.7`

问题：

1. `unix` 被当成单一通道，没有 source 区分
2. 对“精确命中”价值估计偏低

### 10.2 推荐策略

UNIX 通道内部再分 source：

1. `unix_events`
2. `unix_code`
3. `unix_docs`

推荐第一版权重：

1. `semantic`: `1.0`
2. `graph`: `0.9`
3. `unix_events`: `0.9`
4. `unix_code`: `0.85`
5. `unix_docs`: `0.8`
6. `text`: `0.7`

### 10.3 Exactness Bonus

对于以下情况，UNIX 结果应有额外 bonus：

1. query 精确等于文件名
2. query 精确等于符号名
3. query 精确命中错误码 / 配置键

这样才能体现 UNIX 通道的真正价值：

**不是“又一个弱通道”，而是“精确检索强通道”。**

---

## 11. CLI / API 影响

### 11.1 `dimc search`

第一阶段不必改 CLI 语义，只需保证：

1. `--mode unix` 变得更强
2. `--mode hybrid` 能利用更真实的 UNIX 通道

第二阶段可考虑增加：

1. `--unix-source events,code,docs`
2. `--exact`
3. `--show-source`

### 11.2 `dimc trace`

`trace` 当前历史上长期存在“偷懒用 git grep 替代真实结构化能力”的争议。

UNIX retrieval layer 成熟后，可以成为 `trace` 的底层精确召回器之一：

1. 代码路径 / 符号路径查找
2. 文档中设计说明查找
3. 事件日志中同名符号出现查找

### 11.3 `dimc why`

`why` 不应直接依赖 UNIX 通道做结论，但可以依赖它做：

1. 精确证据召回
2. 边缘证据补充
3. 解释链引用定位

---

## 12. 配置面

建议未来增加配置项：

```toml
[search.unix]
enabled = true
use_fd = false
include_agent_rules = false

[search.unix.sources.events]
enabled = true

[search.unix.sources.docs]
enabled = true
paths = ["docs"]

[search.unix.sources.code]
enabled = true
paths = ["src", "tests", "scripts"]
```

第一阶段可以不落配置文件，只在代码里写默认值。

---

## 13. 安全与性能约束

### 13.1 性能约束

UNIX 通道必须比纯 Python 递归扫描更快，至少不能更差。

第一阶段要求：

1. 不使用无界 `Path.rglob()` 深扫整个仓库
2. 不在 query 为空时启动 shell
3. 不对每个候选文件做全量内容回读
4. 命中后只取有限文件、有限片段

### 13.2 安全约束

1. shell 命令必须使用参数数组，不做字符串拼接
2. query 不经 shell 展开
3. 结果路径必须在允许源根目录内
4. 失败时返回空结果或诊断，不传播 shell 注入风险

---

## 14. 测试策略

### 14.1 单元测试

至少覆盖：

1. `rg` 不存在
2. 某个 source root 不存在
3. `events/docs/code` 三类源匹配
4. query 为空
5. exactness bonus
6. source-aware merge

### 14.2 集成测试

至少覆盖：

1. `mode="unix"` 在三类源上的行为
2. `mode="hybrid"` 是否能把 UNIX 候选并入融合
3. `rg` 返回码 `0/1/非0非1` 三种情况

### 14.3 回归测试

必须防止：

1. UNIX 通道重新退化回只扫 `*.md`
2. hybrid 通道忘记接 UNIX source
3. `check.zsh` 中因为 `rg/fd` 缺失引发误失败

---

## 15. 分阶段实施顺序

### Phase 1: Contract-Aligned Refactor

目标：

1. 抽出 `unix_retrieval` 模块
2. 支持 `events/docs/code` 三类源
3. 保持 `SearchEngine` 对外尽量兼容

输出：

1. 新模块
2. 单测
3. `SearchEngine` 接线

### Phase 2: Source-Aware Fusion

目标：

1. 对 `unix_events/unix_code/unix_docs` 分权重
2. 引入 snippet / line number / exactness bonus

### Phase 3: Unified Retrieval Result

目标：

1. 对外提供统一 search result schema
2. CLI/MCP/why 再各自决定展示层

---

## 16. 明确不做的错误方向

1. **不把 shell pipeline 直接塞进 CLI 命令实现里**
2. **不让 UNIX 通道越权承担因果解释**
3. **不在第一阶段同时做 entity semantic embedding**
4. **不把 `tmp/` 全量纳入 docs source**
5. **不把 `.agent/` 默认纳入 code source**

---

## 17. 执行建议

如果下一步开始写代码，建议任务顺序固定为：

1. 新建 `search/unix_retrieval.py`
2. 先实现 source model + `rg` 搜索 + normalized result
3. 再改 `SearchEngine._unix_search()`
4. 再补 source-aware tests
5. 最后才考虑 CLI 展示增强

不要反过来先改 CLI 或直接改 `SearchEngine` 大函数。

---

## 18. 结论

DIMCAUSE 的 UNIX 通道不应该只是“给 hybrid search 加一个 grep 命中”。

它应该被重新定义为：

**DIMCAUSE 的精确检索底层（UNIX-native precision retrieval layer）。**

它的职责不是替代向量、图谱、LLM，而是给这些上层能力提供：

1. 更强的精确召回
2. 更低的假阳性
3. 更好的本地性能
4. 更可靠的审计证据定位

若按这个契约推进，UNIX 通道将不再是临时补丁，而会成为 DIMCAUSE 检索栈里一个长期稳定的基础层。
