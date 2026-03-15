# Security Baseline: SEC-1.1 / SEC-1.2 (Level A)
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dimcause.core.event_index import EventIndex


@dataclass
class TraceNode:
    """Represents a node in the trace graph (File, Code Entity, or Event)"""

    id: str
    type: str  # "file" | "code_definition" | "code_reference" | event types
    summary: str
    timestamp: float
    path: Optional[str] = None
    relevance: float = 1.0  # 0.0 - 1.0
    # Code entity fields (for AST-based analysis)
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None  # "class" | "function" | "method"
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None


class TraceService:
    """
    T1 Trace Engine Core Logic.

    Responsibility:
    - Find related files by keyword (grep)
    - Find related events by keyword/file (EventIndex)
    - Build a simple correlation graph
    """

    def __init__(self, index: Optional[EventIndex] = None):
        self.index = index or EventIndex()
        self.project_root = Path.cwd()  # Assume running from root

    def trace(self, query: str, limit: int = 50) -> List[TraceNode]:
        """
        Main entry point: Trace a topic across files and events.
        """
        nodes: List[TraceNode] = []

        # 1. Find Code Entities (Definitions & References from CodeIndex)
        code_entities = self._find_code_entities(query)
        nodes.extend(code_entities)

        # 2. Find Files (Fallback for non-Python files via git grep)
        related_files = self._find_files(query, limit=limit)
        # Filter out files already covered by code entities
        existing_paths = {n.path for n in code_entities if n.path}
        for file_node in related_files:
            if file_node.path not in existing_paths:
                nodes.append(file_node)

        # 3. Find Events (Context)
        # Strategy: Find events mentioning the query directly
        related_events = self._find_events(query, limit=limit)
        for e in related_events:
            nodes.append(
                TraceNode(
                    id=e["id"],
                    type=e["type"],
                    summary=e.get("summary", ""),
                    timestamp=datetime.fromisoformat(e["timestamp"]).timestamp(),
                    path=e.get("markdown_path"),
                    relevance=0.9,
                )
            )

        # 4. Sort by relevance then time
        nodes.sort(key=lambda x: (x.relevance, x.timestamp), reverse=True)
        return nodes

    def _find_code_entities(self, query: str) -> List[TraceNode]:
        """
        使用 CodeIndex 查找代码实体（定义和引用）

        Returns:
            List[TraceNode]: 代码定义和引用节点
        """
        nodes = []

        try:
            from dimcause.core.code_indexer import trace_code

            results = trace_code(query)

            # 添加定义节点
            for defn in results.get("definitions", []):
                nodes.append(
                    TraceNode(
                        id=f"def:{defn['file_path']}:{defn['line_start']}",
                        type="code_definition",
                        summary=f"{defn['type'].capitalize()}: {defn['name']}",
                        timestamp=self._get_file_mtime(defn["file_path"]),
                        path=defn["file_path"],
                        relevance=1.0,
                        entity_name=defn["name"],
                        entity_type=defn["type"],
                        line_start=defn["line_start"],
                        line_end=defn.get("line_end"),
                        signature=defn.get("signature"),
                        docstring=defn.get("docstring"),
                    )
                )

            # 添加引用节点
            for ref in results.get("references", []):
                reference_type = ref.get("reference_type", "import")
                if reference_type == "call":
                    summary = f"Called by {ref.get('source_entity') or ref['source_file']}"
                else:
                    summary = f"Imported by {ref['source_file']}"
                nodes.append(
                    TraceNode(
                        id=f"ref:{ref['source_file']}:{ref['line_number']}",
                        type="code_reference",
                        summary=summary,
                        timestamp=self._get_file_mtime(ref["source_file"]),
                        path=ref["source_file"],
                        relevance=0.9,
                        entity_name=query,
                        line_start=ref["line_number"],
                    )
                )

        except Exception as e:
            # CodeIndex 不可用时静默失败，回退到 git grep
            print(f"Warning: CodeIndex unavailable: {e}")

        return nodes

    def _find_files(self, query: str, limit: int = 20) -> List[TraceNode]:
        """
        Find file matches containing the query string using git grep.
        Excludes .git, .agent, docs/logs.
        """
        results: List[TraceNode] = []
        seen_paths = set()

        # Try git grep first if in a git repo
        if (self.project_root / ".git").exists():
            try:
                cmd = ["git", "grep", "-n", "-I", "-F", query, "--", "src", "docs", "tests"]
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(self.project_root),
                )
                if process.returncode == 0:
                    for raw_line in process.stdout.strip().split("\n"):
                        if not raw_line:
                            continue
                        path, line_number, snippet = self._parse_grep_match(raw_line)
                        if not path or path.startswith("docs/logs/") or path in seen_paths:
                            continue
                        seen_paths.add(path)
                        results.append(
                            TraceNode(
                                id=f"file:{path}:{line_number or 0}",
                                type="file",
                                summary=snippet or f"File matching '{query}'",
                                timestamp=self._get_file_mtime(path),
                                path=path,
                                relevance=0.8,
                                line_start=line_number,
                            )
                        )
                        if len(results) >= limit:
                            break
            except Exception as e:
                # Fallback or log consistency warning
                print(f"Warning: git grep failed: {e}")

        return results

    def _parse_grep_match(self, raw_line: str) -> tuple[str, Optional[int], str]:
        parts = raw_line.split(":", 2)
        if len(parts) != 3:
            return raw_line.strip(), None, ""

        path, line_number_text, snippet = parts
        try:
            line_number = int(line_number_text)
        except ValueError:
            line_number = None
        return path.strip(), line_number, snippet.strip()

    def _find_events(self, query: str, limit: int = 100) -> List[Dict]:
        """Query EventIndex for query string in summary/content/json_cache"""
        conn = self.index._get_conn()
        try:
            # We search in summary, tags, and json_cache (which contains full content summary sometimes)
            # Using LIKE for basic keyword match
            term = f"%{query}%"
            sql = """
                SELECT * FROM events
                WHERE summary LIKE ?
                   OR tags LIKE ?
                   OR json_cache LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            cursor = conn.execute(sql, (term, term, term, limit))
            return [dict(row) for row in cursor]
        finally:
            conn.close()

    def _get_file_mtime(self, relative_path: str) -> float:
        try:
            return (self.project_root / relative_path).stat().st_mtime
        except Exception:
            return 0.0
