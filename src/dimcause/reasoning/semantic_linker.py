import logging
from typing import List, Optional

from dimcause.core.models import Event
from dimcause.reasoning.causal import CausalLink
from dimcause.reasoning.linker_base import BaseLinker
from dimcause.reasoning.model_manager import ModelManager
from dimcause.reasoning.relation_inference import infer_semantic_relation

logger = logging.getLogger(__name__)


class SemanticLinker(BaseLinker):
    """
    Linker using Semantic Similarity (Embedding + Cosine).
    """

    def __init__(self, model_name: str = ModelManager.DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None  # Lazy load

    @property
    def model(self):
        if self._model is None:
            self._model = ModelManager.load(self.model_name)
        return self._model

    def link(self, events: List[Event], threshold: float = 0.85) -> List[CausalLink]:
        """
        Link events based on semantic similarity.

        Args:
            events: List of events.
            threshold: Cosine similarity threshold (default 0.85).

        Returns:
            List of CausalLink.
        """
        if len(events) < 2:
            return []

        # 1. Prepare texts
        # We combine summary + content for embedding
        texts = [f"{e.summary}\n{e.content}" for e in events]
        [e.id for e in events]

        # 2. Encode
        # convert_to_tensor=True for pytorch optimizations if needed,
        # but numpy is easier for simple dot product here
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        # 3. Compute Similarity Matrix (Dot product of normalized vectors = Cosine Sim)
        # Shape: (N, N)
        similarity_matrix = embeddings @ embeddings.T

        links: List[CausalLink] = []
        n = len(events)

        # 4. Iterate upper triangle (avoid self-loops and duplicates)
        for i in range(n):
            for j in range(i + 1, n):
                score = float(similarity_matrix[i][j])

                if score >= threshold:
                    # Decide direction? Semantic similarity is symmetric.
                    # Ontology requires specific relations. "related_to" is generic.
                    # Logic:
                    # If (Decision, Requirement) -> implements
                    # If (Commit, Decision) -> realizes
                    # If same type (Decision, Decision) -> relates_to
                    # For now, we use a generic "related_to" unless we detect specific types.

                    source = events[i]
                    target = events[j]

                    inferred = self._infer_relation(source, target)
                    if inferred is None:
                        continue

                    relation, source, target = inferred

                    # Ensure directionality matches Ontology
                    # e.g. implements(Decision, Requirement)
                    link = CausalLink(
                        source=source.id,
                        target=target.id,
                        relation=relation,
                        weight=score,
                        metadata={
                            "strategy": "semantic",
                            "model": self.model_name,
                            "similarity": score,
                        },
                    )
                    links.append(link)
                    logger.debug(
                        f"Linked {source.id} --{relation}--> {target.id} (score={score:.4f})"
                    )

        return links

    def _infer_relation(self, e1: Event, e2: Event) -> Optional[tuple[str, Event, Event]]:
        """Infer only ontology-backed relations; return None when no valid relation exists."""
        return infer_semantic_relation(e1, e2)
