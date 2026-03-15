import os
import sys

# Ensure src is in python path
sys.path.insert(0, os.path.abspath("src"))

print("Verifying imports...")

try:
    import dimcause.watchers  # noqa: F401

    print("✅ dimcause.watchers imported")

    import dimcause.watchers.base  # noqa: F401

    print("✅ dimcause.watchers.base imported")

    import dimcause.watchers.claude_watcher  # noqa: F401

    print("✅ dimcause.watchers.claude_watcher imported")

    import dimcause.watchers.cursor_watcher  # noqa: F401

    print("✅ dimcause.watchers.cursor_watcher imported")

    import dimcause.watchers.windsurf_watcher  # noqa: F401

    print("✅ dimcause.watchers.windsurf_watcher imported")

    import dimcause.audit.engine  # noqa: F401

    print("✅ dimcause.audit.engine imported")

    import dimcause.audit.runner  # noqa: F401

    print("✅ dimcause.audit.runner imported")

    import dimcause.audit.checks.security  # noqa: F401

    print("✅ dimcause.audit.checks.security imported")

    import dimcause.audit.result  # noqa: F401

    print("✅ dimcause.audit.result imported")

    print("All imports successful!")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
