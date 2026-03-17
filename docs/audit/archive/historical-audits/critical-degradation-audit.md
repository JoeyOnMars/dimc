# 🔴 核心能力灾难性降级审计报告 (CRITICAL DEGRADATION AUDIT - 专家订正版)

**状态**: 历史审计快照；文风保留原样；仅供追溯当时问题与修复背景，不作当前正式审计依据。

**审计标准**：极度苛刻（Zero Tolerance for Silent Downgrades & Fake Data）
**审计目标**：深挖 DIMCAUSE 代码库中所有“以 catch 异常为名，行数据造假、逻辑阉割之实”的糊弄代码。

---

## 核心发指罪行汇总 (The "Fake It" Anti-Patterns)

### 🔴 罪行一：数据绝对造假（VectorStore 语义向量盲猜）
- **严重程度**：致命（Critical）
- **发源文件**：`src/dimcause/storage/vector_store.py:381`, `385` (`embed_chunks`)
- **作案手法**：在调用 `sentence_transformers` 生成文档特征向量时，竟然使用了**双重异常吞噬**：
  ```python
  except ImportError:   # line 378
      return [np.random.rand(dim).astype(np.float32) for _ in texts]
  except Exception as e:  # line 382
      print(f"Warning: embed_chunks failed: {e}")
      return [np.random.rand(dim).astype(np.float32) for _ in texts]
  ```
- **核心悖论**：`sentence-transformers` 早已被列入 `pyproject.toml` 主依赖中，根本不存在通常意义上的“未安装”场景。第二个 `except Exception` 极其恶劣地吞噬了所有极其严重的运行时错误（如：显存溢出 OOM、模型文件损坏、进程中断），并全盘使用 `np.random.rand(dim)` 塞入数据库！这使得后续的所有检索拿到的全是掷骰子的结果，彻底污染核心数据字典。

### 🔴 罪行二：核心大脑切除（Hybrid Inference 变成时钟流水线）
- **严重程度**：严重（High）- 系统能力退化
- **发源文件**：`src/dimcause/reasoning/engine.py:38` (`HybridInferenceEngine`)
- **作案手法**：作为标榜核心技术壁垒的“多级混合推理引擎”，当大模型库 `litellm` 不存在时。系统仅仅打出一行 `logger.debug("LLMLinker 不可用 (缺少依赖)")`。随后在 `infer()` 主流程中直接跳过大模型因果推理阶段。
- **恶劣影响**：深度决策重演（Deep Decision Replay）形同虚设。最终画出来的网络关联图，不过是按发生时间相近硬凑出来的线（Time-Window Heuristics），因果关系完全丧失。（注：此项在代码层面上属于“正常抛出异常并降级”，并未如 VectorStore 那样造假，但它客观上导致了整个宣发架构的坍塌。）

### 🔴 罪行三：提取引擎掩耳盗铃（AST 解析正则退化）
- **严重程度**：严重（High） 
- **发源文件**：`src/dimcause/extractors/ast_analyzer.py:45`
- **作案手法**：当高精度的 `tree-sitter` 语法树包缺失时，降级使用 `_extract_functions_regex`，控制台仅输出 `print("Warning...")` 糊弄了事。
- **恶劣影响**：用极简正则去提取代码等于盲人摸象。这种降级方案根本无法处理跨行传参和复杂嵌套，提取出的残次 `CodeEntity` 却被当成标准件继续在系统中流转。

### 🔴 罪行四：高性能索引拒载（SQLite-vec 库静默罢工）
- **严重程度**：中等（Medium）- 性能谎言
- **发源文件**：`src/dimcause/storage/vector_store.py:527`
- **作案手法**：直接写死了 `raise ImportError("sqlite-vec disabled due to reliability issues")`。
- **恶劣影响**：假装自己具备向量索引搜索能力，实际上每搜一次都在进行暴力的 `O(N)` 全维矩阵强乘运算。如果不修复，一旦数据量膨胀，系统将瞬间被算力瓶颈卡死。

---

## 🟢 合理降级与正确示范 (The "Good" Patterns)

为了与上述“恶意造假”形成对比，必须澄清以下两点：

### 1. 架构允许的合理降级 (Graceful Degradation)：LLM 缺失跳过
- **案例**：`src/dimcause/reasoning/engine.py:38-39` 
- **定性**：`litellm` 本身就被定义为**可选依赖**。在这里，当环境缺乏大模型推演能力时，系统输出 `logger.debug("LLMLinker 不可用")` 并静默跳过大模型步骤，**这是符合设计的合法降级**。它并没有通过生成“假结果”来欺骗调用方，而是让系统在基础的时间启发式规则下继续运转。这与 `VectorStore` 中硬塞随机数的性质截然不同。

### 2. 正确的异常阻截示范：`model_manager.py`
- **案例**：位于 `reasoning/model_manager.py`
- **定性**：该模块在处理异常时，明确选择了抛出 `raise RuntimeError` 让调用方感知到核心推演能力已经崩塌，**绝不返回任何拼凑或随机生成的假数据**。这就是整个工程在错误处理时应当遵循的唯一底线标准。

---

## 🛠️ 彻底拯救的强制重构建议 (Code-Level Action Plan)

1. **根除 VectorStore 的数据污染**：
   - 立即删除 `vector_store.py` 中所有的 `np.random.rand` 假数据生成代码。
   - 严格区分 `ImportError`（提示依赖未安装，抛出明确指引）和 `RuntimeError`（如OOM或模型损坏，必须抛出 `RuntimeError("Embedding generation failed")` 以熔断脏数据写入流程）。
2. **正视性能瓶颈**：
   - 移除 `sqlite-vec` 人为设置的假路障，修复其返回空结果的真实 bug，或者在代码与文档中用强力警告标明当前的性能极限红线（O(N) 暴力扫描模式），而不是用混淆视听的 `raise ImportError`。
3. **AST 核心刚需化**：
   - 将 `tree-sitter` 移入默认安装，杜绝使用正则提取带来的失真污染。

> **报告版本：专家评审修订版**  
> 现状：已精准对齐 4 大症结，即将进入正式代码破除阶段！
