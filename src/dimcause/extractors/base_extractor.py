from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseExtractor(ABC):
    """
    Abstract base class for all file content extractors.
    Responsibility: Convert a file diff (from StateWatcher) into a semantic explanation.
    """

    @abstractmethod
    async def extract_diff(
        self, file_path: str, old_content: bytes, new_content: bytes
    ) -> Dict[str, Any]:
        """
        Analyze the difference between old and new content.
        Returns a dictionary containing:
        - summary: A human-readable summary of the change
        - structured_diff: A structured representation (e.g., list of changed rows)
        - tags: Key concepts found in the change
        """
        pass


class TextExtractor(BaseExtractor):
    """Simple text-based diff extractor (Free Tier)"""

    async def extract_diff(
        self, file_path: str, old_content: bytes, new_content: bytes
    ) -> Dict[str, Any]:
        # Simple placeholder for text logic
        return {
            "summary": f"Text file {file_path} changed.",
            "structured_diff": {"type": "text", "lines_changed": 0},  # To be implemented
            "tags": ["text_change"],
        }
