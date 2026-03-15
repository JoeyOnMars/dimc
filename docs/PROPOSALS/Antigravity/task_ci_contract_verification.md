# Task: 契约验证自动化（从"荣誉制度"升级为"物理闸门"）

**分支**: `feat/contract-verification-ci`
**审批状态**: Pending User Approval

## 目标

把 `.agent/rules/` 中最关键的两条规则从自然语言翻译成 CI 脚本，集成到现有的 `scripts/check.zsh` 流程中：
1. `api_contracts.yaml` 中定义的函数签名必须与源码一致（契约校验）。
2. L1 层核心文件不允许在非 RFC 分支上被修改（L1 不可变性校验）。

## 背景

当前体系中，契约遵守和 L1 不可变性完全依赖 Agent 的"荣誉制度"（Prompt 遵从）。本次任务将这些约束硬编码为可执行脚本，使其成为物理级阻断。

---

## 提议的修改

### 一、修正 L1 契约元数据

#### [MODIFY] [api_contracts.yaml](file:///Users/mini/projects/GithubRepos/dimc/docs/api_contracts.yaml)

修正 `module` 字段为完整的 Python 包路径，确保 L1 数据源自洽。**仅改 module 字段值，不动签名、参数、返回结构。**

| 函数 | 当前 module | 修正为 |
|------|------------|--------|
| `sanitize` | `security` | `dimcause.utils.security` |
| `sanitize_file` | `security` | `dimcause.utils.security` |
| `index_file` | `core.code_indexer` | `dimcause.core.code_indexer` |
| `find_symbol` | `core.code_indexer` | `dimcause.core.code_indexer` |
| `trace_symbol` | `core.code_indexer` | `dimcause.core.code_indexer` |
| `search_vectors` | `storage.vector_store` | `dimcause.storage.vector_store` |
| `search_engine_search` | `search.engine` | `dimcause.search.engine` |
| `add_structural_relation` | `storage.graph_store` | `dimcause.storage.graph_store` |
| `_internal_add_relation` | `storage.graph_store` | `dimcause.storage.graph_store` |
| `link_causal` | `reasoning.causal_engine` | `dimcause.reasoning.causal_engine` |

---

### 二、新建契约校验脚本

#### [NEW] [verify_contracts.py](file:///Users/mini/projects/GithubRepos/dimc/scripts/verify_contracts.py)

用 Python AST 模块解析源码，逐一校验 `api_contracts.yaml` 中函数定义的签名是否与实际代码一致。

**校验范围**：
- `status: stable` 和 `status: experimental`：完整签名校验（函数存在性 + 参数名 + 参数默认值 + 返回类型）。
- `status: missing_implementation` 和 `status: broken_implementation`：仅检查函数是否存在，不校验签名。

**实现要点**：
- `yaml.safe_load` 解析契约。
- `ast.parse` + `ast.walk` 解析源码，提取函数签名。
- `module` 字段直接转换为文件路径：`src/{module.replace('.', '/')}.py`。
- 参数名列表匹配、默认值存在性匹配。类型标注做字符串级松弛匹配。
- 不一致时 `sys.exit(1)`，全部通过 `sys.exit(0)`。

---

### 三、集成到 CI 检查流

#### [MODIFY] [check.zsh](file:///Users/mini/projects/GithubRepos/dimc/scripts/check.zsh)

在现有 ruff + pytest 之后追加：

1. **契约签名校验**：`python scripts/verify_contracts.py`，失败则 `exit 1`。
2. **L1 不可变性校验**：检查当前分支（相对于 `main`）是否修改了 L1 文件，非 `rfc/*` 分支修改则 `exit 1`。

L1 受保护文件清单：
- `docs/PROJECT_ARCHITECTURE.md`
- `docs/V6.0/DEV_ONTOLOGY.md`
- `docs/api_contracts.yaml`
- `docs/STORAGE_ARCHITECTURE.md`

---

## 验证计划

1. `source .venv/bin/activate && python scripts/verify_contracts.py` — 所有 stable/experimental 函数签名通过。
2. `source .venv/bin/activate && bash scripts/check.zsh` — 完整流程通过。
3. L1 负面测试：临时改 `api_contracts.yaml` 后跑 `check.zsh`，预期报 `L1 VIOLATION`。

---

## M 专家执行指令

在获得 User 的 `Approved/已确认` 后，M 专家按以下顺序执行：

1. **切换分支**：`git checkout feat/contract-verification-ci`
2. **修正 YAML**：按上表修正 `docs/api_contracts.yaml` 中所有 `module` 字段值。不动签名、参数、返回结构。
3. **新建脚本**：按照"二、新建契约校验脚本"的要求，创建 `scripts/verify_contracts.py`。
4. **修改 check.zsh**：按照"三、集成到 CI 检查流"的要求，追加契约校验和 L1 不可变性检查。
5. **运行验证**：执行验证计划中的 3 项测试，全部通过后提交。
6. **Commit & Push**：`git add . && git commit -m "feat: 契约验证自动化 - 从荣誉制度升级为物理闸门" && git push origin HEAD`
7. **输出**：`[PR_READY] 分支 feat/contract-verification-ci 开发与测试已通过，请求审查并合并。`
