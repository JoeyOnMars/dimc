# DIMCAUSE V6.2 - 代码风格与导入规范 (Import Strategy)

> **版本**: 1.0
> **生效日期**: 2026-02-17
> **状态**: 强制执行 (Mandatory)

## 1. 核心原则：混合导入策略 (Hybrid Import Strategy)

为了兼顾**模块内的高内聚 (Cohesion)** 和 **跨子系统的解耦 (Decoupling)**，Dimcause 采用混合导入策略。

### 1.1 规则一：包内引用使用相对导入 (Intra-package Relative Imports)
**适用场景**: 同一个子包内的模块相互引用，或 `__init__.py` 暴露符号。
**理由**: 
- 允许子包重命名或移动而不破坏内部链接。
- 在 `__init__.py` 中最为常见，避免循环导入风险。

**✅ 正确示例 (`src/dimcause/core/__init__.py`)**:
```python
from .models import Event, Entity  # 引用同级模块
from .event_index import EventIndex
from .history import GitCommit
```

**❌ 错误示例**:
```python
from dimcause.core.models import Event  # 不要自指，导致包名硬编码依赖
```

### 1.2 规则二：跨子系统引用使用绝对导入 (Inter-package Absolute Imports)
**适用场景**: 一个子包引用另一个完全独立的子包（例如 `audit` 引用 `core`）。
**理由**: 
- 明确依赖关系。
- 避免 `../../../` 这种脆弱的爬楼梯式引用。

**✅ 正确示例 (`src/dimcause/audit/runner.py`)**:
```python
from dimcause.core.models import Event      # 明确引用 core
from dimcause.storage.graph_store import GraphStore
```

**❌ 错误示例**:
```python
from ..core.models import Event  # 脆弱，如果 runner.py 移动位置就会报错
```

### 1.3 规则三：第三方库优先 (Third-party First)
**顺序**: 标准库 -> 第三方库 -> 本地绝对导入 -> 本地相对导入

```python
import os
import json                  # 1. Stdlib

from pydantic import BaseModel # 2. Third-party

from dimcause.core.config import Config # 3. Local Absolute
from .checks import BaseCheck    # 4. Local Relative
```

## 2. 生产环境考量 (Production & Packaging)

此策略符合 Python Packaging Authority (PyPA) 最佳实践：
1.  **可测试性**: 绝对导入使得 Mocking 更容易 (`patch('dimcause.core.models.Event')`)。
2.  **发布友好**: 作为一个 library 发布到 PyPI 时，用户安装后 `import dimcause`，内部的相对导入确保了包的完整性。

## 3. 验证方法

在提交代码前，使用 `grep` 检查是否违反规则：

```bash
# 检查是否错误使用了过多的相对层级 (超过2层通常是坏味道)
grep -r "\.\.\/\.\." src/dimcause
```
