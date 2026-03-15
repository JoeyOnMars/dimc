from abc import ABC, abstractmethod
from typing import List

from dimcause.core.models import Event
from dimcause.reasoning.causal import CausalLink


class BaseLinker(ABC):
    """
    Abstract base class for all Causal Linkers (Heuristic, Semantic, etc.).
    Follows the Strategy Pattern.
    """

    @abstractmethod
    def link(self, events: List[Event], **kwargs) -> List[CausalLink]:
        """
        Analyze a list of events and infer causal links.

        Args:
            events: List of events to analyze.
            **kwargs: Additional configuration (e.g., time window, threshold).

        Returns:
            List of inferred CausalLink objects.
        """
        pass
