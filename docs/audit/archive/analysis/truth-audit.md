# 🏥 Dimcause 深度真实性审计报告 (Deep Truth Audit)

**状态**: 历史快照；其中部分结论已与当前 live 代码不一致；不得直接作为当前事实依据。

**日期**: 2026-02-16
**审计模式**: Brutal / Strict
**审计对象**: `src/dimcause` vs `docs/`

本报告旨在**揭示 Dimcause 项目中 "Superset" 愿景与当前代码实现之间的真实差距**。拒绝营销辞令，只谈工程事实。

## 1. 核心架构审计 (Ontology & Graph)

| 组件 | 宣传口径 (Marketing) | 代码现状 (Reality) | 真实性评级 | 详细技术分析 |
| :--- | :--- | :--- | :--- | :--- |
| **5-Layer Ontology** | "Wal + 5-Layer Ontology" 严谨分层 | **Disconnected Engine**<br>`src/dimcause/core/ontology.py` | ⚠️ **未集成** | Ontology 引擎本身实现了基于 YAML 的验证 (`validate_relation`)，**但是**！全库搜索显示该方法**除了测试外从未被调用**。这意味着数据写入时没有任何本体约束检查，所谓的"严谨分层"纯属空谈。 |
| **Causal Graph** | "因果图谱 / Causal Memory" | **NetworkX + SQLite KV**<br>`src/dimcause/storage/graph_store.py` | 🔴 **原型级** | 实现仅仅是 `NetworkX` 的简单封装。所谓的 "Causal" (因果) 目前仅体现为 `caused_by` 这一种边类型，**没有任何因果推理算法** (如反事实推理、根因分析)。`find_related` (line 226) 只是简单的 BFS (广度优先搜索)。 |
| **Vector Store** | "语义搜索 / 向量数据库" | **ChromaDB Wrapper**<br>`src/dimcause/storage/vector_store.py` | ✅ **可用** | 基于 `chromadb` 和 `sentence-transformers`。代码实现了 `add` 和 `query`。基础功能扎实。 |

## 2. 搜索与智能审计 (Search & AI)

| 组件 | 宣传口径 | 代码现状 | 真实性评级 | 详细技术分析 |
| :--- | :--- | :--- | :--- | :--- |
| **Hybrid Search** | "文本+语义+图谱 混合检索" | **Text + Vector**<br>`src/dimcause/search/engine.py` | 🔶 **部分实现** | 实现了文本和向量的混合检索，但**完全缺失图谱搜索 (Graph Search)**。CLI 的 `trace` 命令也只是简单的语义搜索封装，并没有利用图谱结构进行路径查找。 |
| **LLM Integration** | "多模型智能底座" | **Robust Client**<br>`src/dimcause/extractors/llm_client.py` | 🌟 **优秀** | 这是系统中**最诚实健壮**的部分。完整实现了 Ollama/OpenAI/Anthropic/DeepSeek 的适配，包含错误回退 (Fallback) 和成本追踪。完全符合文档描述。 |
| **Timeline** | "智能时间线分析" | **Simple Stats**<br>`src/dimcause/core/timeline.py` | ⚠️ **初级** | `TimelineService` 仅提供基础的时间聚合（按小时/类型统计）和简单的“空档期检测”（>4小时）。不存在任何“事件关联分析”或“工作模式识别”。 |

## 3. 功能模块审计 (Importers)

| 组件 | 宣传口径 | 代码现状 | 真实性评级 | 详细技术分析 |
| :--- | :--- | :--- | :--- | :--- |
| **Data Import** | "Superset / 全量导入" | **脆弱的脚本**<br>`src/dimcause/importers/dir_importer.py` | ⚠️ **高风险** | 虽然支持 PDF/Docx，但**完全依赖可选包**且缺乏错误提示优化。如果用户未安装 `dimcause[full]`，导入器会静默跳过文件，体验极差。 |
| **Git Import** | "时光机 / 历史回溯" | **性能黑洞**<br>`src/dimcause/importers/git_importer.py` | 🔴 **不可用** | 1. **OOM 风险**: 尝试一次性加载所有 Commits 到内存。<br>2. **IO 瓶颈**: 循环内逐个写入 VectorStore。<br>3. **Token浪费**: `diff` 截断逻辑粗糙，简单截取前2000字符。 |

