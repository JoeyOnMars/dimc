# Dimcause 开发本体 (Dev-Ontology) v1.1

**版本**: 1.1.0  
**创建日期**: 2026-02-10  
**最后更新**: 2026-02-14 (更名 Trax→Dimcause, 路径对齐)  
**状态**: ✅ Active  
**理论基础**: DIKW模型 + 本体论五层结构

---

## 一、本体概述

### 1.1 定义

**Dev-Ontology (开发本体)** 是 Dimcause V6.0 的核心理论框架，用于描述软件工程活动中实体（类）、关系（谓语）和约束（公理）的语义结构。

### 1.2 目标

1. **语义化因果链**：将平面的事件列表转化为有向因果网络
2. **跨工具互操作**：通过统一的URI和JSON-LD实现跨IDE、跨Agent的知识共享
3. **推理能力**：基于公理进行自动推理，发现隐性知识

### 1.3 与DIKW模型的映射

| DIKW层级 | Dev-Ontology对应 | Dimcause 实现 |
|---------|----------------|----------|
| Data | Instances（实例） | Event记录 |
| Information | Relations（关系） | CausalLink |
| Knowledge | Classes + Axioms | 本体定义 |
| Wisdom | 推理规则 | dimc why 叙事生成 |

---

## 二、类定义 (Classes)

### 2.1 Requirement (需求)

**定义**: 用户需求、产品需求或技术需求的正式声明

**属性**:
- `id`: 唯一标识 (如`req-001`)
- `summary`: 需求摘要
- `source`: 来源 (PRD文档、用户反馈、技术债务)
- `priority`: 优先级 (P0-P3)

**URI格式**: `dev://requirement/{hash}`

**示例**:
```json
{
  "@id": "dev://requirement/auth_timeout",
  "@type": "Requirement",
  "summary": "登录超时时间需要适配弱网环境",
  "source": "用户反馈 (Slack #feedback)",
  "priority": "P1"
}
```

---

### 2.2 Decision (决策)

**定义**: 开发过程中的技术决策或架构选择

**属性**:
- `id`: 决策ID (如`dec-001`)
- `summary`: 决策摘要
- `rationale`: 决策理由
- `alternatives`: 被否决的备选方案
- `timestamp`: 决策时间

**URI格式**: `dev://decision/{hash}`

**示例**:
```json
{
  "@id": "dev://decision/timeout_30s",
  "@type": "Decision",
  "summary": "将auth超时从10s增加到30s",
  "rationale": "兼容弱网环境，减少用户投诉",
  "alternatives": ["使用自适应超时", "增加重试机制"]
}
```

---

### 2.3 Commit (代码提交)

**定义**: Git版本控制系统中的原子提交单元

**属性**:
- `hash`: Git SHA
- `message`: 提交说明
- `author`: 提交者
- `timestamp`: 提交时间
- `files_changed`: 修改的文件列表

**URI格式**: `dev://commit/{git_hash}`

**示例**:
```json
{
  "@id": "dev://commit/abc123def456",
  "@type": "Commit",
  "message": "fix: increase auth timeout to 30s",
  "files_changed": ["src/auth.py"]
}
```

---

### 2.4 Function (代码符号)

**定义**: 代码中的函数、方法或类

**属性**:
- `name`: 符号名称
- `file`: 所在文件路径
- `line_range`: 行范围 (如`L45-L67`)
- `signature`: 函数签名

**URI格式**: `dev://function/{file_hash}#{symbol_name}`

**示例**:
```json
{
  "@id": "dev://function/auth_py#get_connection",
  "@type": "Function",
  "name": "get_connection",
  "file": "src/auth.py",
  "line_range": "L45-L67"
}
```

---

### 2.5 Incident (事故/Bug)

**定义**: 生产环境或测试中发现的故障

**属性**:
- `id`: 事故ID (如`INC-042`)
- `severity`: 严重程度 (Critical/High/Medium/Low)
- `summary`: 事故描述
- `root_cause`: 根本原因分析

**URI格式**: `dev://incident/{id}`

**示例**:
```json
{
  "@id": "dev://incident/INC-042",
  "@type": "Incident",
  "severity": "High",
  "summary": "并发死锁导致登录失败"
}
```

---

### 2.6 Experiment (实验/尝试)

**定义**: A/B测试、POC或临时尝试

**属性**:
- `id`: 实验ID
- `hypothesis`: 假设
- `result`: 实验结果
- `conclusion`: 结论

**URI格式**: `dev://experiment/{id}`

**示例**:
```json
{
  "@id": "dev://experiment/async_pool_test",
  "@type": "Experiment",
  "hypothesis": "异步连接池可提升20%性能",
  "result": "性能提升18%，但引入死锁风险"
}
```

---

### 2.7 CausalEngine (因果引擎)

**定义**: 驱动系统核心因果逻辑与拓扑存储的引擎组件

**属性**:
- `version`: 引擎迭代版本 (如`v1.0`)
- `capabilities`: 核心能力特征集

**URI格式**: `dev://engine/{version}`

