# DIMCAUSE 研究课题（Research Topics）

**状态**: 📋 Active  
**创建日期**: 2026-02-15  
**目的**: 追踪需要深入研究的技术问题和集成方案

---

## 进行中 (In Progress)

### RT-001: AI编程工具集成方案调研
- **状态**: ✅ 已完成（2026-02-15）
- **成果**: `ai_tools_research_2026.md`
- **关键发现**:
  - 识别9种主流工具
  - Claude Code ≠ Claude Desktop
  - Cursor/Continue.dev 100%自动集成

---

## 待研究 (To Research)

### RT-002: GitHub Copilot Chat Exporter 实现机制 🔍

**优先级**: P1 - High  
**创建日期**: 2026-02-15  
**预计工期**: 1-2天

#### 研究问题
1. `github-copilot-chat-exporter` 扩展的具体实现原理？
2. 是否需要手动触发导出，还是自动监听？
3. 导出的数据格式和完整性如何？
4. 能否在此基础上构建 DIMCAUSE 的自动集成？

#### 研究方向
- [ ] 查阅扩展源代码（如果开源）
- [ ] 分析 VS Code Extension API 中的聊天数据访问机制
- [ ] 测试实际导出流程和文件格式
- [ ] 评估集成到 DIMCAUSE 的技术可行性

#### 预期成果
- 技术实现报告（`copilot_exporter_analysis.md`）
- DIMCAUSE 集成方案（自动 vs 半自动）
- 代码示例（如适用）

---

### RT-003: Claude Code CLI 上下文持久化方案 🔍

**优先级**: P1 - High  
**创建日期**: 2026-02-15  
**预计工期**: 2-3天

#### 研究问题
1. Claude Code CLI 是否支持上下文自动保存？
2. 市面上有哪些工具支持 Claude Code 的上下文注入？
3. 这些工具是如何实现的？（API? 文件系统? Shell Hook?）
4. DIMCAUSE 能否复用这些机制？

#### 研究方向
- [ ] 调研 Claude Code 的官方文档（MCP, CLAUDE.md）
- [ ] 查找第三方工具（如 `claude-context-manager`）
- [ ] 分析 Model Context Protocol (MCP) 的集成点
- [ ] 测试 `CLAUDE.md` 文件的自动加载机制
- [ ] 研究 Shell Hook 或 Wrapper 脚本的可行性

#### 预期成果
- 上下文持久化技术报告（`claude_code_context_persistence.md`）
- 主流第三方工具对比（功能、自动化程度、许可证）
- DIMCAUSE 集成方案（推荐 Tier 1/2/3）

---

## 未来研究 (Future)

### RT-004: Windsurf 加密 .pb 文件解析 🔐

**优先级**: P2 - Medium  
**原因**: Windsurf 使用加密 Protocol Buffer 存储对话  
**挑战**: 需要逆向工程或官方 API

---

### RT-005: 跨工具对话去重算法 🧮

**优先级**: P2 - Medium  
**场景**: 用户同时使用 Cursor + Copilot，同一对话可能被重复捕获  
**研究方向**: 语义相似度、时间戳关联、内容指纹

---

### RT-006: AI对话质量评估指标 📊

**优先级**: P3 - Low  
**目的**: 自动识别高价值决策对话 vs 日常问答  
**研究方向**: LLM评分、关键词权重、图谱重要性

---

## 研究流程

### 1. 启动研究
```bash
# 创建研究分支
git checkout -b research/RT-XXX-topic-name

# 创建研究文档
touch docs/research/RT-XXX_topic_name.md
```

### 2. 研究过程
- 📖 阅读官方文档和源码
- 🔬 实验和测试
- 📝 记录发现和笔记
- 💡 提出解决方案

### 3. 完成研究
- ✅ 更新研究状态为"已完成"
- 📄 生成最终报告
- 🔀 合并到主分支（如有代码）
- 📌 在 `STATUS.md` 中记录

---

## 模板

### 新研究课题模板

```markdown
### RT-XXX: [课题名称] 🔍

**优先级**: P1/P2/P3  
**创建日期**: YYYY-MM-DD  
**预计工期**: X天

#### 研究问题
1. 问题1
2. 问题2

#### 研究方向
- [ ] 方向1
- [ ] 方向2

#### 预期成果
- 成果1
- 成果2
```

---

## 决策准则

### 何时创建研究课题？

✅ **应该创建**:
- 技术方案不明确，需要调研多个选项
- 涉及第三方工具/API 的集成
- 算法或架构设计需要原型验证
- 预计需要 1天+ 的探索时间

❌ **不需要创建**:
- 简单的 Bug 修复
- 明确的功能实现（已有设计）
- 文档更新
- 代码重构

---

## 研究成果归档

所有研究报告存放在：
```
docs/research/
├── RT-001_ai_tools_integration.md        ✅ 已完成
├── RT-002_copilot_exporter_analysis.md   🔍 待研究
├── RT-003_claude_code_context.md         🔍 待研究
└── ...
```

---

## 当前待办 (Next Steps)

1. **RT-002**: 研究 GitHub Copilot Chat Exporter 实现
2. **RT-003**: 研究 Claude Code 上下文持久化方案
3. 根据研究成果更新 `IDE_INTEGRATION.md`
