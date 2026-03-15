import sys
import tempfile
import time
from pathlib import Path

# Ensure we can import src
sys.path.append(".")

from dimcause.reasoning.causal import CausalLink
from dimcause.core.event_index import EventIndex
from dimcause.core.models import EventMetadata, EventType, SemanticEvent, SourceType


def test_event_index_enforces_ontology():
    print("Setting up temporary DB...")
    # Use a file-based DB in temp dir to avoid any weird memory DB issues with threads (though unlikely here)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "index.db"
        index = EventIndex(db_path=str(db_path))

        print("1. Testing Valid Event (Commit realizes Decision)...")
        commits_md = Path(tmpdir) / "test_commit.md"
        commits_md.write_text("---")

        valid_event = SemanticEvent(
            id="test_commit_1",
            type=EventType.COMMIT,
            source=SourceType.GIT,
            timestamp=time.time(),
            date="2026-01-01",
            summary="Fix bug",
            tags=["fix"],
            markdown_path=str(commits_md),
            mtime=time.time(),
            metadata=EventMetadata(),
            causal_links=[
                CausalLink(source="test_commit_1", target="decision_1", relation="realizes")
            ],
        )

        try:
            added = index.add(valid_event, str(commits_md))
            if not added:
                print("FAILED: valid event was not added.")
                sys.exit(1)
            print("PASSED: Valid event added.")
        except Exception as e:
            print(f"FAILED: valid event raised exception: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

        print("2. Testing Invalid Event (Commit causes Decision)...")
        invalid_event = SemanticEvent(
            id="test_commit_2",
            type=EventType.COMMIT,
            source=SourceType.GIT,
            timestamp=time.time(),
            date="2026-01-01",
            summary="Bad commit",
            tags=["bad"],
            markdown_path=str(commits_md),
            mtime=time.time(),
            metadata=EventMetadata(),
            causal_links=[
                CausalLink(source="test_commit_2", target="decision_2", relation="causes")
            ],
        )

        try:
            index.add(invalid_event, str(commits_md))
            print("FAILED: Invalid event was NOT rejected (expected ValueError).")
            sys.exit(1)
        except ValueError as e:
            if "Ontology Violation" in str(e):
                print(f"PASSED: Caught expected ValueError: {e}")
            else:
                print(f"FAILED: Caught ValueError but message mismatch: {e}")
                sys.exit(1)
        except Exception as e:
            print(f"FAILED: Caught unexpected exception: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    test_event_index_enforces_ontology()
