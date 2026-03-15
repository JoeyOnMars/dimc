"""
Daemon Entrypoint
Executed by the background process.
"""

import logging
import sys

from dimcause.daemon.manager import DaemonManager
from dimcause.daemon.process import process_manager


def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=os.path.expanduser("~/.dimcause/daemon.log"),
    )

    # Write PID
    try:
        process_manager.write_pid()
    except Exception as e:
        logging.error(f"Failed to write PID file: {e}")
        sys.exit(1)

    try:
        manager = DaemonManager()
        manager.run()
    except Exception as e:
        logging.critical(f"Daemon crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        process_manager.clean_pid()


if __name__ == "__main__":
    import os

    main()
