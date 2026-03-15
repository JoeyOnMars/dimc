"""
Dimcause v5.1 Search

Layer 4: Query Interface - 查询接口
"""

from .engine import SearchEngine
from .result_view import SearchResultView, build_search_result_view

__all__ = [
    "SearchEngine",
    "SearchResultView",
    "build_search_result_view",
]
