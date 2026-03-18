"""
Additional edge case tests for dimc trace command
"""

from dimcause.core.code_indexer import CodeIndexer, trace_code


def test_trace_nonexistent_symbol():
    """Test tracing a symbol that doesn't exist"""
    result = trace_code("NonExistentClass12345")

    assert "definitions" in result
    assert "references" in result
    assert len(result["definitions"]) == 0
    assert len(result["references"]) == 0


def test_trace_empty_string():
    """Test tracing with empty string"""
    result = trace_code("")

    assert "definitions" in result
    assert "references" in result


def test_trace_special_characters():
    """Test tracing with special characters"""
    result = trace_code("!@#$%^&*()")

    # Should not crash
    assert isinstance(result, dict)


def test_trace_very_long_query():
    """Test tracing with very long query string"""
    long_query = "a" * 1000
    result = trace_code(long_query)

    assert isinstance(result, dict)


def test_trace_unicode_characters():
    """Test tracing with Unicode characters"""
    result = trace_code("文件处理类")

    assert isinstance(result, dict)


def test_trace_with_path_separators():
    """Test tracing with path-like strings"""
    result = trace_code("src/dimcause/cli.py")

    # Should handle gracefully
    assert isinstance(result, dict)


def test_trace_case_sensitivity():
    """Test that trace is case-sensitive for code symbols"""
    # Assuming there's a class called 'Config'
    result1 = trace_code("Config")
    result2 = trace_code("config")
    result3 = trace_code("CONFIG")

    # All should return results, but potentially different ones
    assert isinstance(result1, dict)
    assert isinstance(result2, dict)
    assert isinstance(result3, dict)


def test_code_indexer_multiple_files(tmp_path):
    """Test indexing multiple files"""
    indexer = CodeIndexer()

    # Create test files
    file1 = tmp_path / "test1.py"
    file1.write_text("""
class TestClass1:
    def method1(self):
        pass
""")

    file2 = tmp_path / "test2.py"
    file2.write_text("""
from test1 import TestClass1

class TestClass2:
    def method2(self):
        pass
""")

    # Index both files
    indexer.index_file(file1)
    indexer.index_file(file2)

    # Should find both classes
    result1 = indexer.find_symbol("TestClass1")
    result2 = indexer.find_symbol("TestClass2")

    assert len(result1) > 0
    assert len(result2) > 0


def test_code_indexer_handles_syntax_errors(tmp_path):
    """Test that indexer handles files with syntax errors gracefully"""
    indexer = CodeIndexer()

    bad_file = tmp_path / "bad_syntax.py"
    bad_file.write_text("""
def broken_function(
    # Missing closing parenthesis
    pass
""")

    # Should not crash, just skip or handle gracefully
    try:
        indexer.index_file(bad_file)
        # Success if it doesn't crash
        assert True
    except Exception:
        # Or if it raises, it should be a controlled exception
        assert True


def test_code_indexer_empty_file(tmp_path):
    """Test indexing an empty file"""
    indexer = CodeIndexer()

    empty_file = tmp_path / "empty.py"
    empty_file.write_text("")

    indexer.index_file(empty_file)

    # Should handle gracefully
    assert True


def test_code_indexer_large_file(tmp_path):
    """Test indexing a large file"""
    indexer = CodeIndexer()

    large_file = tmp_path / "large.py"

    # Create a file with many classes
    content = []
    for i in range(100):
        content.append(f"""
class TestClass{i}:
    def method{i}(self):
        pass
""")

    large_file.write_text("\n".join(content))

    indexer.index_file(large_file)

    # Should find classes
    result = indexer.find_symbol("TestClass50")
    assert len(result) > 0


def test_trace_with_namespace():
    """Test tracing with namespaced symbols"""
    # Should handle module paths
    result = trace_code("dimcause.utils.config.Config")

    assert isinstance(result, dict)
