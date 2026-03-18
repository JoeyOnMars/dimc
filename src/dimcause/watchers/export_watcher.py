"""
Export Watcher - 监听 Antigravity 导出目录

当用户在 Antigravity 中点击 Export 导出对话为 Markdown 后，
自动检测新文件并索引到 Dimcause。

Usage:
    dimc capture export --watch ~/Documents/AG_Exports/
"""

import os
import time
from datetime import datetime
from pathlib import Path


class ExportWatcher:
    """
    Antigravity 导出目录监听器 (Polling 模式)

    轮询指定目录，当检测到新的导出文件时自动处理。
    比 watchdog 更稳定，不依赖系统事件。
    """

    def __init__(self, watch_dir: str = None, interval: float = 2.0):
        if watch_dir is None:
            from dimcause.utils.config import get_config

            watch_dir = get_config().export_dir
        self.watch_dir = Path(os.path.expanduser(watch_dir))
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self._processed_files = set()
        self._running = False

        # 扩展名过滤
        self.extensions = {".md", ".markdown", ".txt", ".json"}

        # 初始化：记录现有文件（视作已处理）
        # 或者是：如果不记录，启动时会处理目录下所有旧文件？
        # 策略：启动时只记录，不处理旧文件，只处理新增
        self._scan_initial()

    def _scan_initial(self):
        """记录启动时的文件状态"""
        if not self.watch_dir.exists():
            return

        for f in self.watch_dir.iterdir():
            if f.is_file() and f.suffix.lower() in self.extensions:
                self._processed_files.add(f.name)

    def _default_callback(self, path: Path):
        """默认处理回调：复制到 Dimcause 日志目录并索引"""
        from dimcause.utils.config import get_config

        print(f"📥 检测到新导出: {path.name}")

        # 等待文件写入完成 (防抖)
        time.sleep(0.5)

        # 读取内容
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print("  ⚠️ 无法读取文件 (编码错误)")
            return
        except Exception as e:
            print(f"  ⚠️ 读取失败: {e}")
            return

        # 确定目标路径
        config = get_config()
        today = datetime.now().strftime("%Y/%m-%d")
        target_dir = config.logs_dir / today / "exports"
        target_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%H%M%S")
        target_file = target_dir / f"export_{timestamp}_{path.name}"

        # 复制文件
        target_file.write_text(content, encoding="utf-8")
        print(f"  ✅ 已保存到: {target_file.relative_to(config.root_dir)}")

        # 触发索引更新
        try:
            from dimcause.core.indexer import update_index

            update_index()
            print("  ✅ 索引已更新")
        except Exception as e:
            print(f"  ⚠️ 索引更新失败: {e}")

        # 尝试向量化
        try:
            from datetime import datetime as dt

            from dimcause.core.models import Event, EventType
            from dimcause.storage.vector_store import VectorStore

            # 创建 Event
            event = Event(
                id=f"export_{timestamp}",
                # 注意：这里我们已经修复了 EventType
                type=EventType.DISCUSSION,
                summary=f"Exported: {path.name}",
                content=content[:10000],  # 限制长度
                timestamp=dt.now(),
                tags=["export", "antigravity"],
            )

            store = VectorStore()
            store.add(event)
            print(f"  ✅ 已向量化 (ID: {event.id})")
        except Exception as e:
            print(f"  ⚠️ 向量化失败: {e}")
            import traceback

            traceback.print_exc()

    def start(self):
        """启动监听"""
        self._running = True
        print(f"👁️ 正在监听导出目录 (轮询模式): {self.watch_dir}")
        print("   在 Antigravity 中点击 Export 导出对话，Dimcause 将自动处理")
        print("   按 Ctrl+C 停止")

        try:
            while self._running:
                self._scan()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.stop()

    def _scan(self):
        """扫描目录变化"""
        if not self.watch_dir.exists():
            return

        current_files = set()

        try:
            for f in self.watch_dir.iterdir():
                if f.is_file() and f.suffix.lower() in self.extensions:
                    if f.name.startswith("."):
                        continue

                    current_files.add(f.name)

                    # 发现新文件
                    if f.name not in self._processed_files:
                        self._processed_files.add(f.name)
                        self._default_callback(f)
        except Exception as e:
            print(f"Scan error: {e}")

    def stop(self):
        """停止监听"""
        self._running = False
        print("\n⏹️ 已停止监听")


def watch_exports(watch_dir: str = None):
    """便捷函数：启动导出监听"""
    watcher = ExportWatcher(watch_dir)
    watcher.start()


if __name__ == "__main__":
    watch_exports()
