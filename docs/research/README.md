# Research Documentation

**目录**: `/docs/research/`  
**用途**: 存放技术调研报告和研究课题文档

---

## 📑 当前研究课题

详见 [index.md](./index.md)（研究课题追踪）

---

## 📁 文档列表

### 已完成研究

- **[RT-000: Model Selection Evaluation](./RT-000_model_selection_evaluation.md)**  
  模型选型评估（embedding & reranker）

- **[RT-001: AI Tools Integration](./RT-001_ai_tools_integration.md)**  
  AI编程工具集成调研（2026年2月）

### 进行中研究

详见 [index.md](./index.md)

---

## 📝 文档规范

### 命名格式
```
RT-XXX_topic_name.md
```
- `RT-XXX`: Research Topic 编号（3位数字）
- `topic_name`: 用下划线分隔的主题名（小写）

### 内容结构
```markdown
# [课题名称]

**状态**: 进行中 / 已完成  
**创建日期**: YYYY-MM-DD  
**研究者**: [名字/团队]

## 研究问题
...

## 研究方法
...

## 发现与结论
...

## 推荐方案
...

## 参考资料
...
```

---

## 🔀 与 `dev/` 的区别

| 目录 | 用途 | 示例 |
|------|------|------|
| **`research/`** | **技术调研、方案评估** | 模型选型、工具集成调研 |
| **`dev/`** | **开发计划、实现文档** | Roadmap、Alignment Proof |

**原则**:
- 调研性质 → `research/`
- 实施性质 → `dev/`
