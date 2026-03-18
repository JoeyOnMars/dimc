# Changelog

All notable changes to Dimcause will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned for v5.2.0
- 代码级别追溯 (Code-level tracing)
- AST 分析 (AST analysis)
- 因果链推理 (Causal chain reasoning)
- 模板系统 (`dimc template`)
- Web Dashboard

---

## [5.1.0] - 2026-01-19 (Beta)

### 🎉 Major Milestone
完整的四层架构实现 + 文档体系建设。

### Added - 代码实现 (2026-01-19)

#### 四层架构核心
- `src/dimcause/watchers/` - Layer 1: Ghost Mode 监听器
  - `ClaudeWatcher` - Claude Code 对话监听
  - `CursorWatcher` - Cursor IDE 监听
  - `WindsurfWatcher` - Windsurf IDE 监听
- `src/dimcause/extractors/` - Layer 2: LLM Refinery
  - `LiteLLMClient` - 统一 LLM 接口
  - `BasicExtractor` - LLM + Regex 降级提取
  - `ASTAnalyzer` - 代码 AST 分析
- `src/dimcause/storage/` - Layer 3: Hybrid Storage
  - `MarkdownStore` - 人类可读持久化
  - `VectorStore` - ChromaDB 语义索引
  - `GraphStore` - NetworkX 关系图谱
- `src/dimcause/search/` - Layer 4: Query Interface
  - `SearchEngine` - 统一搜索（text/semantic/hybrid）

#### CLI 命令
- `dimc daemon start/stop/status` - 后台服务管理
- `dimc search <query>` - 多模式搜索

#### 后台服务
- `src/dimcause/daemon.py` - DimcauseDaemon 守护进程
  - 自动启动 Watchers
  - 数据处理流水线
  - 优雅依赖降级

#### 测试套件
- `tests/test_v51_components.py` - 核心组件测试
- `tests/test_daemon.py` - Daemon/Watcher 测试
- `tests/test_extractors.py` - 提取器/生命周期测试
- **432 passed, 76% 覆盖率**

#### 项目配置
- `pyproject.toml` - PEP 621 项目配置
  - 依赖分组: core, full, dev, ast
  - pytest/coverage/mypy/ruff 配置
- `src/dimcause/__init__.py` - 包入口，导出 __version__

### Added - 文档体系 (2026-01-18)
#### 核心文档 (14份)
- `docs/V5.1/1_MASTERPLAN.md` - 项目总体规划
- `docs/V5.1/2_ARCHITECTURE.md` - 系统架构设计
- `docs/V5.1/3_MARKET_STRATEGY.md` - 市场策略
- `docs/V5.1/4_CORE_SCOPE.md` - 核心范围定义
- `docs/V5.1/5_DATA_SCHEMA.md` - 数据模型
- `docs/V5.1/6_API_SPEC.md` - API 规范
- `docs/V5.1/7_DESIGN_PHILOSOPHY.md` - 设计哲学(七大公理)
- `docs/V5.1/8_DATA_PIPELINE.md` - 数据流水线（含5张Mermaid图）
- `docs/V5.1/9_CONCURRENCY_DESIGN.md` - 并发控制设计
- `docs/V5.1/10_RELIABILITY_DESIGN.md` - 可靠性与自愈设计
- `docs/V5.1/11_SECURITY_DESIGN.md` - 安全设计
- `docs/V5.1/2-1_BU_INTEGRATION_STRATEGY.md` - Browser-Use 集成
- `docs/V5.1/2-2_MEM0_REFACTOR_STRATEGY.md` - Mem0 重构策略
- `docs/V5.1/2-3_ECOSYSTEM_NOTES_APPS.md` - 笔记应用生态

#### 工程规范文档 (8份)
- `docs/V5.1/Engineering/TESTING_STRATEGY.md` - 完整测试策略
- `docs/V5.1/Engineering/DEPLOYMENT_ARCHITECTURE.md` - 部署架构
- `docs/V5.1/Engineering/PERFORMANCE_BENCHMARKS.md` - 性能基准
- `docs/V5.1/Engineering/PRIVACY_COMPLIANCE.md` - 隐私与合规(GDPR/CCPA/SOC2)
- `docs/V5.1/Engineering/DEVELOPER_GUIDE.md` - 开发者指南（中文）
- `docs/V5.1/Engineering/USER_MANUAL.md` - 用户手册（中文）
- `docs/V5.1/Engineering/PROJECT_AUDIT_REPORT.md` - 项目全面审核报告
- `docs/V5.1/Engineering/REUSABILITY_PORTABILITY_ANALYSIS.md` - 复用性分析

#### 参考文档 (4份)
- `docs/V5.1/Reference/BU_SDK_ANALYSIS.md`
- `docs/V5.1/Reference/MEM0_DEEP_DIVE.md`
- `docs/V5.1/Reference/TECH_CLAUDE_GHOST_MODE.md`
- `docs/V5.1/Reference/COMPARATIVE_LESSONS.md`
- `docs/V5.1/Reference/COMPETITIVE_ANALYSIS_SUPERTHREAD.md` - Superthread竞品分析

#### 战略文档
- `docs/V5.1/SUPERSEDING_STRATEGY.md` - 超越战略（降维打击）
- `docs/V5.1/AI_ACCELERATED_ROADMAP.md` - AI加速路线图
- `docs/V5.1/README.md` - 完整文档索引

### Changed
- 项目从 Documentation Complete 提升到 Beta 状态
- 文档完整性从70%提升到95%
- 代码实现从骨架提升到功能完整

### Security
- 完整的威胁模型分析
- 敏感信息检测设计（10种模式）
- Agent认证机制设计
- GDPR/CCPA/SOC2合规策略

### Documentation
- 总计26份核心文档（约15万字）
- 200+代码示例
- 10+流程图
- 50+对比表格

---

## [5.0.0] - 2026-01-15 (Historical)

### Added
- V5.0 初始架构设计
- Trinity Architecture 概念
- Ghost Mode 技术方案
- 初始竞品分析文档

### Deprecated
- V4.0 架构已归档至 `docs/V5.0_OLD/`

---

## [4.0.0] - 2026-01-10 (Historical)

### Added
- 基础CLI功能
- 简单的日志记录
- Git集成

---

## Links

[Unreleased]: https://github.com/JoeyOnMars/dimc/compare/v5.1.0...HEAD
[5.1.0]: https://github.com/JoeyOnMars/dimc/compare/v5.0.0...v5.1.0
[5.0.0]: https://github.com/JoeyOnMars/dimc/compare/v4.0.0...v5.0.0
[4.0.0]: https://github.com/JoeyOnMars/dimc/releases/tag/v4.0.0
