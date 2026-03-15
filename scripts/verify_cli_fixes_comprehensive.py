import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Mock dependencies to avoid actual execution
# crucial: mock dimcause.core.models BEFORE importing dimcause
sys.modules["dimcause.core.models"] = MagicMock()
sys.modules["dimcause.core"] = MagicMock()
sys.modules["dimcause.core.trace"] = MagicMock()
sys.modules["dimcause.ui"] = MagicMock()
sys.modules["dimcause.ui.trace_view"] = MagicMock()
sys.modules["dimcause.search"] = MagicMock()
sys.modules["dimcause.utils"] = MagicMock()
sys.modules["dimcause.utils.linter"] = MagicMock()
sys.modules["dimcause.utils.security"] = MagicMock()
sys.modules["dimcause.core.history"] = MagicMock()
sys.modules["dimcause.brain"] = MagicMock()
sys.modules["dimcause.brain.why"] = MagicMock()
sys.modules["dimcause.scheduler"] = MagicMock()  # Mock scheduler module

from dimcause.cli import (  # noqa: E402
    audit,
    history,
    scan,
    scheduler_plan,
    scheduler_run,
    search,
    trace,
    why,
)


class TestCliFixes(unittest.TestCase):
    def test_trace(self):
        print("Testing trace()...")
        try:
            trace("query")
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"trace failed: {e}")
        except Exception:
            pass

    def test_why(self):
        print("Testing why()...")
        try:
            why("target")
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"why failed: {e}")
        except Exception:
            pass

    def test_history(self):
        print("Testing history()...")
        try:
            history("file")
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"history failed: {e}")
        except Exception:
            pass

    def test_scan(self):
        print("Testing scan()...")
        try:
            scan(".")
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"scan failed: {e}")
        except Exception:
            pass

    def test_search(self):
        print("Testing search()...")
        try:
            search("query")
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"search failed: {e}")
        except Exception:
            pass

    def test_audit(self):
        print("Testing audit()...")
        try:
            audit()
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"audit failed: {e}")
        except Exception:
            pass

    def test_scheduler_plan(self):
        print("Testing scheduler_plan()...")
        try:
            scheduler_plan()
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"scheduler_plan failed: {e}")
        except Exception:
            pass

    def test_scheduler_run(self):
        print("Testing scheduler_run()...")
        try:
            scheduler_run()
        except TypeError as e:
            if "OptionInfo" in str(e):
                self.fail(f"scheduler_run failed: {e}")
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
