"""
文件锁工具 (改进版)

特性:
1. 基于目录的原子锁
2. 指数退避 + 随机抖动
3. 自动清理过期锁
4. 完整的日志记录
"""

import logging
import os
import random
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from dimcause.utils.config import get_config

logger = logging.getLogger(__name__)


def get_lock_dir() -> Path:
    """获取锁目录"""
    config = get_config()
    config.lock_dir.mkdir(parents=True, exist_ok=True)
    return config.lock_dir


class FileLock:
    """基于目录的文件锁 (mkdir 原子操作)"""

    def __init__(self, name: str, timeout: Optional[int] = None):
        """
        初始化锁

        Args:
            name: 锁名称
            timeout: 获取锁的超时时间 (秒)，None 使用默认配置
        """
        config = get_config()
        self.name = name
        self.timeout = timeout if timeout is not None else config.lock_timeout
        self.lock_path = get_lock_dir() / f"{name}.lockdir"
        self._acquired = False
        self._pid = os.getpid()

    def acquire(self) -> bool:
        """
        获取锁 (使用指数退避 + 随机抖动)

        Returns:
            是否成功获取
        """
        config = get_config()
        start_time = time.time()
        attempt = 0

        while True:
            try:
                # mkdir 是原子操作
                self.lock_path.mkdir(exist_ok=False)

                # 写入锁信息
                info_file = self.lock_path / "info"
                info_file.write_text(f"{self._pid}:{int(time.time())}")

                self._acquired = True
                logger.debug(f"Lock acquired: {self.name} (attempt {attempt + 1})")
                return True
            except FileExistsError:
                pass
            except OSError as e:
                logger.warning(f"Lock acquire error: {self.name}: {e}")
                return False

            elapsed = time.time() - start_time
            if elapsed >= self.timeout:
                logger.warning(f"Lock timeout: {self.name} after {elapsed:.1f}s")
                return False

            # 指数退避 + 随机抖动
            delay = min(
                config.lock_retry_base * (2**attempt) + random.uniform(0, 0.1),
                1.0,  # 最大等待1秒
            )
            time.sleep(delay)
            attempt += 1

            if attempt >= config.lock_max_retries:
                logger.warning(f"Lock max retries exceeded: {self.name}")
                return False

        return False

    def release(self) -> None:
        """释放锁"""
        if not self._acquired:
            return

        if not self.lock_path.exists():
            self._acquired = False
            return

        try:
            info_file = self.lock_path / "info"
            if info_file.exists():
                info_file.unlink()
            self.lock_path.rmdir()
            logger.debug(f"Lock released: {self.name}")
        except OSError as e:
            # 锁已被其他进程删除，这是可接受的
            logger.debug(f"Lock release ignored: {self.name}: {e}")
        finally:
            self._acquired = False

    def is_held(self) -> bool:
        """检查锁是否被持有"""
        return self.lock_path.exists()

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Failed to acquire lock: {self.name}")
        return self

    def __exit__(self, *args):
        self.release()


@contextmanager
def with_lock(name: str, timeout: Optional[int] = None):
    """
    上下文管理器形式的锁

    Usage:
        with with_lock("session-end"):
            # 执行需要锁保护的操作
            pass
    """
    lock = FileLock(name, timeout)
    try:
        if not lock.acquire():
            raise TimeoutError(f"Failed to acquire lock: {name}")
        yield lock
    finally:
        lock.release()


def cleanup_stale_locks(max_age: Optional[int] = None) -> int:
    """
    清理过期的锁

    Args:
        max_age: 最大年龄 (秒)，None 使用默认配置

    Returns:
        清理的锁数量
    """
    config = get_config()
    if max_age is None:
        max_age = config.stale_lock_max_age

    lock_dir = get_lock_dir()
    now = int(time.time())
    cleaned = 0

    for lock_path in lock_dir.glob("*.lockdir"):
        if not lock_path.is_dir():
            continue

        info_file = lock_path / "info"
        should_remove = False

        if not info_file.exists():
            # 没有 info 文件，锁状态不完整
            should_remove = True
        else:
            try:
                content = info_file.read_text()
                pid_str, timestamp_str = content.split(":")
                timestamp = int(timestamp_str)
                age = now - timestamp

                if age > max_age:
                    should_remove = True
                    logger.info(f"Cleaning stale lock: {lock_path.name} (age: {age}s)")
            except (ValueError, OSError):
                should_remove = True

        if should_remove:
            try:
                if info_file.exists():
                    info_file.unlink()
                lock_path.rmdir()
                cleaned += 1
            except OSError:
                pass

    return cleaned
