from unittest.mock import MagicMock, patch

import pytest

from dimcause.reasoning.model_manager import ModelManager


class TestModelManager:
    @patch("dimcause.reasoning.model_manager.torch.backends.mps.is_available")
    @patch("dimcause.reasoning.model_manager.torch.cuda.is_available")
    def test_get_device_mps(self, mock_cuda, mock_mps):
        mock_mps.return_value = True
        mock_cuda.return_value = False
        assert ModelManager.get_device() == "mps"

    @patch("dimcause.reasoning.model_manager.torch.backends.mps.is_available")
    @patch("dimcause.reasoning.model_manager.torch.cuda.is_available")
    def test_get_device_cpu(self, mock_cuda, mock_mps):
        mock_mps.return_value = False
        mock_cuda.return_value = False
        assert ModelManager.get_device() == "cpu"

    @patch("dimcause.reasoning.model_manager.SentenceTransformer")
    def test_ensure_model_success(self, mock_cls):
        # Setup
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        # Action
        result = ModelManager.ensure_model("test/model")

        # Check
        assert result == "test/model"
        mock_cls.assert_called_once()

    @patch("dimcause.reasoning.model_manager.SentenceTransformer")
    def test_ensure_model_failure(self, mock_cls):
        # Setup
        mock_cls.side_effect = Exception("Download failed")

        # Action & Check
        with pytest.raises(RuntimeError, match="Could not download/load model"):
            ModelManager.ensure_model("test/fail")
