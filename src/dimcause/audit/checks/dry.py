"""
DRY 违规检测：检测同名函数在多个模块中的重复定义。

典型问题场景：get_root_dir() 在 cli.py、state.py、stats.py 中各定义一份，
实现不一致导致安装后行为异常。
"""

import ast
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

from dimcause.audit.engine import BaseCheck, CheckResult

logger = logging.getLogger(__name__)

# 不检测这些常见的"允许重复"函数名
ALLOWED_DUPLICATES: Set[str] = {
    "__init__",
    "__repr__",
    "__str__",
    "__eq__",
    "__hash__",
    "__len__",
    "__iter__",
    "__enter__",
    "__exit__",
    "__post_init__",
    "run",
    "main",
    "setup",
    "teardown",
    "setUp",
    "tearDown",
}


class DuplicateDefinitionCheck(BaseCheck):
    """检测同名顶层函数在多个模块中的重复定义。"""

    name = "dry_violation"
    description = "检测同名函数的多模块重复定义 (DRY 违规)"

    def run(self, files: List[Path]) -> CheckResult:
        # 收集所有 .py 文件
        py_files: List[Path] = []
        for f in files:
            if f.is_dir():
                py_files.extend(f.rglob("*.py"))
            elif f.is_file() and f.suffix == ".py":
                py_files.append(f)

        # 排除测试文件、__pycache__、.venv 等非项目目录
        EXCLUDED_DIRS = {
            "__pycache__",
            ".venv",
            "venv",
            ".env",
            "env",
            "node_modules",
            ".git",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "build",
            "dist",
            "site-packages",
        }
        py_files = [
            f
            for f in py_files
            if not any(excl in f.parts for excl in EXCLUDED_DIRS) and not f.name.startswith("test_")
        ]

        # 函数名 -> [(文件路径, 行号)]
        func_locations: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        for py_file in py_files:
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.debug(f"跳过无法解析的文件 {py_file}: {e}")
                continue

            for node in ast.iter_child_nodes(tree):
                # 只检测模块顶层的函数定义（非类方法）
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    func_name = node.name
                    if func_name not in ALLOWED_DUPLICATES and not func_name.startswith("_test"):
                        func_locations[func_name].append((str(py_file), node.lineno))

        # 找出在 2+ 个不同文件中定义的同名函数
        violations: List[str] = []
        for func_name, locations in sorted(func_locations.items()):
            # 按文件去重（同一文件内的重载不算）
            unique_files = {loc[0] for loc in locations}
            if len(unique_files) >= 2:
                loc_strs = [f"  - {path}:{line}" for path, line in locations]
                violations.append(
                    f"'{func_name}()' 在 {len(unique_files)} 个模块中重复定义:\n"
                    + "\n".join(loc_strs)
                )

        if violations:
            return CheckResult(
                check_name=self.name,
                success=False,
                message=f"发现 {len(violations)} 个 DRY 违规（同名函数多模块定义）",
                details=violations,
                is_blocking=False,  # 警告级别，不阻塞
            )

        return CheckResult(
            check_name=self.name,
            success=True,
            message="未发现 DRY 违规",
        )