**示例**:
```json
{
  "@id": "dev://engine/v1.0",
  "@type": "CausalEngine",
  "version": "v1.0",
  "capabilities": ["时间锥拦截", "拓扑隔离"]
}
```

---

## 三、关系定义 (Relations)

### 3.0 关系分类法则 (Relation Taxonomy)

在 DIMCAUSE 的底层物理实现中，本体定义的所有关联行为被**极其严格地区分为两类**。此分界线构成了存储抽象（GraphStore）与推理引擎（CausalEngine）的代码级路由分界线（详见 Task 007-01）：

1. **因果边 (Causal Edges)**：
   - **特征**：描述具有时间发展先后顺序的动作触发、问题修复或结论验证。具备明确的时序漏斗（向前传递）与因果衍生特性。
   - **路由约束**：必须调用 `CausalEngine.link_causal` 写入。受“时间倒流（`CausalTimeReversedError`）”和“拓扑孤岛（`TopologicalIsolationError`）”的底层时空硬锁保护。
   - **包含的谓词**：`triggers`, `validates`, `realizes`, `fixes`（对应代码库里的 `CAUSAL_RELATIONS_SET` 白名单）。

2. **结构边 (Structural Edges)**：
   - **特征**：描述静态的层级划分、属性映射、接口实现。无发生时间的顺序限制，不受时空漏斗的检测约束。
   - **路由约束**：必须调用 `GraphStore.add_structural_relation` 写入。**严禁**越级或绕过分类直接调用底层 `add_relation`。
   - **包含的谓词**：`implements`, `modifies`, `overrides`。

---
### 3.1 implements (实现)

**定义**: Decision实现某个Requirement

**域**: Decision  
**值域**: Requirement  
**方向**: Decision --implements--> Requirement

**语义**: "该决策是为了实现某需求"

**示例**:
```turtle
dev://decision/timeout_30s  implements  dev://requirement/auth_timeout
```

---

### 3.2 realizes (落地)

**定义**: Commit落地某个Decision

**域**: Commit  
**值域**: Decision  
**方向**: Commit --realizes--> Decision

**语义**: "该提交实现了某决策"

**示例**:
```turtle
dev://commit/abc123  realizes  dev://decision/timeout_30s
```

---

### 3.3 modifies (修改)

**定义**: Commit修改了某个Function

**域**: Commit  
**值域**: Function  
**方向**: Commit --modifies--> Function

**语义**: "该提交修改了某函数"

**示例**:
```turtle
dev://commit/abc123  modifies  dev://function/auth_py#get_connection
```

---

### 3.4 triggers (触发)

**定义**: Incident触发新的Decision

**域**: Incident  
**值域**: Decision  
**方向**: Incident --triggers--> Decision

**语义**: "该事故促使我们做出新决策"

**示例**:
```turtle
dev://incident/INC-042  triggers  dev://decision/singleton_pattern
```

---

### 3.5 validates (验证)

**定义**: Experiment验证某个Decision

**域**: Experiment  
**值域**: Decision  
**方向**: Experiment --validates--> Decision

**语义**: "该实验验证了某决策的可行性"

**示例**:
```turtle
dev://experiment/async_pool_test  validates  dev://decision/async_pool
```

---

### 3.6 overrides (覆盖)

**定义**: Decision覆盖之前的Decision

**域**: Decision  
**值域**: Decision  
**方向**: Decision --overrides--> PreviousDecision

**语义**: "新决策取代旧决策"

**示例**:
```turtle
dev://decision/singleton_pattern  overrides  dev://decision/async_pool
```

---

## 四、公理定义 (Axioms)

### 4.1 Commit必须有因

**公理**: 每个Commit必须至少realize一个Decision或fix一个Incident

**形式化表达**:
```prolog
∀ commit: Commit → ∃ (decision: Decision ∨ incident: Incident)
  (commit realizes decision) ∨ (commit fixes incident)
```

**验证规则**:
```python
def validate_commit_has_cause(commit: Commit) -> bool:
    return (
        len(commit.get_related(relation="realizes")) > 0 or
        len(commit.get_related(relation="fixes")) > 0
    )
```

**违反后果**: 警告 (Warning)，建议补充关联信息

---

### 4.2 Decision不能循环依赖

**公理**: Decision的overrides关系不能形成环

**形式化表达**:
```prolog
∀ d1, d2: Decision → ¬(d1 overrides d2 ∧ d2 overrides d1)
```

**验证规则**:
```python
def validate_no_decision_cycle(graph: nx.DiGraph) -> bool:
    try:
        nx.find_cycle(graph, orientation='original')
        return False  # 发现环
    except nx.NetworkXNoCycle:
        return True  # 无环
```

**违反后果**: 错误 (Error)，拒绝创建关系

---

### 4.3 Function修改可回溯

**公理**: 每个Function的修改历史必须可回溯到至少一个Decision

**形式化表达**:
```prolog
∀ function: Function → ∃ decision: Decision
  ∃ commit: Commit (commit modifies function ∧ commit realizes decision)
```

**验证规则**:
```python
def validate_function_traceability(function: Function) -> bool:
    commits = function.get_modifying_commits()
    return all(
        len(commit.get_related(relation="realizes")) > 0 
        for commit in commits
    )
```

