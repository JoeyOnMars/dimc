"""
Code Indexer - AST & Dependency Indexing (Phase 3)

This module handles indexing source code to support `dimc trace`.
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from dimcause.extractors.ast_analyzer import ASTAnalyzer, detect_language
from dimcause.utils.config import get_config

logger = logging.getLogger(__name__)


class CodeIndexer:
    """
    代码索引器

    负责维护代码的 AST 和依赖索引 (SQLite)
    """

    def __init__(self, db_path: Optional[Path] = None, project_root: Optional[Path] = None):
        self.config = get_config()
        self.db_path = db_path or self.config.index_db
        self.project_root = project_root or self.config.root_dir
        self.analyzer = ASTAnalyzer()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # Code Files
            conn.execute("""
                CREATE TABLE IF NOT EXISTS code_files (
                    path TEXT PRIMARY KEY,
                    mtime REAL,
                    language TEXT,
                    calls_indexed INTEGER DEFAULT 0
                )
            """)

            # Code Entities (Functions, Classes)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS code_entities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    file_path TEXT,
                    line_start INTEGER,
                    line_end INTEGER,
                    signature TEXT,
                    docstring TEXT,
                    FOREIGN KEY(file_path) REFERENCES code_files(path)
                )
            """)

            # Imports / Dependencies
            conn.execute("""
                CREATE TABLE IF NOT EXISTS code_imports (
                    source_file TEXT,
                    module_name TEXT,
                    line_number INTEGER,
                    FOREIGN KEY(source_file) REFERENCES code_files(path)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS code_calls (
                    source_file TEXT,
                    source_entity TEXT,
                    target_name TEXT,
                    line_number INTEGER,
                    call_type TEXT,
                    FOREIGN KEY(source_file) REFERENCES code_files(path)
                )
            """)

            # Create Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON code_entities(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_file ON code_entities(file_path)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_import_source ON code_imports(source_file)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_import_module ON code_imports(module_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_code_calls_target ON code_calls(target_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_code_calls_source ON code_calls(source_file)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_code_calls_source_entity ON code_calls(source_entity)"
            )

    def _load_cached_files(self, conn: sqlite3.Connection) -> Dict[str, tuple[float, int]]:
        try:
            cursor = conn.execute("SELECT path, mtime, calls_indexed FROM code_files")
            return {row[0]: (row[1], row[2]) for row in cursor}
        except sqlite3.OperationalError:
            return {}

    def index_all(self) -> int:
        """扫描并索引所有代码文件"""
        logger.info(f"Indexing code in {self.project_root}...")

        # Exclude directories
        exclude_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            ".agent",
            "docs",
            "dist",
            "build",
            "site-packages",
        }

        count = 0
        with sqlite3.connect(self.db_path) as conn:
            # Get existing cache to skip unchanged files
            cached = self._load_cached_files(conn)

            for root, dirs, files in os.walk(self.project_root):
                # Filter dirs in-place to avoid recursion
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                for file in files:
                    file_path = Path(root) / file

                    # Detect language
                    language = detect_language(str(file_path))
                    if language == "unknown":
                        continue

                    try:
                        rel_path = str(file_path.relative_to(self.project_root))
                    except ValueError:
                        continue

                    # Check mtime
                    try:
                        mtime = file_path.stat().st_mtime
                    except OSError:
                        continue

                    cached_entry = cached.get(rel_path)
                    if cached_entry and cached_entry[0] >= mtime and cached_entry[1]:
                        continue

                    # Index the file
                    # Index the file
                    # Modified to match new _index_file signature which only takes (conn, abs_path)
                    self._index_file(conn, file_path)
                    count += 1

            conn.commit()

        logger.info(f"Indexed {count} code files.")
        return count

    def index_file(self, file_path: str) -> bool:
        """
        Public API: 索引单个文件

        Args:
            file_path: 文件路径 (str or Path)

        Returns:
            bool: 是否成功
        """
        try:
            path_obj = Path(file_path)
            if not path_obj.exists():
                return False

            with sqlite3.connect(self.db_path) as conn:
                # Derive rel_path, language, mtime inside _index_file
                self._index_file(conn, path_obj)
                return True
        except Exception as e:
            logger.error(f"Failed to index file {file_path}: {e}")
            return False

    def _index_file(self, conn: sqlite3.Connection, abs_path: Path):
        """索引单个文件"""
        try:
            try:
                rel_path = str(abs_path.relative_to(self.project_root))
            except ValueError:
                # File is outside project root (e.g. during tests)
                rel_path = str(abs_path)

            language = detect_language(str(abs_path))
            mtime = abs_path.stat().st_mtime
            code = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Skipping binary or encoding error: {abs_path}")
            return
        except Exception as e:
            print(f"Error reading {abs_path}: {e}")
            return

        # Update file info
        conn.execute(
            """
            INSERT OR REPLACE INTO code_files (path, mtime, language, calls_indexed)
            VALUES (?, ?, ?, 0)
            """,
            (rel_path, mtime, language),
        )

        # Clear old entities and imports for this file
        conn.execute("DELETE FROM code_entities WHERE file_path = ?", (rel_path,))
        conn.execute("DELETE FROM code_imports WHERE source_file = ?", (rel_path,))
        conn.execute("DELETE FROM code_calls WHERE source_file = ?", (rel_path,))

        # Extract and store entities
        try:
            functions = self.analyzer.extract_functions(code, language, rel_path)
            classes = self.analyzer.extract_classes(code, language, rel_path)

            for entity in functions + classes:
                # ID format: file_path:name (Not perfect for overloading or nested classes, but simple)
                # Maybe suffix with line number if needed?
                entity_id = f"{rel_path}:{entity.name}"

                # Check if ID exists to avoid constraint error (e.g. multiple funcs with same name in same file? unlikely in Python, possible in JS)
                # We'll just overwrite or append signature

                conn.execute(
                    """
                    INSERT OR REPLACE INTO code_entities
                    (id, name, type, file_path, line_start, line_end, signature, docstring)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entity_id,
                        entity.name,
                        getattr(entity.type, "value", str(entity.type)),
                        rel_path,
                        entity.line_start,
                        entity.line_end,
                        entity.signature,
                        entity.docstring,
                    ),
                )
        except Exception as e:
            print(f"Error analyzing entities in {rel_path}: {e}")

        # Extract and store imports
        try:
            imports = self.analyzer.extract_imports(code, language)
            for imp_name, line_no in imports:
                conn.execute(
                    "INSERT INTO code_imports (source_file, module_name, line_number) VALUES (?, ?, ?)",
                    (rel_path, imp_name, line_no),
                )
        except Exception as e:
            print(f"Error analyzing imports in {rel_path}: {e}")

        # Extract and store call sites
        try:
            call_ranges = {
                entity.name: (entity.line_start, entity.line_end or entity.line_start)
                for entity in functions
            }
            known_entities = set(call_ranges.keys())
            calls = self.analyzer.extract_calls(code, language)
            for called_name, line_no, call_type in calls:
                caller = None
                for entity_name, (start, end) in call_ranges.items():
                    if start <= line_no <= end:
                        caller = entity_name
                        break
                if caller is None:
                    continue

                target_name = called_name
                if call_type == "method_call" and "." in caller:
                    caller_owner = caller.rsplit(".", 1)[0]
                    qualified_target = f"{caller_owner}.{called_name}"
                    if qualified_target in known_entities:
                        target_name = qualified_target
                elif called_name in known_entities:
                    target_name = called_name

                conn.execute(
                    """
                    INSERT INTO code_calls (source_file, source_entity, target_name, line_number, call_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (rel_path, caller, target_name, line_no, call_type),
                )

            conn.execute(
                "UPDATE code_files SET calls_indexed = 1 WHERE path = ?",
                (rel_path,),
            )
        except Exception as e:
            print(f"Error analyzing calls in {rel_path}: {e}")

    def find_symbol(self, query: str) -> list:
        """
        Public API: 查找符号 (Alias for trace_symbol for test compatibility)
        """
        try:
            # trace_symbol returns dict, tests expect list?
            # Let's check trace_symbol return. It returns dict with definitions/references.
            # Tests behave like it returns a list of specific matches.
            # Adaptation: return definitions list
            result = self.trace_symbol(query)
            return result.get("definitions", [])
        except Exception:
            return []

    def trace_symbol(self, query: str) -> Dict[str, List[Any]]:
        """
        追踪符号: 查找定义和引用

        Returns:
            {
                "definitions": [...],
                "references": [...]
            }
        """
        results = {"definitions": [], "references": []}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 1. 查找定义 (按名字或 ID)
            # LIKE 用于模糊搜索
            cursor = conn.execute(
                "SELECT * FROM code_entities WHERE name = ? OR id = ? OR name LIKE ?",
                (query, query, f"%{query}%"),
            )
            for row in cursor:
                results["definitions"].append(dict(row))

            if not results["definitions"]:
                # 如果找不到定义，可能 query 就是一个文件或模块名
                # 尝试查找包含该 query 的文件名
                cursor = conn.execute(
                    "SELECT path, language FROM code_files WHERE path LIKE ?", (f"%{query}%",)
                )
                for row in cursor:
                    results["definitions"].append(
                        {
                            "name": Path(row["path"]).name,
                            "type": "file",
                            "file_path": row["path"],
                            "signature": f"File ({row['language']})",
                        }
                    )

            # 2. 查找引用 (Who imports the defining file)
            # 启发式：如果找到定义在 auth.py，则查找所有 import auth 的文件

            target_modules = set()

            # 收集所有定义的所在文件，作为目标模块
            for definition in results["definitions"]:
                if "file_path" in definition:
                    file_path = definition["file_path"]
                    target_modules.update(self._generated_module_names(file_path))

            # 如果 query 本身看起来像模块名，也加入
            if not results["definitions"]:
                target_modules.add(query)

            if target_modules:
                placeholders = ",".join("?" for _ in target_modules)
                cursor = conn.execute(
                    f"""
                    SELECT
                        ci.source_file,
                        ci.module_name,
                        ci.line_number,
                        cf.language
                    FROM code_imports ci
                    JOIN code_files cf ON ci.source_file = cf.path
                    WHERE ci.module_name IN ({placeholders})
                    """,
                    list(target_modules),
                )
                for row in cursor:
                    reference = dict(row)
                    reference["reference_type"] = "import"
                    reference["target_name"] = reference.get("module_name")
                    results["references"].append(reference)

            target_names = {query}
            for definition in results["definitions"]:
                name = definition.get("name")
                if name:
                    target_names.add(name)

            call_matchers = set(target_names)
            for target_name in list(target_names):
                if "." in target_name:
                    call_matchers.add(target_name.rsplit(".", 1)[-1])

            if call_matchers:
                placeholders = ",".join("?" for _ in call_matchers)
                cursor = conn.execute(
                    f"""
                    SELECT
                        source_file,
                        source_entity,
                        target_name,
                        line_number,
                        call_type
                    FROM code_calls
                    WHERE target_name IN ({placeholders})
                    ORDER BY source_file, line_number
                    """,
                    list(call_matchers),
                )
                for row in cursor:
                    results["references"].append(
                        {
                            **dict(row),
                            "reference_type": "call",
                        }
                    )

        return results

    def _generated_module_names(self, file_path: str) -> List[str]:
        """
        根据文件路径生成可能的模块名
        e.g. src/dimcause/core/auth.py ->
             src.dimcause.core.auth
             dimcause.core.auth
             core.auth
             auth
        """
        p = Path(file_path)
        stem = p.stem  # auth

        candidates = {stem}

        # 构建点分路径
        parts = list(p.parts)  # ('src', 'dimcause', 'core', 'auth.py')
        # 去掉扩展名
        parts[-1] = stem

        # 从后往前组合
        # 1. auth
        # 2. core.auth
        # 3. dimcause.core.auth
        # ...

        current = ""
        for part in reversed(parts):
            if part in [".", "..", "/"]:
                continue
            if not current:
                current = part
            else:
                current = f"{part}.{current}"
            candidates.add(current)

        return list(candidates)


# Helper functions
def update_code_index() -> int:
    """更新代码索引"""
    indexer = CodeIndexer()
    return indexer.index_all()


def trace_code(query: str) -> dict:
    """追踪代码"""
    indexer = CodeIndexer()
    return indexer.trace_symbol(query)
