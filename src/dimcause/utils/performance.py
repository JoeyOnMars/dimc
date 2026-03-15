"""
Performance Monitoring Utilities

Decorators and tools for monitoring Dimcause performance.
"""

import json
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Track performance metrics"""

    def __init__(self):
        self.metrics = []

    def record(self, func_name: str, duration: float, args_summary: str = ""):
        """Record a performance metric"""
        self.metrics.append(
            {
                "function": func_name,
                "duration": duration,
                "args": args_summary,
                "timestamp": time.time(),
            }
        )

    def get_stats(self):
        """Get performance statistics"""
        if not self.metrics:
            return {}

        by_func = {}
        for metric in self.metrics:
            fname = metric["function"]
            if fname not in by_func:
                by_func[fname] = []
            by_func[fname].append(metric["duration"])

        stats = {}
        for fname, durations in by_func.items():
            stats[fname] = {
                "count": len(durations),
                "total": sum(durations),
                "avg": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
            }

        return stats

    def save_report(self, output_path: Path):
        """Save performance report to file"""
        stats = self.get_stats()
        with open(output_path, "w") as f:
            json.dump({"stats": stats, "raw_metrics": self.metrics}, f, indent=2)


# Global monitor instance
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor"""
    return _monitor


def performance_monitor(threshold_seconds: float = 1.0):
    """
    Decorator to monitor function performance.

    Args:
        threshold_seconds: Log warning if execution exceeds this threshold

    Usage:
        @performance_monitor(threshold_seconds=0.5)
        def slow_function():
            time.sleep(1)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start

                # Build args summary
                args_summary = f"{len(args)} args" if args else "no args"

                # Record metric
                _monitor.record(func.__name__, elapsed, args_summary)

                # Log if slow
                if elapsed > threshold_seconds:
                    logger.warning(
                        f"[PERF] {func.__name__} took {elapsed:.2f}s "
                        f"(threshold: {threshold_seconds}s)"
                    )

        return wrapper

    return decorator


def timed(func: Callable) -> Callable:
    """
    Simple timing decorator for development/debugging.

    Usage:
        @timed
        def my_function():
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"⏱️  {func.__name__}: {elapsed:.3f}s")
        return result

    return wrapper


def measure_memory(func: Callable) -> Callable:
    """
    Measure memory usage of a function (requires psutil).

    Usage:
        @measure_memory
        def memory_intensive():
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            result = func(*args, **kwargs)

            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_used = mem_after - mem_before

            if mem_used > 10:  # > 10 MB
                logger.warning(
                    f"[MEM] {func.__name__} used {mem_used:.1f} MB (peak: {mem_after:.1f} MB)"
                )

            return result
        except ImportError:
            # psutil not available, just run function
            return func(*args, **kwargs)

    return wrapper