**违反后果**: 警告 (Warning)，提示"孤立修改"

---

## 五、实现规范

### 5.1 YAML Schema

本体定义使用YAML格式存储于`src/dimcause/core/ontology.yaml`:

```yaml
version: "1.0.0"

classes:
  - name: Requirement
    uri_prefix: "dev://requirement/"
    properties:
      - summary: string
      - source: string
      - priority: enum[P0, P1, P2, P3]
  
  - name: Decision
    uri_prefix: "dev://decision/"
    properties:
      - summary: string
      - rationale: string
      - alternatives: list[string]
  
  - name: Commit
    uri_prefix: "dev://commit/"
    properties:
      - hash: string
      - message: string
      - files_changed: list[string]
  
  - name: Function
    uri_prefix: "dev://function/"
    properties:
      - name: string
      - file: string
      - line_range: string
  
  - name: Incident
    uri_prefix: "dev://incident/"
    properties:
      - severity: enum[Critical, High, Medium, Low]
      - summary: string
  
  - name: Experiment
    uri_prefix: "dev://experiment/"
    properties:
      - hypothesis: string
      - result: string
  
  - name: CausalEngine
    uri_prefix: "dev://engine/"
    properties:
      - version: string
      - capabilities: list[string]

relations:
  - name: implements
    domain: Decision
    range: Requirement
    inverse: implemented_by
  
  - name: realizes
    domain: Commit
    range: Decision
    inverse: realized_by
  
  - name: modifies
    domain: Commit
    range: Function
    inverse: modified_by
  
  - name: triggers
    domain: Incident
    range: Decision
    inverse: triggered_by
  
  - name: validates
    domain: Experiment
    range: Decision
    inverse: validated_by
  
  - name: overrides
    domain: Decision
    range: Decision
    inverse: overridden_by

axioms:
  - id: commit_must_have_cause
    description: "每个Commit必须至少realize一个Decision或fix一个Incident"
    severity: warning
  
  - id: no_decision_cycle
    description: "Decision的overrides关系不能形成环"
    severity: error
  
  - id: function_traceability
    description: "Function修改必须可回溯到Decision"
    severity: warning
```

---

### 5.2 JSON-LD Context

统一的JSON-LD上下文定义（用于跨工具互操作）:

```json
{
  "@context": {
    "dev": "https://schema.dimcause.dev/v1#",
    "prov": "http://www.w3.org/ns/prov#",
    
    "Requirement": "dev:Requirement",
    "Decision": "dev:Decision",
    "Commit": "dev:Commit",
    "Function": "dev:Function",
    "Incident": "dev:Incident",
    "Experiment": "dev:Experiment",
    "CausalEngine": "dev:CausalEngine",
    
    "implements": {"@id": "dev:implements", "@type": "@id"},
    "realizes": {"@id": "dev:realizes", "@type": "@id"},
    "modifies": {"@id": "dev:modifies", "@type": "@id"},
    "triggers": {"@id": "dev:triggers", "@type": "@id"},
    "validates": {"@id": "dev:validates", "@type": "@id"},
    "overrides": {"@id": "dev:overrides", "@type": "@id"}
  }
}
```

---

## 六、验收标准

### Phase 1 完成标准

- [x] 本文档创建（DEV_ONTOLOGY.md）
- [x] `src/dimcause/core/ontology.yaml` 文件创建
- [x] `src/dimcause/core/ontology.py` 实现 Ontology 类
- [x] 单元测试覆盖 YAML 解析和公理验证
- [ ] 文档通过技术评审

---

## 七、未来扩展

### 7.1 待考虑的类

- **TestCase** (测试用例): 用于关联测试失败与Bug修复
- **Document** (文档): ADR、设计文档等
- **ChatMessage** (聊天记录): IDE内的讨论或Slack消息

### 7.2 待考虑的关系

- **depends_on**: Requirement之间的依赖
- **breaks**: Commit破坏了某个Function的功能
- **refutes**: Experiment反驳了某个Decision

### 7.3 待考虑的公理

- "一个Function不能在同一个Commit中既被修改又被删除"
- "Incident的severity必须与触发的Decision的priority对应"

---

## 八、参考文献

1. **DIKW模型**: [Wikipedia - DIKW Pyramid](https://en.wikipedia.org/wiki/DIKW_pyramid)
2. **本体论五层结构**: Gruber, T. (1993). "A translation approach to portable ontology specifications"
3. **JSON-LD规范**: [W3C JSON-LD 1.1](https://www.w3.org/TR/json-ld11/)
4. **Provenance Ontology**: [W3C PROV-O](https://www.w3.org/TR/prov-o/)
5. **Gemini DIKW讨论**: `docs/logs/raw/Gemini/DIKW与本体的深度讨论-GEMINI-20260210.md`
6. **Perplexity战略回复**: `docs/logs/raw/Perplexity/对Gemini讨论的回复`

---

**签署**: AI Agent  
**审核状态**: ✅ v1.1 对齐更新 (2026-02-14)
