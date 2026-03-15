"""
Search Cache Utilities

LRU cache for search results to improve performance.
"""

import hashlib
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=100)
def cached_search_query(query_hash: str, mode: str, top_k: int) -> str:
    """
    Cached search result lookup by query hash.

    This is a placeholder that returns the cache key.
    The actual implementation should integrate with search engine.

    Args:
        query_hash: MD5 hash of the query string
        mode: Search mode
        top_k: Number of results

    Returns:
        Cached result JSON string (or empty if miss)
    """
    # This is a cache layer - actual search happens in SearchEngine
    return ""


def get_query_hash(query: str) -> str:
    """Generate a hash from query string for cache key"""
    return hashlib.md5(query.encode()).hexdigest()


class SearchCache:
    """
    In-memory LRU cache for search results.

    Usage:
        cache = SearchCache(maxsize=100)

        # Try to get from cache
        results = cache.get(query, mode, top_k)

        if results is None:
            # Cache miss - perform actual search
            results = search_engine.search(query, mode, top_k)
            cache.put(query, mode, top_k, results)
    """

    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self._cache = {}
        self._access_order = []  # Track access for LRU
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str, mode: str, top_k: int) -> str:
        """Generate cache key"""
        return f"{get_query_hash(query)}:{mode}:{top_k}"

    def get(self, query: str, mode: str, top_k: int) -> Any:
        """
        Get cached results.

        Returns:
            Cached results or None if cache miss
        """
        key = self._make_key(query, mode, top_k)

        if key in self._cache:
            # Hit - move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            self.hits += 1
            return self._cache[key]

        self.misses += 1
        return None

    def put(self, query: str, mode: str, top_k: int, results: Any):
        """Cache search results"""
        key = self._make_key(query, mode, top_k)

        # Evict LRU if at capacity
        if len(self._cache) >= self.maxsize and key not in self._cache:
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]

        self._cache[key] = results

        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def clear(self):
        """Clear all cached results"""
        self._cache.clear()
        self._access_order.clear()
        self.hits = 0
        self.misses = 0

    def get_hit_rate(self) -> float:
        """Get cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def stats(self) -> dict:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.get_hit_rate(),
        }


# Global cache instance
_search_cache = SearchCache(maxsize=100)


def get_search_cache() -> SearchCache:
    """Get the global search cache instance"""
    return _search_cache
