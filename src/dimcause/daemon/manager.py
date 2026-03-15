"""
Dimcause Daemon Manager
Responsible for managing the lifecycle of all watchers and coordinating the data pipeline.
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

from dimcause.core.models import DimcauseConfig
from dimcause.services.pipeline import Pipeline
from dimcause.watchers import (
    BaseWatcher,
    ClaudeWatcher,
    ContinueWatcher,
    CursorWatcher,
    StateWatcher,
    WindsurfWatcher,
)

logger = logging.getLogger(__name__)


class DaemonManager:
    """
    Dimcause Daemon Manager

    Responsibilities:
    1. Manage Watcher Lifecycle
    2. Coordinate Data Pipeline
    3. Graceful Shutdown
    """

    def __init__(self, config: Optional[DimcauseConfig] = None):
        if config is None:
            # Load from file if not provided
            from dimcause.utils.config import get_config, load_config_file

            # 1. Get base paths from legacy config
            base_config = get_config()
            config_file = base_config.config_file

            # 2. Load raw dict
            raw_config = load_config_file(config_file)

            # 3. Construct DimcauseConfig (Pydantic will handle types)
            # Map legacy keys if needed, or rely on .logger-config having matching structure
            # For watchers, we support "watcher_claude.enabled=true" style in raw_config key-value

            # Prepare init dict
            init_data = {}
            if "data_dir" in raw_config:
                init_data["data_dir"] = raw_config["data_dir"]
            elif "logs_dir" in raw_config:
                init_data["data_dir"] = str(
                    base_config.root_dir / raw_config["logs_dir"]
                )  # Approximation
            else:
                init_data["data_dir"] = (
                    str(base_config.data_dir)
                    if hasattr(base_config, "data_dir")
                    else os.path.expanduser("~/.dimcause")
                )

            # Parse watcher configs from flat keys (e.g. watcher_claude.path)
            watchers = ["claude", "cursor", "continue_dev", "state", "windsurf"]
            for w in watchers:
                w_key = f"watcher_{w}"
                w_config = {}

                # Check for flat keys in raw_config (e.g. watcher_claude.enabled)
                for k, v in raw_config.items():
                    if k.startswith(f"{w_key}."):
                        field = k.split(".", 1)[1]
                        if field == "enabled" and isinstance(v, str):
                            v = v.lower() in ("true", "yes", "1")
                        elif field == "debounce_seconds":
                            v = float(v)
                        w_config[field] = v

                # Also check if json structure has it
                if w_key in raw_config and isinstance(raw_config[w_key], dict):
                    w_config.update(raw_config[w_key])

                if w_config:
                    init_data[w_key] = w_config

            self.config = DimcauseConfig(**init_data)
        else:
            self.config = config

        self._watchers: List[BaseWatcher] = []
        self._pipeline: Optional[Pipeline] = None

        self._is_running = False
        self._start_time: Optional[datetime] = None

        # Initialize
        self._setup()

    def _setup(self) -> None:
        """Initialize components"""
        # Initialize WAL
        from dimcause.utils.wal import WriteAheadLog

        wal_path = os.path.join(os.path.expanduser(self.config.data_dir), "wal", "active.log")
        self.wal = WriteAheadLog(wal_path=wal_path)

        # Initialize Pipeline with WAL
        self._pipeline = Pipeline(self.config, wal_manager=self.wal)

        # Initialize Watchers
        self._init_watchers()

    def _recover_pending(self) -> None:
        """Recover pending events from WAL"""
        from datetime import datetime

        from dimcause.core.models import RawData, SourceType

        pending_entries = self.wal.recover_pending()
        if not pending_entries:
            return

        logger.info(f"🔄 Recovering {len(pending_entries)} pending events from WAL...")
        for entry in pending_entries:
            try:
                # 重建 RawData 对象
                # WALEntry.data 包含 raw data fields
                raw = RawData(
                    id=entry.id,
                    source=SourceType(entry.data.get("source", "manual")),
                    content=entry.data.get("content", ""),
                    timestamp=datetime.fromisoformat(str(entry.data.get("timestamp")))
                    if isinstance(entry.data.get("timestamp"), str)
                    else entry.data.get("timestamp"),  # Handle string or datetime if rehydrated
                    files_mentioned=entry.data.get("files_mentioned", []),
                    project_path=entry.data.get("project_path"),
                )

                logger.info(f"  ↪ Replaying {entry.id}")
                self._pipeline.process(raw)
            except Exception as e:
                logger.error(f"  ❌ Recovery failed for {entry.id}: {e}")

        logger.info("✅ Recovery complete.")

    def _init_watchers(self) -> None:
        """Initialize configured watchers"""
        # Claude Watcher
        if self.config.watcher_claude.enabled:
            try:
                watcher = ClaudeWatcher(
                    watch_path=self.config.watcher_claude.path,
                    debounce_seconds=self.config.watcher_claude.debounce_seconds,
                )
                self.register_watcher(watcher)
                print(f"✅ Claude Watcher initialized: {watcher.watch_path}")
            except Exception as e:
                print(f"⚠️ Claude Watcher failed: {e}")

        # Cursor Watcher
        if self.config.watcher_cursor and self.config.watcher_cursor.enabled:
            try:
                watcher = CursorWatcher(
                    watch_path=self.config.watcher_cursor.path,
                    debounce_seconds=self.config.watcher_cursor.debounce_seconds,
                )
                self.register_watcher(watcher)
                print(f"✅ Cursor Watcher initialized: {watcher.watch_path}")
            except Exception as e:
                print(f"⚠️ Cursor Watcher failed: {e}")

        # Windsurf Watcher
        if self.config.watcher_windsurf and self.config.watcher_windsurf.enabled:
            try:
                watcher = WindsurfWatcher(
                    watch_path=self.config.watcher_windsurf.path,
                    debounce_seconds=self.config.watcher_windsurf.debounce_seconds,
                )
                self.register_watcher(watcher)
                print(f"✅ Windsurf Watcher initialized: {watcher.watch_path}")
            except Exception as e:
                print(f"⚠️ Windsurf Watcher failed: {e}")

        # Continue.dev Watcher
        if self.config.watcher_continue_dev and self.config.watcher_continue_dev.enabled:
            try:
                watcher = ContinueWatcher(
                    watch_path=self.config.watcher_continue_dev.path,
                    debounce_seconds=self.config.watcher_continue_dev.debounce_seconds,
                )
                self.register_watcher(watcher)
                print(f"✅ Continue Watcher initialized: {watcher.watch_path}")
            except Exception as e:
                print(f"⚠️ Continue Watcher failed: {e}")

        # State Watcher
        if self.config.watcher_state and self.config.watcher_state.enabled:
            try:
                watcher = StateWatcher(
                    project_path=self.config.watcher_state.path,
                    interval_seconds=self.config.watcher_state.debounce_seconds,
                )
                self.register_watcher(watcher)
                print(f"✅ State Watcher initialized: {watcher.watch_path}")
            except Exception as e:
                print(f"⚠️ State Watcher failed: {e}")

    def register_watcher(self, watcher: BaseWatcher) -> None:
        """Register a new watcher"""
        # Check for duplicates
        for w in self._watchers:
            if w.name == watcher.name and w.watch_path == watcher.watch_path:
                logger.warning(
                    f"Watcher {watcher.name} for {watcher.watch_path} already registered"
                )
                return

        # Connect callback
        watcher.on_new_data(self._on_raw_data)
        self._watchers.append(watcher)

    def _on_raw_data(self, raw_data) -> None:
        """Callback for new data from watchers"""
        if self._pipeline:
            try:
                self._pipeline.process(raw_data)
            except Exception as e:
                logger.error(f"Pipeline processing failed: {e}")

    def start(self) -> None:
        """Start the daemon and all watchers"""
        if self._is_running:
            logger.warning("Daemon is already running")
            return

        logger.info("🚀 Starting Dimcause Daemon...")
        logger.info(f"📂 Data directory: {self.config.data_dir}")
        logger.info(f"👁️ Watchers: {len(self._watchers)}")

        # Recover pending tasks
        self._recover_pending()

        # Start all watchers
        for watcher in self._watchers:
            try:
                watcher.start()
                logger.info(f"  ▶️ {watcher.name} started")
            except Exception as e:
                logger.error(f"  ❌ {watcher.name} failed: {e}")

        self._is_running = True
        self._start_time = datetime.now()

        logger.info("✅ Dimcause Daemon is running.")

    def stop(self) -> None:
        """Stop the daemon and all watchers"""
        if not self._is_running:
            return

        logger.info("⏹️ Stopping Dimcause Daemon...")

        for watcher in self._watchers:
            try:
                watcher.stop()
                logger.info(f"  ⏹️ {watcher.name} stopped")
            except Exception as e:
                logger.error(f"  ⚠️ Error stopping {watcher.name}: {e}")

        self._is_running = False

        if self._start_time:
            uptime = datetime.now() - self._start_time
            stats = self._pipeline.get_stats() if self._pipeline else {}
            logger.info("📊 Session Stats:")
            logger.info(f"  Uptime: {uptime}")
            logger.info(f"  Events processed: {stats.get('event_count', 0)}")

        logger.info("✅ Dimcause Daemon stopped")

    def run(self) -> None:
        """Run the daemon (blocking)"""
        self.start()

        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self._is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def status(self) -> Dict:
        """Return daemon status information"""
        pipeline_stats = self._pipeline.get_stats() if self._pipeline else {}
        return {
            "is_running": self._is_running,
            "watchers": [w.name for w in self._watchers],
            "watcher_status": {w.name: w.is_running for w in self._watchers},
            "stats": pipeline_stats,
            "event_count": pipeline_stats.get("event_count", 0),
            "start_time": self._start_time.isoformat() if self._start_time else None,
        }

    # === 兼容属性（旧接口） ===

    @property
    def _markdown_store(self):
        return self._pipeline.markdown_store if self._pipeline else None

    @property
    def _vector_store(self):
        return self._pipeline.vector_store if self._pipeline else None

    @property
    def _graph_store(self):
        return self._pipeline.graph_store if self._pipeline else None

    @property
    def _ast_analyzer(self):
        return getattr(self._pipeline, "ast_analyzer", None) if self._pipeline else None

    @property
    def _event_count(self):
        """兼容属性：返回已处理事件数"""
        stats = self._pipeline.get_stats() if self._pipeline else {}
        return stats.get("event_count", 0)

    def _save_event(self, event) -> None:
        """兼容方法：委托给 pipeline._save_event"""
        if self._pipeline:
            self._pipeline._save_event(event)


DimcauseDaemon = DaemonManager  # 向后兼容别名


def create_daemon(config: Optional[DimcauseConfig] = None) -> DaemonManager:
    """Factory to create a DaemonManager instance"""
    return DaemonManager(config=config)
