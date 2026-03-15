# 贡献指南 (Contributing Guide)

> 感谢您对 Dimcause (DIMCAUSE) 的关注！我们欢迎所有形式的贡献。

---

## 📋 目录

1. [行为准则](#行为准则)
2. [如何贡献](#如何贡献)
3. [开发流程](#开发流程)
4. [代码规范](#代码规范)
5. [提交规范](#提交规范)
6. [测试要求](#测试要求)
7. [文档贡献](#文档贡献)

---

## 行为准则

### 我们的承诺

为了营造一个开放和友好的环境，我们承诺：

- ✅ 使用友好和包容的语言
- ✅ 尊重不同的观点和经验
- ✅ 优雅地接受建设性批评
- ✅ 关注对社区最有利的事情
- ✅ 对其他社区成员表示同理心

### 不可接受的行为

- ❌ 使用性别化语言或imagery
- ❌ 人身攻击或政治攻击
- ❌ 公开或私下骚扰
- ❌ 未经明确许可发布他人信息
- ❌ 其他不专业或不受欢迎的行为

---

## 如何贡献

### 报告 Bug

**在提交 Issue 前**，请：
1. 检查当前仓库的已有 Issues
2. 确保使用最新版本
3. 尝试最小化复现步骤

**Bug Report 模板**:
```markdown
**描述**
清晰简洁地描述 bug

**复现步骤**
1. 执行 '...'
2. 点击 '....'
3. 滚动到 '....'
4. 看到错误

**预期行为**
应该发生什么

**实际行为**
实际发生了什么

**环境**
- OS: [e.g. macOS 14.0]
- Python: [e.g. 3.10.5]
- DIMCAUSE: [e.g. 5.1.0]

**日志**
粘贴相关日志（如果有）
```

---

### 建议新功能

**Feature Request 模板**:
```markdown
**功能描述**
清晰描述你想要的功能

**使用场景**
这个功能解决什么问题？

**建议方案**
你希望如何实现？

**替代方案**
考虑过其他方案吗？

**额外信息**
任何其他补充
```

---

### 提交代码

#### 1. Fork 仓库

```bash
# Fork 到你的账号
# 然后 clone
git clone https://github.com/YOUR_USERNAME/dimc.git
cd dimc
```

#### 2. 创建分支

```bash
# 从 main 分支创建
git checkout main
git pull origin main

# 创建贡献分支（当前仓库统一使用 codex/ 前缀）
git checkout -b codex/feat-short-topic

# 或 bug 修复分支
git checkout -b codex/fix-short-topic
```

#### 3. 搭建开发环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install
```

#### 4. 编写代码

- 遵循 [代码规范](#代码规范)
- 添加单元测试
- 更新文档（如果需要）

#### 5. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/<path_to_relevant_test>.py

# 查看覆盖率（可选）
pytest --cov=dimcause --cov-report=term-missing
```

#### 6. 提交代码

```bash
# 添加修改
git add .

# 提交（遵循提交规范）
git commit -m "feat(cli): add search command"

# 推送到你的 fork
git push origin codex/feat-short-topic
```

#### 7. 创建 Pull Request

1. 访问你的 fork：`https://github.com/YOUR_USERNAME/dimc`
2. 点击 "New Pull Request"
3. 选择: `base: main` ← `compare: codex/feat-short-topic`
4. 填写 PR 模板
5. 提交并等待 Review

---

## 开发流程

### 分支策略

```
main (主分支)
  ↑
codex/feat-xxx (功能分支)
codex/fix-xxx (修复分支)
```

### PR Review 流程

1. **自动检查**（必须通过）
   - ✅ CI 测试通过
   - ✅ 代码覆盖率不下降
   - ✅ Black/isort 格式检查通过
   - ✅ mypy 类型检查通过

2. **人工 Review**（至少1个 Maintainer 批准）
   - ✅ 代码质量
   - ✅ 测试完整性
   - ✅ 文档更新
   - ✅ 符合项目目标

3. **合并**
   - 使用 "Squash and Merge"
   - 保持提交历史清晰

---

## 代码规范

请注意：本文件描述的是当前仓库的贡献与协作方式，不定义 DIMCAUSE 的产品定位。产品架构应以 `docs/ARCHITECTURE_INDEX.md`、正式架构文档和 proposal 为准。

### Python 风格

遵循 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

**关键点**:
```python
# ✅ 好的命名
class SensitiveDataDetector:
    def detect_api_keys(self, text: str) -> List[str]:
        pass

# ❌ 不好的命名
class SDD:
    def det(self, t):
        pass

# ✅ 好的类型注解
def process_event(
    event: Event,
    timeout: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    处理事件并返回结果。
    
    Args:
        event: 要处理的事件
        timeout: 超时时间（秒）
    
    Returns:
        处理结果，失败返回 None
    
    Raises:
        TimeoutError: 处理超时
    """
    pass

# ❌ 缺少注解
def process_event(event, timeout=30):
    pass
```

### 格式化工具

```bash
# Black（自动格式化）
black .

# isort（自动排序 imports）
isort .

# mypy（类型检查）
mypy dimcause

# 全部一起运行
pre-commit run --all-files
```

---

## 提交规范

### Commit Message 格式

```
<类型>(<范围>): <主题>

<详细描述>（可选）

<关联 Issue>（可选）
```

### 类型 (Type)

| 类型 | 说明 | 示例 |
| :--- | :--- | :--- |
| `feat` | 新功能 | `feat(search): add hybrid search` |
| `fix` | Bug 修复 | `fix(watcher): handle permission errors` |
| `docs` | 文档更新 | `docs(readme): update installation guide` |
| `style` | 代码格式 | `style: run black formatter` |
| `refactor` | 重构 | `refactor(storage): extract adapter layer` |
| `test` | 测试相关 | `test(llm): add parser fallback tests` |
| `chore` | 构建/工具 | `chore: update dependencies` |
| `perf` | 性能优化 | `perf(search): add vector db index` |

### 示例

```bash
# 好的提交
git commit -m "feat(cli): add template command for weekly review"
git commit -m "fix(config): handle missing config file gracefully"
git commit -m "docs(api): add examples for search API"

# 不好的提交
git commit -m "update"
git commit -m "fix bug"
git commit -m "WIP"
```

---

## 测试要求

### 测试覆盖率

- **单元测试**: >80%
- **集成测试**: 核心流程 100%
- **E2E 测试**: 关键场景 100%

### 测试文件组织

```
tests/
├── unit/           # 单元测试
│   ├── test_config.py
│   ├── test_detector.py
│   └── test_watcher.py
├── integration/    # 集成测试
│   ├── test_pipeline.py
│   └── test_storage.py
├── e2e/            # E2E 测试
│   └── test_user_workflow.py
└── conftest.py     # 共享 fixtures
```

### 编写测试

```python
# tests/unit/test_detector.py
import pytest
from dimcause.security import SensitiveDataDetector

class TestSensitiveDataDetector:
    def setup_method(self):
        """每个测试前运行"""
        self.detector = SensitiveDataDetector()
    
    def test_detect_openai_key(self):
        """测试 OpenAI API key 检测"""
        text = "My key is sk-abc123..."
        findings = self.detector.detect(text)
        
        assert len(findings) == 1
        assert findings[0][0] == "openai_key"
    
    def test_redaction(self):
        """测试脱敏功能"""
        text = "API key: sk-abc123..."
        redacted = self.detector.redact(text)
        
        assert "sk-abc123" not in redacted
        assert "[REDACTED" in redacted
```

---

## 文档贡献

### 文档类型

| 类型 | 位置 | 何时更新 |
| :--- | :--- | :--- |
| **用户文档** | `docs/V5.1/Engineering/USER_MANUAL.md` | 添加新功能 |
| **开发文档** | `docs/V5.1/Engineering/DEVELOPER_GUIDE.md` | 架构变更 |
| **API 文档** | `docs/V5.1/6_API_SPEC.md` | API 变更 |
| **代码注释** | 源码中的 docstring | 始终 |

### 文档规范

```python
# ✅ 好的 docstring
def search(
    query: str,
    top_k: int = 10,
    filters: Optional[Dict] = None
) -> List[SearchResult]:
    """
    在记忆库中搜索。
    
    使用混合搜索（Vector + Graph）返回最相关的结果。
    
    Args:
        query: 搜索查询（支持自然语言）
        top_k: 返回结果数量，默认10
        filters: 可选过滤条件，例如 {"type": "bug"}
    
    Returns:
        按相关度排序的搜索结果列表
    
    Raises:
        ValueError: 如果 top_k < 1
        DatabaseError: 如果数据库连接失败
    
    Example:
        >>> results = dimcause.search("authentication bug", top_k=5)
        >>> print(results[0].summary)
        "Fixed auth.py permission bug"
    """
    pass
```

---

## 发布流程（Maintainers）

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/)：

```
MAJOR.MINOR.PATCH

5.1.0
│ │ │
│ │ └─ PATCH: Bug 修复
│ └─── MINOR: 新功能（向后兼容）
└───── MAJOR: 破坏性变更
```

### Release Checklist

```bash
# 1. 更新版本号
# - pyproject.toml
# - mal/__init__.py
# - docs/V5.1/README.md

# 2. 更新 CHANGELOG.md
# 添加新版本的更新内容

# 3. 运行全部测试
pytest
pytest tests/e2e

# 4. 构建文档
mkdocs build

# 5. 创建 Git Tag
git tag -a v5.1.0 -m "Release v5.1.0"
git push origin v5.1.0

# 6. 构建 Package
python -m build

# 7. 上传到 PyPI (Test 先)
twine upload --repository testpypi dist/*

# 8. 验证安装
pip install --index-url https://test.pypi.org/simple/ dimcause

# 9. 正式发布
twine upload dist/*

# 10. 创建 GitHub Release
# 附上 CHANGELOG + 二进制文件（如果有）
```

---

## 获取帮助

- **GitHub Issues**: https://github.com/JoeyOnMars/dimc/issues
- **Discussions**: https://github.com/JoeyOnMars/dimc/discussions
- **Email**: joey@dimcause.dev

---

## 致谢

感谢所有贡献者！你们让 DIMCAUSE 变得更好。

查看完整贡献者列表：https://github.com/JoeyOnMars/dimc/graphs/contributors

---

**Happy Contributing! 🚀**
