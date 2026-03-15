"""
Dimcause Daemon Process Management
Handles process detachment, PID file management, and signal handling.
"""

import atexit
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Manages the daemon process lifecycle (start, stop, status).
    """

    def __init__(self, pid_file: Optional[str] = None):
        if pid_file:
            self.pid_file = os.path.expanduser(pid_file)
        else:
            env_pid = os.environ.get("DIMCAUSE_PID_FILE")
            if env_pid:
                self.pid_file = os.path.expanduser(env_pid)
            else:
                self.pid_file = os.path.expanduser("~/.dimcause/daemon.pid")

    def is_running(self) -> bool:
        """Check if daemon is running by PID file and process existence."""
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except OSError:
            # Process dead but PID file exists
            return False

    def get_pid(self) -> Optional[int]:
        """Read PID from file."""
        if not os.path.exists(self.pid_file):
            return None

        try:
            with open(self.pid_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            return None

    def start_daemon(self) -> None:
        """
        Start the daemon in background.
        Uses subprocess to detach.
        """
        if self.is_running():
            print(f"⚠️ Daemon is already running (PID: {self.get_pid()})")
            return

        print("🚀 Starting Dimcause Daemon (Background)...")

        # Prepare command
        # Assumes 'mal' is in path, or use sys.executable + script
        # Using sys.executable to ensure same python environment
        cmd = [sys.executable, "-m", "dimcause.daemon.entrypoint"]

        try:
            # Detach process
            # start_new_session=True sets setsid()
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.getcwd(),
            )

            # Wait a bit to ensure it started (PID file creation happens in entrypoint)
            # We can't easily wait for file here without blocking, so we trust Popen returned.
            print("✅ Daemon started in background.")
            print("   Check status with: dimc daemon status")

        except Exception as e:
            print(f"❌ Failed to start daemon: {e}")

    def stop_daemon(self) -> None:
        """Stop the running daemon."""
        pid = self.get_pid()
        if not pid:
            print("⚠️ Daemon is not running (No PID file)")
            return

        try:
            print(f"⏹️ Stopping Daemon (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)

            # Wait for exit
            for _ in range(50):  # Wait up to 5 seconds
                if not self._pid_exists(pid):
                    break
                time.sleep(0.1)

            if self._pid_exists(pid):
                print("⚠️ Daemon did not exit gracefully, forcing kill...")
                os.kill(pid, signal.SIGKILL)

            # Clean up PID file if it still exists
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)

            print("✅ Daemon stopped.")

        except OSError as e:
            print(f"❌ Error stopping daemon: {e}")
            # If process doesn't exist, just clean pid file
            if "No such process" in str(e) and os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                print("   Cleaned up stale PID file.")

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def write_pid(self) -> None:
        """Write current process PID to file (called by daemon itself)."""
        pid = os.getpid()
        pid_dir = os.path.dirname(self.pid_file)
        os.makedirs(pid_dir, exist_ok=True)

        with open(self.pid_file, "w") as f:
            f.write(str(pid))

        # Register cleanup
        atexit.register(self.clean_pid)

    def clean_pid(self) -> None:
        """Remove PID file."""
        if os.path.exists(self.pid_file):
            try:
                os.remove(self.pid_file)
            except OSError:
                pass


# Global instance
process_manager = ProcessManager()
