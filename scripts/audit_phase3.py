import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "dimcause"
TEST_DIR = PROJECT_ROOT / "tests"


def check_hardcoded_paths():
    print("\n🔍 Checking for hardcoded paths...")
    user_path_pattern = re.compile(r"/Users/mini/")

    issues = []
    for path in SRC_DIR.rglob("*.py"):
        if path.name == "config.py":
            continue  # Config might have defaults
        try:
            content = path.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if user_path_pattern.search(line):
                    issues.append(f"{path.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
        except Exception as e:
            print(f"Error reading {path}: {e}")

    if issues:
        print("❌ Found hardcoded paths:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ No hardcoded paths found.")


def check_todos():
    print("\n🔍 Checking for TODOs/FIXMEs...")
    todo_pattern = re.compile(r"\b(TODO|FIXME)\b")

    count = 0
    for path in SRC_DIR.rglob("*.py"):
        try:
            content = path.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if todo_pattern.search(line):
                    print(f"{path.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
                    count += 1
        except Exception:
            pass

    print(f"ℹ️ Found {count} TODO/FIXME items.")


def check_imports():
    print("\n🔍 Checking imports (dry run)...")
    try:
        subprocess.run(["python", "-c", "import dimcause"], check=True, cwd=PROJECT_ROOT)
        print("✅ dimcause package holds importable.")
    except subprocess.CalledProcessError:
        print("❌ Failed to import dimcause.")


def verify_files_exist():
    print("\n🔍 Verifying Phase 3 files...")
    required_files = [
        "src/dimcause/core/graph_store.py",
        "src/dimcause/tui/app.py",
        "src/dimcause/tui/widgets.py",
        "src/dimcause/cli_graph.py",
    ]

    missing = []
    for f in required_files:
        if not (PROJECT_ROOT / f).exists():
            missing.append(f)

    if missing:
        print("❌ Missing files:")
        for f in missing:
            print(f"  - {f}")
    else:
        print("✅ All key Phase 3 files exist.")


if __name__ == "__main__":
    print("🚀 Starting Phase 3 Audit...")
    check_hardcoded_paths()
    check_todos()
    check_imports()
    verify_files_exist()
    print("\nAudit Complete.")
