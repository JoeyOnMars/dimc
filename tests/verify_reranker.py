import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path.cwd() / "src"))

from dimcause.core.models import Event, EventType
from dimcause.search.reranker import Reranker


class TestReranker(unittest.TestCase):
    def setUp(self):
        # Reset singleton if needed, though Reranker is singleton
        # We can just patch the _model instance on the singleton
        self.reranker = Reranker()

    def test_rank_logic(self):
        # Mock the model
        mock_model = MagicMock()
        # Simulate scores for 3 events: [0.1, 0.9, 0.5]
        # Expect order: Event 2 (0.9), Event 3 (0.5), Event 1 (0.1)
        mock_model.predict.return_value = [0.1, 0.9, 0.5]

        self.reranker._model = mock_model

        events = [
            Event(
                id="1",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="Low score",
                content="Low",
            ),
            Event(
                id="2",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="High score",
                content="High",
            ),
            Event(
                id="3",
                type=EventType.DECISION,
                timestamp=datetime.now(),
                summary="Mid score",
                content="Mid",
            ),
        ]

        sorted_events = self.reranker.rank("query", events, top_k=3)

        self.assertEqual(len(sorted_events), 3)
        self.assertEqual(sorted_events[0].id, "2")
        self.assertEqual(sorted_events[1].id, "3")
        self.assertEqual(sorted_events[2].id, "1")
        print("[Pass] Reranker sorted events correctly by score")

    def test_empty_input(self):
        self.reranker._model = MagicMock()
        res = self.reranker.rank("query", [], top_k=5)
        self.assertEqual(res, [])
        print("[Pass] Empty input handled")


if __name__ == "__main__":
    unittest.main()
