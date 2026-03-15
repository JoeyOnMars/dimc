import sqlite3
from pathlib import Path

import pytest

from dimcause.core.code_indexer import CodeIndexer
from dimcause.extractors.ast_analyzer import ASTAnalyzer, build_code_dependency_graph


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure with python files."""
    # Structure:
    # src/
    #   main.py (imports utils)
    #   utils.py (defines helper)

    src = tmp_path / "src"
    src.mkdir()

    (src / "utils.py").write_text(
        '''
def helper():
    """A helper function"""
    pass

class MyClass:
    def method(self):
        pass
''',
        encoding="utf-8",
    )

    (src / "main.py").write_text(
        """
from utils import helper
import os

def main():
    helper()
""",
        encoding="utf-8",
    )

    return tmp_path


def test_code_indexer_basic(temp_project):
    db_path = temp_project / ".index.db"
    project_root = temp_project

    indexer = CodeIndexer(db_path=db_path, project_root=project_root)
    count = indexer.index_all()

    assert count == 2

    # Check DB directly
    with sqlite3.connect(db_path) as conn:
        # Check files
        files = conn.execute("SELECT path FROM code_files").fetchall()
        paths = [f[0] for f in files]
        assert "src/main.py" in paths or str(Path("src/main.py")) in paths
        assert "src/utils.py" in paths or str(Path("src/utils.py")) in paths

        # Check entities
        # utils.py: helper, MyClass
        entities = conn.execute("SELECT name, type FROM code_entities").fetchall()
        names = [e[0] for e in entities]
        assert "helper" in names
        assert "MyClass" in names

        # Check imports
        imports = conn.execute("SELECT module_name FROM code_imports").fetchall()
        modules = [i[0] for i in imports]
        assert "utils" in modules or "os" in modules


def test_trace_symbol(temp_project):
    db_path = temp_project / ".index.db"
    indexer = CodeIndexer(db_path=db_path, project_root=temp_project)
    indexer.index_all()

    # 1. Trace definition
    res = indexer.trace_symbol("helper")
    assert len(res["definitions"]) >= 1
    assert res["definitions"][0]["name"] == "helper"
    assert "utils.py" in str(res["definitions"][0]["file_path"])

    # 2. Trace reference (incoming dependency)
    # helper is imported by main.py
    # But wait, trace_symbol logic relies on name matching.
    # If I trace "helper", I find definition in utils.py.
    # Then I look for imports of "utils" (because utils.py -> utils).
    # main.py has `from utils import helper`. Analyzer extracts `utils`.
    # So `code_imports` has (main.py, utils).
    # So searching imports of 'utils' should find main.py.

    assert len(res["references"]) >= 1
    src_files = [r["source_file"] for r in res["references"]]
    assert any("main.py" in s for s in src_files)
    assert any(r.get("reference_type") == "call" for r in res["references"])
    assert any(
        r.get("reference_type") == "call" and r.get("source_entity") == "main"
        for r in res["references"]
    )


def test_trace_file(temp_project):
    db_path = temp_project / ".index.db"
    indexer = CodeIndexer(db_path=db_path, project_root=temp_project)
    indexer.index_all()

    # Trace file name "utils.py"
    # Fallback search should find it as a definition
    res = indexer.trace_symbol("utils")
    found_file = False
    for d in res["definitions"]:
        if d["type"] == "file" and "utils.py" in str(d["file_path"]):
            found_file = True
            break
    assert found_file

    # And references (who imports utils)
    assert len(res["references"]) >= 1


def test_ast_analyzer_extracts_class_qualified_methods():
    analyzer = ASTAnalyzer()
    code = """
class MyClass:
    def method(self):
        return helper()

    def other(self):
        return 1


def helper():
    return 42
"""

    entities = analyzer.extract_functions(code, "python", "sample.py")
    names = {entity.name: entity.type.value for entity in entities}

    assert names["helper"] == "function"
    assert names["MyClass.method"] == "method"
    assert names["MyClass.other"] == "method"


def test_build_code_dependency_graph_tracks_method_calls():
    code = """
class MyClass:
    def method(self):
        helper()
        self.other()

    def other(self):
        return 1


def helper():
    return 42
"""

    graph = build_code_dependency_graph("sample.py", code, "python")
    deps = set(graph["dependencies"])

    assert ("sample.py:MyClass.method", "sample.py:helper", "calls") in deps
    assert ("sample.py:MyClass.method", "sample.py:MyClass.other", "calls") in deps


def test_trace_symbol_resolves_method_call_references(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "service.py").write_text(
        """
class Service:
    def run(self):
        self.helper()

    def helper(self):
        return 1
""",
        encoding="utf-8",
    )

    db_path = tmp_path / ".index.db"
    indexer = CodeIndexer(db_path=db_path, project_root=tmp_path)
    indexer.index_all()

    res = indexer.trace_symbol("Service.helper")

    assert any(d["name"] == "Service.helper" for d in res["definitions"])
    assert any(
        r.get("reference_type") == "call"
        and r.get("source_entity") == "Service.run"
        and r.get("target_name") == "Service.helper"
        for r in res["references"]
    )
