"""
文件锁模块测试
"""

import tempfile
import threading
import time
from pathlib import Path

import pytest


class TestFileLock:
    """文件锁测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        """创建临时锁目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_acquire_and_release(self, temp_lock_dir):
        """测试获取和释放锁"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("test-lock", timeout=5)

        # 获取锁
        assert lock.acquire() is True
        assert lock._acquired is True

        # 锁目录应该存在
        lock_path = temp_lock_dir / "test-lock.lockdir"
        assert lock_path.exists()

        # 释放锁
        lock.release()
        assert lock._acquired is False
        assert not lock_path.exists()

    def test_context_manager(self, temp_lock_dir):
        """测试上下文管理器"""
        from dimcause.utils.lock import FileLock

        lock_path = temp_lock_dir / "context-lock.lockdir"

        with FileLock("context-lock") as lock:
            assert lock._acquired is True
            assert lock_path.exists()

        # 退出后锁应该释放
        assert not lock_path.exists()

    def test_with_lock_decorator(self, temp_lock_dir):
        """测试 with_lock 上下文管理器"""
        from dimcause.utils.lock import with_lock

        executed = False

        with with_lock("decorator-lock"):
            executed = True
            lock_path = temp_lock_dir / "decorator-lock.lockdir"
            assert lock_path.exists()

        assert executed is True

    def test_lock_timeout(self, temp_lock_dir):
        """测试锁超时"""
        from dimcause.utils.lock import FileLock

        # 第一个锁
        lock1 = FileLock("timeout-lock", timeout=1)
        assert lock1.acquire() is True

        # 第二个锁应该超时
        lock2 = FileLock("timeout-lock", timeout=1)
        assert lock2.acquire() is False

        # 释放第一个锁
        lock1.release()

        # 现在第二个锁应该能获取
        assert lock2.acquire() is True
        lock2.release()

    def test_cleanup_stale_locks(self, temp_lock_dir):
        """测试清理过期锁"""
        from dimcause.utils.lock import cleanup_stale_locks

        # 创建一个 "过期" 的锁
        stale_lock = temp_lock_dir / "stale.lockdir"
        stale_lock.mkdir()
        info_file = stale_lock / "info"
        # 写入一个很老的时间戳
        info_file.write_text("12345:1000000000")  # 2001年

        # 清理
        cleanup_stale_locks(max_age=1)

        # 应该被清理
        assert not stale_lock.exists()


class TestLockConcurrency:
    """锁并发测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_concurrent_access(self, temp_lock_dir):
        """测试并发访问"""
        from dimcause.utils.lock import FileLock

        results = []

        def worker(worker_id):
            lock = FileLock("concurrent-lock", timeout=5)
            if lock.acquire():
                results.append(f"acquired-{worker_id}")
                time.sleep(0.1)
                lock.release()
                results.append(f"released-{worker_id}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 每个 worker 应该都成功获取并释放了锁
        assert len([r for r in results if r.startswith("acquired")]) == 3
        assert len([r for r in results if r.startswith("released")]) == 3


class TestLockMethods:
    """锁方法测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_is_held(self, temp_lock_dir):
        """is_held 方法"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("held-test", timeout=5)

        # 初始不被持有
        assert lock.is_held() is False

        # 获取后被持有
        lock.acquire()
        assert lock.is_held() is True

        # 释放后不被持有
        lock.release()
        assert lock.is_held() is False

    def test_release_without_acquire(self, temp_lock_dir):
        """未获取就释放"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("not-acquired", timeout=1)
        # 不应抛出异常
        lock.release()

    def test_get_lock_dir(self, temp_lock_dir):
        """get_lock_dir 函数"""
        from dimcause.utils.lock import get_lock_dir

        lock_dir = get_lock_dir()
        assert lock_dir.exists()


class TestLockTimeout:
    """锁超时测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_lock_timeout(self, temp_lock_dir, monkeypatch):
        """锁超时测试"""
        from dimcause.utils.lock import FileLock

        # 创建一个很短超时的锁
        lock1 = FileLock("timeout-test", timeout=0.1)
        lock2 = FileLock("timeout-test", timeout=0.1)

        # 第一个锁获取成功
        assert lock1.acquire() is True

        # 第二个锁应该超时失败
        result = lock2.acquire()
        assert result is False

        lock1.release()


class TestLockContextManager:
    """锁上下文管理器测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_context_manager(self, temp_lock_dir):
        """with 语句测试"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("context-test", timeout=5)

        with lock:
            # 在 with 块中应该持有锁
            assert lock.is_held() is True

        # 退出 with 后应该释放
        assert lock.is_held() is False

    def test_context_manager_exception(self, temp_lock_dir):
        """with 异常时仍释放锁"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("exception-test", timeout=5)

        try:
            with lock:
                assert lock.is_held() is True
                raise ValueError("test error")
        except ValueError:
            pass

        # 异常后仍应释放
        assert lock.is_held() is False


class TestWithLockFunction:
    """with_lock 函数测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_with_lock_function(self, temp_lock_dir):
        """with_lock 上下文管理器"""
        from dimcause.utils.lock import with_lock

        with with_lock("func-test"):
            # 在 with 块中执行操作
            pass  # 成功执行


class TestFileLockEdgeCases:
    """FileLock 边缘情况测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_release_deleted_lock(self, temp_lock_dir):
        """释放已被删除的锁"""
        from dimcause.utils.lock import FileLock

        lock = FileLock("deleted-test", timeout=5)
        lock.acquire()

        # 模拟锁被其他进程删除
        import shutil

        if lock.lock_path.exists():
            shutil.rmtree(lock.lock_path)

        # 释放不应抛出异常
        lock.release()
        assert lock._acquired is False

    def test_acquire_context_timeout(self, temp_lock_dir):
        """上下文管理器获取超时"""
        import pytest

        from dimcause.utils.lock import FileLock

        lock1 = FileLock("ctx-timeout", timeout=5)
        lock2 = FileLock("ctx-timeout", timeout=0.1)

        lock1.acquire()

        # 第二个锁应该抛出 TimeoutError
        with pytest.raises(TimeoutError):
            with lock2:
                pass

        lock1.release()

    def test_max_retries_exceeded(self, temp_lock_dir, monkeypatch):
        """超过最大重试次数"""
        from dimcause.utils.config import get_config
        from dimcause.utils.lock import FileLock

        # 设置很低的重试次数
        config = get_config()
        original_retries = config.lock_max_retries
        monkeypatch.setattr(config, "lock_max_retries", 1)
        lock1 = FileLock("max-retry", timeout=10)
        lock2 = FileLock("max-retry", timeout=10)

        lock1.acquire()

        # 第二个锁应该因为重试次数超限而失败
        result = lock2.acquire()
        assert result is False

        lock1.release()
        monkeypatch.setattr(config, "lock_max_retries", original_retries)


class TestLockOSError:
    """OSError 边缘情况测试"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_acquire_oserror(self, temp_lock_dir, monkeypatch):
        """acquire 时的 OSError"""
        import os

        from dimcause.utils.lock import FileLock

        lock = FileLock("oserror-test", timeout=1)

        # 模拟 mkdir 抛出 OSError
        original_mkdir = os.mkdir

        def mock_mkdir(path, mode=0o777):
            if "oserror-test" in str(path):
                raise OSError("Permission denied")
            return original_mkdir(path, mode)

        monkeypatch.setattr(os, "mkdir", mock_mkdir)

        result = lock.acquire()
        assert result is False

    def test_release_with_oserror(self, temp_lock_dir, monkeypatch):
        """release 时的 OSError"""

        from dimcause.utils.lock import FileLock

        lock = FileLock("release-error", timeout=5)
        lock.acquire()

        # 让锁目录变得不可删除

        # 模拟 rmdir 失败
        original_rmdir = Path.rmdir

        def mock_rmdir(self):
            if "release-error" in str(self):
                raise OSError("Directory not empty")
            return original_rmdir(self)

        monkeypatch.setattr(Path, "rmdir", mock_rmdir)

        # release 应该不崩溃
        lock.release()
        assert lock._acquired is False


class TestLockStaleDetection:
    """锁过期检测"""

    @pytest.fixture
    def temp_lock_dir(self, monkeypatch):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir)
            monkeypatch.setattr("dimcause.utils.lock.get_lock_dir", lambda: lock_dir)
            yield lock_dir

    def test_stale_lock_info(self, temp_lock_dir):
        """过期锁的信息文件"""
        from dimcause.utils.lock import FileLock

        lock1 = FileLock("stale-test", timeout=5)
        lock1.acquire()

        # 检查 info 文件
        info = lock1.lock_path / "info"
        assert info.exists()

        content = info.read_text()
        assert "pid" in content.lower() or content.strip() != ""

        lock1.release()
