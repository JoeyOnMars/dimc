"""
E2E Test: WAL Recovery
Verifies that the daemon recovers pending events from WAL on startup.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from dimcause.core.models import RawData, SourceType
from dimcause.daemon.process import process_manager
from dimcause.utils.config import CONFIG_FILENAME
from dimcause.utils.wal import WriteAheadLog

# Configuration
TEST_DIR = Path("~/tmp/dimcause_e2e_recovery").expanduser().resolve()
DIMCAUSE_CONFIG_PATH = TEST_DIR / CONFIG_FILENAME
DIMCAUSE_DATA_DIR = TEST_DIR / ".dimcause"
WAL_DIR = DIMCAUSE_DATA_DIR / "wal"


def setup():
    """Setup test environment"""
    if TEST_DIR.exists():
        import shutil

        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True)

    # Create config file
    config_data = {
        "logs_dir": ".dimcause",  # Use relative path compliant with Config
        "watcher_claude": {
            "enabled": False,
            "path": str(TEST_DIR / "dummy_log.jsonl"),  # Required schema field
        },
    }

    with open(DIMCAUSE_CONFIG_PATH, "w") as f:
        json.dump(config_data, f)


def run_test():
    print(f"📂 Setting up test env in {TEST_DIR}...")
    setup()

    # Switch CWD to test dir so daemon picks up config
    original_cwd = os.getcwd()
    os.chdir(TEST_DIR)

    # Force DIMCAUSE_ROOT to test dir to ensure config is loaded from here
    os.environ["DIMCAUSE_ROOT"] = str(TEST_DIR)
    os.environ["DIMCAUSE_PID_FILE"] = str(TEST_DIR / ".dimcause" / "dimcause.pid")

    # Reload process manager to pick up env var
    import importlib

    from dimcause.daemon import process

    importlib.reload(process)

    try:
        # 1. Pre-seed WAL with pending tasks
        print("⚡ Pre-seeding WAL with pending events...")
        wal = WriteAheadLog(wal_path=str(WAL_DIR / "active.log"))

        pending_data = RawData(
            id="recovery_test_001",
            source=SourceType.MANUAL,
            content="This event was left pending in WAL. RECOVERY_TOKEN_999",
            timestamp=datetime.now(),
        )
        wal.append_pending(pending_data.id, pending_data.model_dump())
        # Note: We do NOT call mark_done

        print(f"   Wrote pending event: {pending_data.id}")

        # 2. Start Daemon
        print("🚀 Starting Daemon (should trigger recovery)...")
        process_manager.start_daemon()

        # Wait for startup and recovery
        time.sleep(10)  # Give it time to replay and process (model load involved)

        if not process_manager.is_running():
            print("❌ Daemon failed to start")
            return False

        print("✅ Daemon running")

        # 3. Verify Processing
        print("⏳ Waiting for recovered persistence...")
        # Check Markdown storage for the token
        events_dir = DIMCAUSE_DATA_DIR / "events"

        found = False
        for _ in range(60):  # 30 seconds
            if events_dir.exists():
                for f in events_dir.rglob("*.md"):
                    content = f.read_text()
                    if "RECOVERY_TOKEN_999" in content:
                        print(f"✅ Found recovered event in: {f.name}")
                        found = True
                        break
            if found:
                break
            time.sleep(0.5)

        if not found:
            print("❌ Recovery Failed: Token not found in storage")
            return False

        # 4. Verify WAL State (Should be ACKed now)
        # We can't easily check the WAL file safely while Daemon holds lock?
        # Daemon uses RLock but in a separate process.
        # But we can check if a new ACK line was appended.
        # 4. Verify WAL State (Should be ACKed now)
        print("🔍 Checking WAL for ACK...")
        ack_found = False
        for _ in range(20):  # Retry for 10 seconds
            with open(WAL_DIR / "active.log", "r") as f:
                lines = f.readlines()
                for line in lines:
                    if '"event_type": "completed"' in line and '"id": "recovery_test_001"' in line:
                        ack_found = True
                        break
            if ack_found:
                break
            time.sleep(0.5)

        if ack_found:
            print("✅ WAL ACK record found.")
        else:
            print("❌ WAL ACK record MISSING.")
            return False

        print("✅ E2E Recovery Test Passed!")
        return True

    except Exception as e:
        print(f"❌ Test Error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # 5. Stop Daemon
        if process_manager.is_running():
            print("⏹️ Stopping Daemon...")
            process_manager.stop_daemon()

        os.chdir(original_cwd)


if __name__ == "__main__":
    success = run_test()
    if not success:
        exit(1)
