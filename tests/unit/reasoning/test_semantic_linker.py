from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dimcause.core.models import Event, EventType
from dimcause.reasoning.semantic_linker import SemanticLinker


class TestSemanticLinker:
    @pytest.fixture
    def mock_model(self):
        with patch("dimcause.reasoning.semantic_linker.ModelManager.load") as mock_load:
            model = MagicMock()
            mock_load.return_value = model
            yield model

    def create_event(self, id, type, summary):
        return Event(id=id, type=type, timestamp=datetime.now(), summary=summary, content=summary)

    def test_link_high_similarity(self, mock_model):
        # Mock embeddings: e1 and e2 are identical (sim=1.0)
        # e1=[1, 0], e2=[1, 0]
        mock_model.encode.return_value = np.array([[1.0, 0.0], [1.0, 0.0]])

        linker = SemanticLinker()
        e1 = self.create_event("d1", EventType.DECISION, "Data privacy")
        e2 = self.create_event("r1", EventType.REQUIREMENT, "GDPR compliance")

        links = linker.link([e1, e2], threshold=0.9)

        assert len(links) == 1
        link = links[0]
        # logic: Decision implements Requirement
        # d1 is Decision, r1 is Requirement. So d1 -> r1
        assert link.source == "d1"
        assert link.target == "r1"
        assert link.relation == "implements"
        assert link.weight >= 0.99

    def test_link_low_similarity(self, mock_model):
        # Mock orthogonal embeddings (sim=0.0)
        mock_model.encode.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

        linker = SemanticLinker()
        e1 = self.create_event("d1", EventType.DECISION, "A")
        e2 = self.create_event("d2", EventType.DECISION, "B")

        links = linker.link([e1, e2], threshold=0.5)
        assert len(links) == 0

    def test_direction_swap(self, mock_model):
        # e1=Req, e2=Dec. High sim.
        # Should result in Dec -> Req (implements)
        mock_model.encode.return_value = np.array([[0.707, 0.707], [0.707, 0.707]])

        linker = SemanticLinker()
        e1 = self.create_event("r1", EventType.REQUIREMENT, "Req")
        e2 = self.create_event("d1", EventType.DECISION, "Dec")

        links = linker.link([e1, e2])
        assert len(links) == 1
        assert links[0].source == "d1"  # Decision
        assert links[0].target == "r1"  # Requirement
