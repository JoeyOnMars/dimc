"""
Code Smell Detector - 代码反模式检测

使用 Python ast 模块精确检测代码反模式：
- bare_except: except: 捕获所有
- broad_catch: except Exception: 宽泛捕获
- swallowed_error: except 块吞没错误 (pass/return 无 raise)
- empty_function: 空函数体

参考 BCC architecture: 用自动化规则拦截代码反模式
"""

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CodeSmell:
    """代码气味发现记录"""

    rule_id: str  # bare_except, broad_catch, etc.
    severity: str  # P0, P1, P2
    file_path: str
    line_number: int
    message: str
    code_snippet: str


class SmellVisitor(ast.NodeVisitor):
    """AST 访问器，检测代码反模式"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.issues: List[CodeSmell] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # SMELL-001: bare_except -> except:
        if node.type is None:
            snippet = self._get_code_snippet(node)
            self.issues.append(
                CodeSmell(
                    rule_id="bare_except",
                    severity="P0",
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    message="捕获所有异常 (except:)，建议捕获具体异常类型",
                    code_snippet=snippet,
                )
            )

        # SMELL-002: broad_catch -> except Exception / BaseException
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            snippet = self._get_code_snippet(node)
            self.issues.append(
                CodeSmell(
                    rule_id="broad_catch",
                    severity="P1",
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    message="宽泛捕获 Exception/BaseException，建议捕获具体异常类型",
                    code_snippet=snippet,
                )
            )

        # SMELL-003: swallowed_error -> except 块只有 pass/return 但无 raise
        # 有 raise 的是正确处理（重新抛出），不算吞没
        if node.body and self._is_silent_body(node.body):
            has_raise = any(isinstance(b, ast.Raise) for b in node.body)
            if not has_raise:
                snippet = self._get_code_snippet(node)
                self.issues.append(
                    CodeSmell(
                        rule_id="swallowed_error",
                        severity="P0",
                        file_path=self.file_path,
                        line_number=node.lineno or 0,
                        message="异常被吞没 (pass/return 无 raise)，可能导致静默失败",
                        code_snippet=snippet,
                    )
                )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # SMELL-004: empty_function -> 只有 pass 或 ...
        if self._is_empty_body(node.body):
            snippet = self._get_code_snippet(node)
            self.issues.append(
                CodeSmell(
                    rule_id="empty_function",
                    severity="P2",
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    message="空函数体 (只有 pass 或 ...)",
                    code_snippet=snippet,
                )
            )

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # 异步函数同样检测
        if self._is_empty_body(node.body):
            snippet = self._get_code_snippet(node)
            self.issues.append(
                CodeSmell(
                    rule_id="empty_function",
                    severity="P2",
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    message="空异步函数体 (只有 pass 或 ...)",
                    code_snippet=snippet,
                )
            )

        self.generic_visit(node)

    def _is_silent_body(self, body: List[ast.stmt]) -> bool:
        """判断 except 块是否是静默吞没 (只有 pass/return，无 raise)"""
        if not body:
            return False
        return all(isinstance(b, (ast.Pass, ast.Return, ast.Raise)) for b in body)

    def _is_empty_body(self, body: List[ast.stmt]) -> bool:
        """判断函数体是否为空 (只有 pass 或 ...)"""
        if not body:
            return True
        return all(isinstance(b, (ast.Pass, ast.Expr)) for b in body)

    def _get_code_snippet(self, node: ast.AST) -> str:
        """获取代码片段"""
        # 使用 ast.unparse 获取代码表示 (Python 3.9+)
        try:
            return ast.unparse(node)
        except (TypeError, ValueError, AttributeError) as e:
            # ast.unparse 可能抛出的异常类型
            logging.warning(f"Failed to get code snippet: {e}")
            return ""


class CodeSmellDetector:
    """
    代码气味检测器

    使用 Python ast 模块遍历代码，检测反模式。
    零外部依赖，只支持 Python 代码。
    """

    # 规则定义
    RULES = {
        "bare_except": {
            "severity": "P0",
            "description": "捕获所有异常",
        },
        "broad_catch": {
            "severity": "P1",
            "description": "宽泛捕获 Exception/BaseException",
        },
        "swallowed_error": {
            "severity": "P0",
            "description": "异常被静默吞没",
        },
        "empty_function": {
            "severity": "P2",
            "description": "空函数体",
        },
    }

    def detect_file(self, file_path: Path) -> List[CodeSmell]:
        """
        检测单个文件的代码气味

        Args:
            file_path: Python 文件路径

        Returns:
            CodeSmell 列表
        """
        if file_path.suffix != ".py":
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            # 跳过语法错误的文件
            logging.warning(f"Syntax error in {file_path}, skipping")
            return []
        except OSError:
            # 跳过无法读取的文件
            logging.warning(f"Cannot read {file_path}, skipping")
            return []

        visitor = SmellVisitor(str(file_path))
        visitor.visit(tree)

        return visitor.issues

    def detect_directory(
        self, directory: Path, patterns: Optional[List[str]] = None
    ) -> List[CodeSmell]:
        """
        递归检测目录中所有 Python 文件的代码气味

        Args:
            directory: 目录路径
            patterns: 文件名模式列表，默认 ["*.py"]

        Returns:
            所有 CodeSmell 列表
        """
        if patterns is None:
            patterns = ["*.py"]

        all_issues = []

        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                if file_path.is_file() and ".git" not in str(file_path):
                    issues = self.detect_file(file_path)
                    all_issues.extend(issues)

        # 按严重级排序: P0 > P1 > P2
        severity_order = {"P0": 0, "P1": 1, "P2": 2}
        all_issues.sort(
            key=lambda x: (severity_order.get(x.severity, 3), x.file_path, x.line_number)
        )

        return all_issues


def detect_code_smells(path: str) -> List[CodeSmell]:
    """
    便捷函数：检测路径的代码气味

    Args:
        path: 文件或目录路径

    Returns:
        CodeSmell 列表
    """
    detector = CodeSmellDetector()
    target = Path(path)

    if target.is_file():
        return detector.detect_file(target)
    else:
        return detector.detect_directory(target)
