from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from dimcause.reasoning.causal import CausalLink
from dimcause.core.models import Event, EventType
from dimcause.reasoning.engine import HybridInferenceEngine


class TestHybridInferenceEngine:
    @pytest.fixture
    def mock_time_linker(self):
        with patch("dimcause.reasoning.engine.TimeWindowLinker") as mock:
            instance = MagicMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_semantic_linker(self):
        with patch("dimcause.reasoning.engine.SemanticLinker") as mock:
            instance = MagicMock()
            mock.return_value = instance
            yield instance

    def create_event(self, id):
        return Event(
            id=id, type=EventType.DECISION, timestamp=datetime.now(), summary="test", content="test"
        )

    def test_infer_aggregation(self, mock_time_linker, mock_semantic_linker):
        # Setup
        engine = HybridInferenceEngine()
        events = [self.create_event("e1"), self.create_event("e2")]

        # Mock results
        link1 = CausalLink(source="e1", target="e2", relation="triggers", weight=0.6)
        link2 = CausalLink(source="e2", target="e1", relation="related_to", weight=0.9)

        mock_time_linker.link.return_value = [link1]
        mock_semantic_linker.link.return_value = [link2]

        # Execute
        links = engine.infer(events)

        # Verify
        assert len(links) == 2
        assert link1 in links
        assert link2 in links

        # Verify calls
        mock_time_linker.link.assert_called_once_with(events)
        mock_semantic_linker.link.assert_called_once_with(events, threshold=0.85)