## 4. 致命代码异味 (Code Smells)

1.  **Dead Code (死代码)**: `Ontology.validate_relation` 是一个典型的"幽灵功能"——写了但没用。它给了开发者一种"系统很严谨"的错觉，但实际上从未生效。
2.  **Import 地狱**: `importers/dir_importer.py` 充斥着 `try...except ImportError` 的局部引用，难以维护。
3.  **缺乏事务**: `GraphStore` 的 `add_event_relations` 在写入 SQLite 时虽然有 commit，但 NetworkX 内存更新和 SQLite 更新缺乏强一致性保障。

## 5. 结论与行动建议

**Dimcause 目前是一个 "High Potential, Low Integration" 的系统。**
组件（LLM, Ontology Engine, VectorStore）都写得不错，但**核心逻辑链条断裂**（Ontology 未被调用，Graph 未被搜索使用）。

**立即整改计划 (P0)**:
1.  **激活 Ontology**: 在 `Event` 构造或 `GraphStore.add_edge` 时强制调用 `validate_relation`。
2.  **重构 Git Importer**: 改为 Generator 模式流式处理 Commit，并实现 `batch_add`。
3.  **实现 Graph Search**: 在 `SearchEngine` 中真正加入图谱跳跃逻辑，否则不要宣传 "Graph RAG"。


## 6. Phase 3 深度审计 (Deep Dive)

| 组件 | 宣传口径 | 代码现状 | 真实性评级 | 详细技术分析 |
| :--- | :--- | :--- | :--- | :--- |
| **AST Analysis** | "代码级深度感知 / Code Intelligence" | **Tree-sitter + Regex**<br>`src/dimcause/extractors/ast_analyzer.py` | ✅ **合格** | 实现了基于 `tree-sitter` 的解析，支持 Python/JS/TS 的函数、类、导入提取。虽然缺乏深度流分析 (Control Flow)，但作为提取器是合格的。 |
| **Audit Command** | "Causal Audit / 因果审计" | **Linter Wrapper**<br>`src/dimcause/audit/runner.py` | 🔴 **误导** | `dimc audit` 命令**完全未调用**因果验证器 (`AxiomValidator`)。它只是运行了 Ruff, Mypy, Bandit 等常规工具。**真正的因果审计被隐藏在 `dimc graph check` 子命令中**。 |
| **MCP Server** | "Protocol Interface" | **Full Exposure**<br>`src/dimcause/protocols/mcp_server.py` | 🌟 **优秀** | MCP Server 正确暴露了核心能力，包括 `get_causal_chain` (调用 GraphStore) 和 `audit_check` (调用 AxiomValidator)。它是目前系统中访问 "高级功能" 的最佳入口。 |

## 7. 最终结论 (Final Verdict)

Dimcause 系统呈现出明显的 **"人格分裂" (Split Personality)** 特征：

1.  **扎实的基础层**: LLM Client, MCP Protocol, Vector Store 基础实现都很扎实，达到了生产级原型标准。
2.  **空洞的智能层**: "Causal Graph", "Hybrid Search", "Timeline Analysis" 等高级概念在代码中大多未真正集成，或者逻辑非常浅薄（BFS 代替因果推理）。
3.  **误导的接口层**: `dimc audit` 不跑审计，`Ontology` 不校验数据。

**核心问题**: 系统拥有所有必要的组件（AST解析器、图数据库、验证引擎），但**它们没有被连接起来**。

**修正建议**:
-   **Connect the dots**: 将现有组件串联。让 `audit` 调用 `graph check`，让 `add_event` 调用 `ontology.validate`。
-   **Be Honest**: 修改文档，明确区分 "Implemented Features" (已实现) 和 "Roadmap Features" (画饼)。
