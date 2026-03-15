import sys
import time
from unittest.mock import MagicMock

from dimcause.core.models import Event, EventType, SourceType
from dimcause.search.engine import SearchEngine


def test_graph_search():
    print("Testing Graph Search...")

    # 1. Setup Mock GraphStore
    mock_graph_store = MagicMock()
    # Mock get_file_history returning a list of event IDs
    mock_graph_store.get_file_history.return_value = ["event_1", "event_2"]
    # Mock underlying graph for complex queries (optional, mainly verifying heuristic 1)
    mock_graph_store._graph = MagicMock()
    mock_graph_store._graph.has_node.return_value = False

    # Mock get_event_metadata
    mock_graph_store.get_event_metadata.side_effect = (
        lambda eid: {"markdown_path": f"/tmp/{eid}.md"} if eid == "event_1" else None
    )

    # 2. Setup Mock MarkdownStore
    mock_md_store = MagicMock()

    def load_side_effect(path):
        if path == "/tmp/event_1.md":
            return Event(
                id="event_1",
                type=EventType.GIT_COMMIT,
                source=SourceType.FILE,
                timestamp=time.time(),
                date="2026-01-01",
                summary="Fix bug",
                content="Fixed logic",
            )
        return None

    mock_md_store.load.side_effect = load_side_effect

    # 3. Initialize Engine
    engine = SearchEngine(
        markdown_store=mock_md_store, vector_store=MagicMock(), graph_store=mock_graph_store
    )

    # 4. Run Search
    query = "src/main.py"
    results = engine.search(query, mode="graph", top_k=5)

    # 5. Verify
    print(f"Results found: {len(results)}")
    if len(results) == 1 and results[0].id == "event_1":
        print("PASSED: Graph search returned expected event.")
    else:
        print(f"FAILED: Expected 1 event (event_1), got {len(results)}")
        sys.exit(1)


if __name__ == "__main__":
    test_graph_search()
