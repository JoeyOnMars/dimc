"""
BaseWatcher - 所有 Watcher 的基类

提供共享功能：
- Debounce 机制
- 文件监听
- 回调管理
"""

import os
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from dimcause.core.models import RawData, SourceType


class DebounceHandler(FileSystemEventHandler):
    """
    防抖动文件事件处理器

    在 debounce_seconds 内的多次修改只触发一次回调
    """

    def __init__(self, callback: Callable[[str], None], debounce_seconds: float = 1.0):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_modified: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return

        path = event.src_path
        current_time = time.time()

        with self._lock:
            last_time = self._last_modified.get(path, 0)

            if current_time - last_time > self.debounce_seconds:
                self._last_modified[path] = current_time
                # 在单独线程中执行，避免阻塞
                threading.Thread(target=self.callback, args=(path,), daemon=True).start()


class BaseWatcher(ABC):
    """
    Watcher 基类

    所有 IDE Watcher 必须继承此类
    """

    def __init__(self, watch_path: str, source: SourceType, debounce_seconds: float = 1.0):
        self.watch_path = os.path.expanduser(watch_path)
        self.source = source
        self.debounce_seconds = debounce_seconds

        self._observer: Optional[Observer] = None
        self._callbacks: List[Callable[[RawData], None]] = []
        self._is_running = False
        self._last_position: int = 0  # 文件读取位置

    @property
    @abstractmethod
    def name(self) -> str:
        """Watcher 名称"""
        ...

    @property
    def is_running(self) -> bool:
        return self._is_running

    def on_new_data(self, callback: Callable[[RawData], None]) -> None:
        """注册新数据回调"""
        self._callbacks.append(callback)

    def start(self) -> None:
        """启动监听"""
        if self._is_running:
            return

        # 检查文件/目录是否存在
        path = Path(self.watch_path)
        if not path.exists():
            raise FileNotFoundError(f"Watch path not found: {self.watch_path}")

        # 创建观察者
        self._observer = Observer()
        handler = DebounceHandler(
            callback=self._on_file_change, debounce_seconds=self.debounce_seconds
        )

        # 监听文件或目录
        if path.is_file():
            self._observer.schedule(handler, str(path.parent), recursive=False)
        else:
            self._observer.schedule(handler, str(path), recursive=True)

        self._observer.start()
        self._is_running = True

        # 初始化文件位置（从末尾开始，只监听新内容）
        if path.is_file():
            self._last_position = path.stat().st_size

    def stop(self) -> None:
        """停止监听"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._is_running = False

    def _on_file_change(self, file_path: str) -> None:
        """文件变化回调"""
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("文件发生变化: %s", file_path)

        # 只处理目标文件
        if not self._should_process(file_path):
            logger.debug("忽略文件: %s (should_process=False)", file_path)
            return

        # 读取新内容
        new_content = self._read_new_content(file_path)
        if not new_content:
            logger.debug("文件 %s 没有新增内容", file_path)
            return

        logger.debug("新增内容长度: %s", len(new_content))

        # 解析并触发回调
        raw_data = self._parse_content(new_content)
        if raw_data:
            logger.debug("解析到原始数据: %s", raw_data.id)
            for callback in self._callbacks:
                try:
                    callback(raw_data)
                except Exception as e:
                    # 回调异常不应该影响 Watcher
                    logger.error(f"Callback error: {e}")

    def _should_process(self, file_path: str) -> bool:
        """判断是否应该处理该文件"""
        # 默认：只处理目标文件
        return os.path.abspath(file_path) == os.path.abspath(self.watch_path)

    def _read_new_content(self, file_path: str) -> str:
        """读取文件新增内容"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.seek(self._last_position)
                content = f.read()
                self._last_position = f.tell()
                return content.strip()
        except Exception as e:
            print(f"Read error: {e}")
            return ""

    @abstractmethod
    def _parse_content(self, content: str) -> Optional[RawData]:
        """
        解析内容为 RawData

        子类必须实现，处理特定 IDE 的日志格式
        """
        ...
