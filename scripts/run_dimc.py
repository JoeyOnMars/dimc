import sys
from pathlib import Path

# Ensure src is in Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dimcause.cli import app

if __name__ == "__main__":
    app()
