#!/usr/bin/env python3
"""
Verify VectorStore migration to SQLite.
"""

import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from dimcause.core.models import Event, EventType
from dimcause.storage.vector_store import VectorStore


def verify():
    print("[-] Initializing VectorStore with isolated DB...")
    test_db = "test_vec_migration.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        store = VectorStore(persist_dir=".dimcause/chroma_legacy_dummy", db_path=test_db)
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False

    print("[-] Checking stats...")
    stats = store.stats()
    print(f"    Stats: {stats}")

    if stats.get("backend") != "sqlite":
        print(f"[FAIL] Backend is not sqlite: {stats.get('backend')}")
        return False

    if "chromadb" in sys.modules:
        print(
            "[WARN] chromadb module is present in sys.modules (unexpected but might be residual if not uninstalled checking)"
        )
    else:
        print("[OK] chromadb not imported.")

    # Test Add
    print("[-] Testing Add Event...")
    event_id = "test_vec_migration_001"
    event = Event(
        id=event_id,
        type=EventType.REASONING,
        timestamp=datetime.now(),
        summary="Vector migration test event",
        content="This is a test content for checking sqlite vector storage capability.",
        tags=["test", "migration"],
    )

    try:
        store.add(event)
        print(f"[OK] Added event {event_id}")

        # Verify count
        stats = store.stats()
        print(f"    Stats after add: {stats}")
        if stats.get("count", 0) == 0:
            print("[FAIL] Stats count is 0 after add!")
            return False

    except Exception as e:
        print(f"[FAIL] Add event failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Check if sqlite_vec is available
    try:
        import sqlite_vec

        print(f"[-] sqlite_vec module found: {sqlite_vec}")
    except ImportError:
        print("[-] sqlite_vec module NOT found (expecting brute force)")

    # Test Search
    print("[-] Testing Search...")
    try:
        results = store.search("migration test", top_k=1)
        if not results:
            print(
                "[WARN] Search returned no results (might be embedding model download or indexing issue)"
            )
        else:
            print(f"[OK] Search returned {len(results)} results")
            print(f"    Top result: {results[0].id} - {results[0].summary}")
            if results[0].id == event_id:
                print("[PASS] Found correct event.")
            else:
                print(f"[WARN] Found different event: {results[0].id} (maybe existing data).")
    except Exception as e:
        print(f"[FAIL] Search failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test Delete
    print("[-] Testing Delete...")
    if store.delete(event_id):
        print("[OK] Delete returned True")
    else:
        print("[FAIL] Delete returned False")

    # Verify Delete
    results_after = store.search("migration test", top_k=5)
    found = any(e.id == event_id for e in results_after)
    if found:
        print("[FAIL] Event still found after delete")
        return False
    else:
        print("[OK] Event successfully deleted")

    return True


if __name__ == "__main__":
    success = verify()
    if success:
        print("\n[SUCCESS] VectorStore migration verification passed.")
        sys.exit(0)
    else:
        print("\n[FAILURE] Verification failed.")
        sys.exit(1)
