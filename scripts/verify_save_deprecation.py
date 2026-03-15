import warnings

from dimcause.storage.graph_store import GraphStore

# Filter warnings to ensure we see it
warnings.simplefilter("always", DeprecationWarning)

print("[-] Testing GraphStore.save() deprecation...")
gs = GraphStore()
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    gs.save()
    if len(w) > 0:
        print(f"[OK] Caught {len(w)} warnings")
        print(f"    Message: {w[-1].message}")
        assert issubclass(w[-1].category, DeprecationWarning)
        print("[SUCCESS] Deprecation warning verified.")
    else:
        print("[FAIL] No warning caught!")
        exit(1)
