"""
AST Analyzer - 代码结构分析

使用 tree-sitter 进行轻量级代码解析
Dimcause 的核心差异化：代码级深度
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dimcause.core.models import CodeEntity, CodeEntityType

logger = logging.getLogger(__name__)


class ASTAnalyzer:
    """
    AST 分析器

    实现 IASTAnalyzer 接口
    支持语言: Python, JavaScript/TypeScript
    """

    # 支持的语言
    SUPPORTED_LANGUAGES = ["python", "javascript", "typescript"]

    def __init__(self):
        self._tree_sitter_available = False
        self._parsers: Dict[str, Any] = {}
        self._setup()

    def _setup(self) -> None:
        """初始化 tree-sitter"""
        try:
            import tree_sitter_javascript
            import tree_sitter_python
            import tree_sitter_typescript
            from tree_sitter import Language, Parser

            # 创建解析器
            self._parsers["python"] = Parser(Language(tree_sitter_python.language()))
            self._parsers["javascript"] = Parser(Language(tree_sitter_javascript.language()))
            # TypeScript 使用独立的解析器（不再是 JavaScript 复用）
            self._parsers["typescript"] = Parser(
                Language(tree_sitter_typescript.language_typescript())
            )

            self._tree_sitter_available = True
        except ImportError:
            logger.warning(
                "tree-sitter 未安装，AST 解析将降级为正则表达式。"
                "多行函数签名和复杂类型注解可能提取失败。"
                "如需完整功能，运行: pip install 'dimcause[ast]'"
            )
            self._tree_sitter_available = False

    def supported_languages(self) -> List[str]:
        """返回支持的语言列表"""
        return self.SUPPORTED_LANGUAGES

    def extract_functions(
        self, code: str, language: str, file: str = "unknown"
    ) -> List[CodeEntity]:
        """提取函数定义"""
        if language not in self.SUPPORTED_LANGUAGES:
            return []

        if self._tree_sitter_available and language in self._parsers:
            return self._extract_functions_treesitter(code, language, file)
        else:
            return self._extract_functions_regex(code, language, file)

    def extract_classes(self, code: str, language: str, file: str = "unknown") -> List[CodeEntity]:
        """提取类定义"""
        if language not in self.SUPPORTED_LANGUAGES:
            return []

        if self._tree_sitter_available and language in self._parsers:
            return self._extract_classes_treesitter(code, language, file)
        else:
            return self._extract_classes_regex(code, language, file)

    def extract_imports(self, code: str, language: str) -> List[tuple[str, int]]:
        """提取导入语句，返回 (模块名, 行号) 列表"""
        if language == "python":
            return self._extract_imports_python(code)
        elif language in ["javascript", "typescript"]:
            return self._extract_imports_js(code)
        return []

    # =========================================================================
    # Tree-sitter 实现
    # =========================================================================

    def _extract_functions_treesitter(
        self, code: str, language: str, file: str
    ) -> List[CodeEntity]:
        """使用 tree-sitter 提取函数"""
        entities = []
        parser = self._parsers.get(language)
        if not parser:
            return entities

        tree = parser.parse(bytes(code, "utf-8"))
        root = tree.root_node

        # 遍历 AST 查找函数定义
        for node in self._walk_tree(root):
            if node.type in ["function_definition", "function_declaration", "method_definition"]:
                # 获取函数名
                name_node = node.child_by_field_name("name")
                if name_node:
                    raw_name = code[name_node.start_byte : name_node.end_byte]
                    method_owner = self._get_enclosing_class_name(node, code)
                    is_method = node.type == "method_definition" or method_owner is not None
                    name = f"{method_owner}.{raw_name}" if method_owner else raw_name

                    # 获取签名（参数列表）
                    params_node = node.child_by_field_name("parameters")
                    signature = None
                    if params_node:
                        params = code[params_node.start_byte : params_node.end_byte]
                        if language == "python":
                            signature = f"def {raw_name}{params}"
                        else:
                            signature = f"function {raw_name}{params}"

                    # 获取文档字符串（Python）
                    docstring = None
                    if language == "python":
                        docstring = self._extract_docstring(node, code)

                    entities.append(
                        CodeEntity(
                            name=name,
                            type=CodeEntityType.METHOD if is_method else CodeEntityType.FUNCTION,
                            file=file,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            signature=signature,
                            docstring=docstring,
                            language=language,
                        )
                    )

        return entities

    def _extract_classes_treesitter(self, code: str, language: str, file: str) -> List[CodeEntity]:
        """使用 tree-sitter 提取类"""
        entities = []
        parser = self._parsers.get(language)
        if not parser:
            return entities

        tree = parser.parse(bytes(code, "utf-8"))
        root = tree.root_node

        for node in self._walk_tree(root):
            if node.type in ["class_definition", "class_declaration"]:
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = code[name_node.start_byte : name_node.end_byte]

                    # Python 类签名
                    signature = None
                    if language == "python":
                        # 检查是否有基类
                        superclass = node.child_by_field_name("superclasses")
                        if superclass:
                            bases = code[superclass.start_byte : superclass.end_byte]
                            signature = f"class {name}{bases}"
                        else:
                            signature = f"class {name}"

                    entities.append(
                        CodeEntity(
                            name=name,
                            type=CodeEntityType.CLASS,
                            file=file,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            signature=signature,
                            language=language,
                        )
                    )

        return entities

    def _walk_tree(self, node):
        """遍历 AST"""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _get_enclosing_class_name(self, node, code: str) -> Optional[str]:
        """获取节点所在的类名，支持嵌套类时返回限定名。"""
        names: List[str] = []
        current = getattr(node, "parent", None)
        while current is not None:
            if current.type in {"class_definition", "class_declaration"}:
                name_node = current.child_by_field_name("name")
                if name_node is not None:
                    names.append(code[name_node.start_byte : name_node.end_byte])
            current = getattr(current, "parent", None)

        if not names:
            return None
        return ".".join(reversed(names))

    def _extract_docstring(self, func_node, code: str) -> Optional[str]:
        """提取 Python 函数的 docstring"""
        # 查找函数体
        body = func_node.child_by_field_name("body")
        if not body or not body.children:
            return None

        # 第一个语句
        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement":
            # 检查是否是字符串
            if first_stmt.children and first_stmt.children[0].type == "string":
                docstring = code[
                    first_stmt.children[0].start_byte : first_stmt.children[0].end_byte
                ]
                # 去掉引号
                return docstring.strip('"').strip("'").strip()

        return None

    # =========================================================================
    # Regex 降级实现
    # =========================================================================

    def _extract_functions_regex(self, code: str, language: str, file: str) -> List[CodeEntity]:
        """使用 Regex 提取函数（降级方案）"""
        entities = []
        lines = code.split("\n")

        if language == "python":
            pattern = r"^\s*def\s+(\w+)\s*\((.*?)\)\s*(?:->.*?)?:"
            class_pattern = r"^(\s*)class\s+(\w+)\s*(?:\(.*?\))?:"
            class_stack: List[tuple[int, str]] = []
        else:  # JavaScript/TypeScript
            pattern = r"(?:function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*:\s*(?:async\s*)?\()"

        for i, line in enumerate(lines):
            if language == "python":
                class_match = re.match(class_pattern, line)
                if class_match:
                    indent = len(class_match.group(1))
                    while class_stack and class_stack[-1][0] >= indent:
                        class_stack.pop()
                    class_stack.append((indent, class_match.group(2)))
                    continue

                stripped = line.strip()
                if stripped:
                    indent = len(line) - len(line.lstrip(" "))
                    while class_stack and indent <= class_stack[-1][0]:
                        class_stack.pop()

            match = re.match(pattern, line)
            if match:
                # 获取函数名
                name = match.group(1) or (match.group(2) if language != "python" else None)
                if name:
                    entity_type = CodeEntityType.FUNCTION
                    entity_name = name
                    if language == "python":
                        indent = len(line) - len(line.lstrip(" "))
                        if class_stack and indent > class_stack[-1][0]:
                            entity_type = CodeEntityType.METHOD
                            entity_name = f"{class_stack[-1][1]}.{name}"
                    entities.append(
                        CodeEntity(
                            name=entity_name,
                            type=entity_type,
                            file=file,
                            line_start=i + 1,
                            line_end=i + 1,  # Regex 无法确定结束行
                            signature=line.strip(),
                            language=language,
                        )
                    )

        return entities

    def _extract_classes_regex(self, code: str, language: str, file: str) -> List[CodeEntity]:
        """使用 Regex 提取类（降级方案）"""
        entities = []
        lines = code.split("\n")

        if language == "python":
            pattern = r"^\s*class\s+(\w+)\s*(?:\(.*?\))?:"
        else:
            pattern = r"^\s*class\s+(\w+)\s*(?:extends\s+\w+)?\s*{"

        for i, line in enumerate(lines):
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                entities.append(
                    CodeEntity(
                        name=name,
                        type=CodeEntityType.CLASS,
                        file=file,
                        line_start=i + 1,
                        line_end=i + 1,
                        signature=line.strip(),
                        language=language,
                    )
                )

        return entities

    def _extract_imports_python(self, code: str) -> List[tuple[str, int]]:
        """提取 Python 导入 (模块, 行号)"""
        imports = []

        # import xxx
        for match in re.finditer(r"^\s*import\s+(\S+)", code, re.MULTILINE):
            line_no = code[: match.start()].count("\n") + 1
            imports.append((match.group(1), line_no))

        # from xxx import yyy
        for match in re.finditer(r"^\s*from\s+(\S+)\s+import", code, re.MULTILINE):
            line_no = code[: match.start()].count("\n") + 1
            imports.append((match.group(1), line_no))

        return list(set(imports))

    def _extract_imports_js(self, code: str) -> List[tuple[str, int]]:
        """提取 JavaScript/TypeScript 导入 (模块, 行号)"""
        imports = []

        # import ... from 'xxx'
        for match in re.finditer(r"(?:import|from)\s+['\"]([^'\"]+)['\"]", code):
            line_no = code[: match.start()].count("\n") + 1
            imports.append((match.group(1), line_no))

        # require('xxx')
        for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
            line_no = code[: match.start()].count("\n") + 1
            imports.append((match.group(1), line_no))

        return list(set(imports))

    def extract_calls(self, code: str, language: str) -> List[tuple[str, int, str]]:
        """
        提取函数/方法调用

        Returns:
            List[(被调用的函数/方法名, 行号, 调用类型)]
            调用类型: "function_call" | "method_call" | "class_call"
        """
        if language == "python":
            return self._extract_calls_python(code)
        elif language in ["javascript", "typescript"]:
            return self._extract_calls_js(code)
        return []

    def _extract_calls_python(self, code: str) -> List[tuple[str, int, str]]:
        """提取 Python 函数调用"""
        calls = []

        if not self._tree_sitter_available:
            # 降级：使用正则
            pattern = r"(?<!def\s)(?<!class\s)\b(\w+)\s*\("
            for match in re.finditer(pattern, code):
                line_no = code[: match.start()].count("\n") + 1
                name = match.group(1)
                # 排除关键字
                if name not in (
                    "if",
                    "for",
                    "while",
                    "with",
                    "return",
                    "assert",
                    "raise",
                    "yield",
                    "print",
                    "open",
                    "len",
                    "str",
                    "int",
                    "float",
                    "list",
                    "dict",
                    "set",
                    "tuple",
                    "range",
                    "enumerate",
                    "zip",
                    "map",
                    "filter",
                    "sum",
                    "min",
                    "max",
                    "abs",
                    "round",
                    "isinstance",
                    "hasattr",
                    "getattr",
                    "setattr",
                    "type",
                    "callable",
                    "iter",
                    "next",
                    "super",
                ):
                    calls.append((name, line_no, "function_call"))
            return calls

        # Tree-sitter 实现
        parser = self._parsers.get("python")
        if not parser:
            return []

        try:
            tree = parser.parse(bytes(code, "utf8"))
            root = tree.root_node

            for node in self._walk_tree(root):
                # 查找函数调用 (call)
                if node.type == "call":
                    # 获取函数名
                    func = node.child_by_field_name("function")
                    if func:
                        if func.type == "identifier":
                            name = code[func.start_byte : func.end_byte]
                            line_no = func.start_point[0] + 1
                            calls.append((name, line_no, "function_call"))
                        elif func.type == "attribute":
                            # 方法调用 obj.method()
                            attr = func.child_by_field_name("attribute")
                            if attr:
                                name = code[attr.start_byte : attr.end_byte]
                                line_no = attr.start_point[0] + 1
                                calls.append((name, line_no, "method_call"))

        except Exception as e:
            logger.warning(f"Failed to extract calls with tree-sitter: {e}")

        return calls

    def _extract_calls_js(self, code: str) -> List[tuple[str, int, str]]:
        """提取 JavaScript/TypeScript 函数调用"""
        calls = []

        if not self._tree_sitter_available:
            # 降级：使用正则
            pattern = r"\b(\w+)\s*\("
            for match in re.finditer(pattern, code):
                line_no = code[: match.start()].count("\n") + 1
                name = match.group(1)
                if name not in (
                    "if",
                    "for",
                    "while",
                    "return",
                    "throw",
                    "console",
                    "require",
                    "module",
                    "exports",
                    "JSON",
                    "Object",
                    "Array",
                    "String",
                    "Number",
                    "Boolean",
                    "Math",
                    "Date",
                    "Promise",
                    "setTimeout",
                    "setInterval",
                ):
                    calls.append((name, line_no, "function_call"))
            return calls

        parser = self._parsers.get("javascript")
        if not parser:
            return []

        try:
            tree = parser.parse(bytes(code, "utf8"))
            root = tree.root_node

            for node in self._walk_tree(root):
                if node.type == "call_expression":
                    func = node.child_by_field_name("function")
                    if func:
                        if func.type == "identifier":
                            name = code[func.start_byte : func.end_byte]
                            line_no = func.start_point[0] + 1
                            calls.append((name, line_no, "function_call"))
                        elif func.type == "member_expression":
                            # obj.method()
                            prop = func.child_by_field_name("property")
                            if prop:
                                name = code[prop.start_byte : prop.end_byte]
                                line_no = prop.start_point[0] + 1
                                calls.append((name, line_no, "method_call"))

        except Exception as e:
            logger.warning(f"Failed to extract JS calls with tree-sitter: {e}")

        return calls

    def extract_control_flow(self, code: str, language: str) -> List[dict]:
        """
        提取控制流结构

        Returns:
            List[{
                "type": "if" | "for" | "while" | "try" | "with",
                "line": int,
                "condition": str,  # 条件表达式（可选）
                "body_lines": (start, end),  # 循环体行号范围
            }]
        """
        if language == "python":
            return self._extract_control_flow_python(code)
        elif language in ["javascript", "typescript"]:
            return self._extract_control_flow_js(code)
        return []

    def _extract_control_flow_python(self, code: str) -> List[dict]:
        """提取 Python 控制流"""
        results = []

        if not self._tree_sitter_available:
            return results

        parser = self._parsers.get("python")
        if not parser:
            return results

        try:
            tree = parser.parse(bytes(code, "utf8"))
            root = tree.root_node

            for node in self._walk_tree(root):
                cf_type = None
                if node.type == "if_statement":
                    cf_type = "if"
                elif node.type in ("for_statement", "for_in_statement"):
                    cf_type = "for"
                elif node.type == "while_statement":
                    cf_type = "while"
                elif node.type == "try_statement":
                    cf_type = "try"
                elif node.type == "with_statement":
                    cf_type = "with"

                if cf_type:
                    result = {
                        "type": cf_type,
                        "line": node.start_point[0] + 1,
                    }

                    # 提取条件表达式
                    if cf_type in ("if", "while", "for"):
                        condition = node.child_by_field_name("condition")
                        if condition:
                            result["condition"] = code[condition.start_byte : condition.end_byte]

                    # 循环体/try 块行号范围
                    if cf_type in ("for", "while", "try", "with"):
                        body = node.child_by_field_name("body")
                        if body:
                            result["body_lines"] = (body.start_point[0] + 1, body.end_point[0] + 1)

                    results.append(result)

        except Exception as e:
            logger.warning(f"Failed to extract control flow: {e}")

        return results

    def _extract_control_flow_js(self, code: str) -> List[dict]:
        """提取 JavaScript/TypeScript 控制流"""
        results = []

        if not self._tree_sitter_available:
            return results

        parser = self._parsers.get("javascript")
        if not parser:
            return results

        try:
            tree = parser.parse(bytes(code, "utf8"))
            root = tree.root_node

            for node in self._walk_tree(root):
                cf_type = None
                if node.type == "if_statement":
                    cf_type = "if"
                elif node.type == "for_statement":
                    cf_type = "for"
                elif node.type == "while_statement":
                    cf_type = "while"
                elif node.type == "try_statement":
                    cf_type = "try"
                elif node.type == "with_statement":
                    cf_type = "with"

                if cf_type:
                    result = {
                        "type": cf_type,
                        "line": node.start_point[0] + 1,
                    }

                    # 提取条件表达式
                    if cf_type in ("if", "while", "for"):
                        condition = node.child_by_field_name("condition")
                        if condition:
                            result["condition"] = code[condition.start_byte : condition.end_byte]

                    # 循环体行号范围
                    if cf_type in ("for", "while", "try", "with"):
                        body = node.child_by_field_name("body")
                        if body:
                            result["body_lines"] = (body.start_point[0] + 1, body.end_point[0] + 1)

                    results.append(result)

        except Exception as e:
            logger.warning(f"Failed to extract JS control flow: {e}")

        return results


# 便捷函数
def create_ast_analyzer() -> ASTAnalyzer:
    """创建 AST 分析器实例"""
    return ASTAnalyzer()


def detect_language(file_path: str) -> str:
    """根据文件扩展名检测语言"""
    ext = Path(file_path).suffix.lower()
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }
    return lang_map.get(ext, "unknown")


def build_code_dependency_graph(
    file_path: str,
    code: str,
    language: str,
    graph_store=None,
) -> dict:
    """
    构建单个文件的代码依赖图并可选地存储到 GraphStore

    Args:
        file_path: 文件路径
        code: 文件内容
        language: 编程语言
        graph_store: 可选的 GraphStore 实例

    Returns:
        {
            "functions": [...],
            "classes": [...],
            "imports": [...],
            "calls": [...],
            "dependencies": [(source, target, type), ...]
        }
    """
    analyzer = ASTAnalyzer()

    # 提取各类信息
    functions = analyzer.extract_functions(code, language, file_path)
    classes = analyzer.extract_classes(code, language, file_path)
    imports = analyzer.extract_imports(code, language)
    calls = analyzer.extract_calls(code, language)

    dependencies = []

    # 添加文件级节点
    if graph_store:
        graph_store.add_entity(file_path, "file", language=language)

    # 提取的函数和类作为节点
    all_entities = functions + classes

    for entity in all_entities:
        node_id = f"{file_path}:{entity.name}"
        if graph_store:
            graph_store.add_entity(
                node_id,
                entity.type.value if hasattr(entity.type, "value") else str(entity.type),
                line_start=entity.line_start,
                line_end=entity.line_end,
            )

    # 构建调用关系：跟踪当前所在函数/方法
    func_ranges = {}
    for func in functions:
        func_ranges[func.name] = (func.line_start, func.line_end)
    known_entities = set(func_ranges.keys())

    # 添加调用关系
    for func_name, line_no, _call_type in calls:
        # 查找调用点所在的函数
        caller = None
        for fname, (start, end) in func_ranges.items():
            if start <= line_no <= end:
                caller = fname
                break

        if caller:
            source = f"{file_path}:{caller}"
            target_name = func_name
            if _call_type == "method_call" and "." in caller:
                caller_owner = caller.rsplit(".", 1)[0]
                qualified_target = f"{caller_owner}.{func_name}"
                if qualified_target in known_entities:
                    target_name = qualified_target
            if target_name not in known_entities and func_name in known_entities:
                target_name = func_name

            target = f"{file_path}:{target_name}"
            dependencies.append((source, target, "calls"))
            if graph_store:
                graph_store.add_structural_relation(source, target, "calls")

    # 添加导入关系
    for import_name, _import_line in imports:
        source = file_path
        target = import_name
        dependencies.append((source, target, "imports"))
        if graph_store:
            graph_store.add_structural_relation(source, target, "imports")

    return {
        "functions": [e.name for e in functions],
        "classes": [e.name for e in classes],
        "imports": imports,
        "calls": calls,
        "dependencies": dependencies,
    }
