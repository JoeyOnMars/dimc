"""
Document Trace Check - 文档与代码因果覆盖率审计

核心功能：检验"这段代码为什么要改？有没有留档说明？"

根据 DEV_ONTOLOGY.md 公理 4.3:
- "每个 Function 的修改历史必须可回溯到至少一个 Decision"
- 验证规则: validate_function_traceability
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TracedSymbol:
    """可追溯的代码符号"""

    file_path: str
    symbol_name: str
    symbol_type: str  # "function" | "class" | "method"
    line_start: int
    line_end: int


@dataclass
class TraceIssue:
    """追踪问题"""

    symbol: TracedSymbol
    issue_type: str  # "untraced" | "orphan"
    message: str


class DocumentTraceChecker:
    """
    文档覆盖率审计器

    检验代码变更是否有对应的决策文档/Timeline记录
    """

    def __init__(self, event_index=None):
        self.event_index = event_index

    def get_git_changes(self, path: str = ".", since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取 Git 变更文件

        Args:
            path: 仓库路径
            since: 起始 commit 或日期 (e.g., "HEAD~10", "2026-01-01")

        Returns:
            List[{"file": str, "status": str, "lines": [int, ...]}]
        """
        changes = []

        try:
            # 获取变更文件列表
            cmd = ["git", "diff", "--name-status"]
            if since:
                cmd.append(f"{since}..HEAD")

            result = subprocess.run(cmd, cwd=path, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"git diff failed: {result.stderr}")
                return changes

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    status = parts[0]  # M, A, D
                    file_path = parts[1]

                    # 获取变更的行号
                    lines = self._get_changed_lines(path, file_path)

                    changes.append({"file": file_path, "status": status, "lines": lines})

        except Exception as e:
            logger.warning(f"Failed to get git changes: {e}")

        return changes

    def _get_changed_lines(self, repo_path: str, file_path: str) -> List[int]:
        """获取文件变更的行号"""
        lines = []

        try:
            result = subprocess.run(
                ["git", "diff", "--unified=0", "HEAD", "--", file_path],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("@@"):
                        # 解析 @@ -start,count +start,count @@
                        import re

                        match = re.search(r"\+(\d+)", line)
                        if match:
                            lines.append(int(match.group(1)))

        except Exception as e:
            logger.debug(f"Failed to get changed lines for {file_path}: {e}")

        return lines

    def check_untraced_code(
        self,
        path: str = ".",
        since: Optional[str] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> List[TraceIssue]:
        """
        检查未追踪的代码（幽灵代码）

        Args:
            path: 仓库路径
            since: 起始 commit
            ignore_patterns: 忽略的文件模式 (e.g., ["tests/", "*.test.py"])

        Returns:
            List[TraceIssue] - 未追踪的代码变更
        """
        if ignore_patterns is None:
            ignore_patterns = ["tests/", "test_", ".git/"]

        issues = []

        # 1. 获取 Git 变更
        changes = self.get_git_changes(path, since)

        # 2. 过滤忽略的文件
        filtered_changes = []
        for change in changes:
            file_path = change["file"]
            if any(pattern in file_path for pattern in ignore_patterns):
                continue
            filtered_changes.append(change)

        # 3. 对每个变更文件进行符号解析和验证
        from dimcause.extractors.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        for change in filtered_changes:
            file_path = change["file"]
            changed_lines = change["lines"]

            try:
                full_path = Path(path) / file_path
                if not full_path.exists():
                    continue

                code = full_path.read_text(encoding="utf-8")

                # 提取函数和类
                functions = analyzer.extract_functions(code, "python", file_path)
                classes = analyzer.extract_classes(code, "python", file_path)

                # 找到变更行所在的符号
                impacted_symbols = self._find_impacted_symbols(functions, classes, changed_lines)

                # 4. 检查每个符号是否有 Timeline 记录
                for symbol in impacted_symbols:
                    has_trace = self._check_symbol_trace(file_path, symbol)
                    if not has_trace:
                        issues.append(
                            TraceIssue(
                                symbol=symbol,
                                issue_type="untraced",
                                message=f"Function '{symbol.symbol_name}' modified but no Timeline/Decision found",
                            )
                        )

            except Exception as e:
                logger.debug(f"Failed to analyze {file_path}: {e}")

        return issues

    def _find_impacted_symbols(
        self,
        functions: List,
        classes: List,
        changed_lines: List[int],
    ) -> List[TracedSymbol]:
        """找到变更行所在的符号"""
        symbols = []

        all_symbols = []

        # 添加函数
        for func in functions:
            all_symbols.append(
                TracedSymbol(
                    file_path=func.file,
                    symbol_name=func.name,
                    symbol_type="function",
                    line_start=func.line_start,
                    line_end=func.line_end,
                )
            )

        # 添加类
        for cls in classes:
            all_symbols.append(
                TracedSymbol(
                    file_path=cls.file,
                    symbol_name=cls.name,
                    symbol_type="class",
                    line_start=cls.line_start,
                    line_end=cls.line_end,
                )
            )

        # 找到变更行在哪些符号范围内
        for symbol in all_symbols:
            for line in changed_lines:
                if symbol.line_start <= line <= symbol.line_end:
                    symbols.append(symbol)
                    break

        return symbols

    def _check_symbol_trace(self, file_path: str, symbol: TracedSymbol) -> bool:
        """
        检查符号是否有 Timeline/Decision 记录

        Returns:
            True if trace exists, False otherwise
        """
        if self.event_index is None:
            # 如果没有 EventIndex，尝试搜索 docs/ 目录
            return self._check_docs_for_trace(file_path, symbol.symbol_name)

        try:
            # 搜索相关的 Decision/Task 事件
            results = self.event_index.search(query=f"{symbol.symbol_name} {file_path}", limit=5)

            # 检查是否有相关事件
            for result in results:
                metadata = result.get("metadata", {})
                event_type = metadata.get("type", "")
                if event_type in ("decision", "task", "requirement"):
                    return True

        except Exception as e:
            logger.debug(f"Failed to check trace for {symbol.symbol_name}: {e}")

        return False

    def _check_docs_for_trace(self, file_path: str, symbol_name: str) -> bool:
        """在文档目录中搜索追踪记录"""
        docs_path = Path("docs")

        if not docs_path.exists():
            return False

        # 搜索相关文档
        search_terms = [symbol_name, file_path.replace("/", "_")]

        for term in search_terms:
            matches = list(docs_path.rglob(f"*{term}*"))
            if matches:
                return True

        return False

    def get_trace_coverage_report(self, issues: List[TraceIssue]) -> Dict[str, Any]:
        """生成追踪覆盖率报告"""
        total_symbols = len({i.symbol.symbol_name for i in issues})

        return {
            "total_issues": len(issues),
            "untraced_symbols": total_symbols,
            "coverage": f"{max(0, 100 - total_symbols * 10)}%",  # 简化计算
            "issues": [
                {
                    "file": i.symbol.file_path,
                    "symbol": i.symbol.symbol_name,
                    "type": i.symbol.symbol_type,
                    "message": i.message,
                }
                for i in issues
            ],
        }


# 便捷函数
def create_trace_checker(event_index=None) -> DocumentTraceChecker:
    """创建文档追踪检查器"""
    return DocumentTraceChecker(event_index)
