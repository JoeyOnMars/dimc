# -*- coding: utf-8 -*-
"""
Seed and Export Data for Verification
"""

from pathlib import Path

from dimcause.core.models import Entity
from dimcause.storage.graph_store import GraphStore


def main():
    db_path = "verification.db"
    jsonld_path = "verification.jsonld"

    # Clean up
    Path(db_path).unlink(missing_ok=True)

    print(f"Seeding {db_path}...")
    store = GraphStore(db_path=db_path)

    import json

    # 1. Add Requirement
    req = Entity(
        name="req_001",
        type="requirement",
        context=json.dumps({"summary": "Support JSON-LD Export", "priority": "P1"}),
    )
    store.add_entity(req)

    # 2. Add Decision
    dec = Entity(
        name="dec_001",
        type="decision",
        context=json.dumps({"summary": "Use schema.org and prov-o", "status": "accepted"}),
    )
    store.add_entity(dec)

    # 3. Add Relation
    store.add_relation("dec_001", "req_001", "implements")

    print("Exporting to JSON-LD...")
    # Using CLI command logic directly or via subprocess?
    # Let's use subprocess to test CLI integration too,
    # but for simplicity here I'll just use the store to verify content first.

    # Actually, verify_jsonld_consumer expects a file.
    # Let's run the actual export command via os.system or subprocess
    import os

    ret = os.system(f"python -m dimcause.cli export jsonld --db-path {db_path} --out {jsonld_path}")

    if ret == 0:
        print(f"Successfully exported to {jsonld_path}")
    else:
        print("Export failed")


if __name__ == "__main__":
    main()
