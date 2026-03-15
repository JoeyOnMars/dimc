from typing import Any, Dict

from dimcause.extractors.base_extractor import BaseExtractor


class VisionExtractorPrototype(BaseExtractor):
    """
    PROTOTYPE: Vision Extractor for Image/Video analysis.
    Status: Feature-Gated (Enterprise Feature).

    In a real implementation, this would call GPT-4o or Claude 3.5 Sonnet Vision.
    Here, it serves as a placeholder to prove architectural extensibility.
    """

    async def extract_diff(
        self, file_path: str, old_content: bytes, new_content: bytes
    ) -> Dict[str, Any]:
        # MOCK LOGIC: Simulate an AI analyzing an image
        return {
            "summary": "Visual Element Changed: Button color shifted from Blue to Red.",
            "structured_diff": {
                "type": "vision",
                "objects_detected": ["button", "login_form"],
                "change_type": "style_update",
            },
            "tags": ["ui_change", "vision_analysis"],
            "ai_model": "mock-vision-model-v1",
        }


class ExcelExtractorPrototype(BaseExtractor):
    """
    PROTOTYPE: Data Extractor for Spreadsheets.
    Status: Feature-Gated (Pro Feature).
    """

    async def extract_diff(
        self, file_path: str, old_content: bytes, new_content: bytes
    ) -> Dict[str, Any]:
        # MOCK LOGIC: Simulate pandas comparison
        return {
            "summary": "Price Update: Product 'A123' changed from $10 to $9.",
            "structured_diff": {
                "type": "tabular",
                "rows_modified": 1,
                "columns_affected": ["Price"],
            },
            "tags": ["price_change", "data_update"],
        }
