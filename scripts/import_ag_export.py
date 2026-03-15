#!/usr/bin/env python3
"""
AG Export Auto-Importer
Automatically imports Antigravity exported conversations into MAL logs.

Usage:
    python3 scripts/import_ag_export.py
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Paths
AG_EXPORT_DIR = Path.home() / "Documents" / "AG_EXPORT"
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "docs" / "logs"


def main():
    print("🔍 Scanning AG_EXPORT directory...\n")

    if not AG_EXPORT_DIR.exists():
        print(f"❌ AG_EXPORT directory not found: {AG_EXPORT_DIR}")
        print("   Please export your Antigravity conversations first.")
        sys.exit(1)

    # Get all markdown files
    md_files = list(AG_EXPORT_DIR.glob("*.md"))
    if not md_files:
        print(f"📭 No .md files found in {AG_EXPORT_DIR}")
        print("   Export your conversations and try again.")
        return

    # Prepare target directory (today's date)
    today = datetime.now()
    target_dir = LOGS_DIR / today.strftime("%Y") / today.strftime("%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Source: {AG_EXPORT_DIR}")
    print(f"📂 Target: {target_dir}\n")

    # Import files
    imported_count = 0
    for md_file in md_files:
        dest_name = f"ag_{md_file.name}"
        dest_path = target_dir / dest_name

        if dest_path.exists():
            print(f"⏭️  Skipped (already exists): {md_file.name}")
            continue

        shutil.copy2(md_file, dest_path)
        print(f"✅ Imported: {md_file.name} → {dest_name}")
        imported_count += 1

    print(f"\n✨ Imported {imported_count} file(s)")

    if imported_count > 0:
        print("\n🔄 Running MAL indexer...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

        result = subprocess.run(
            [sys.executable, "-m", "dimcause.cli", "index"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ Index updated successfully!")
        else:
            print("⚠️  Indexing completed with warnings")
            if result.stderr:
                print(f"   {result.stderr[:200]}")

    print("\n" + "=" * 50)
    print("🎉 All done! Your Antigravity conversations are now in MAL.")
    print("\nNext step:")
    print("  PYTHONPATH=src python3 -m dimcause.cli daily-end")
    print("=" * 50)


if __name__ == "__main__":
    main()
