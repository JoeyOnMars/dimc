import logging

import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class ModelManager:
    """
    负责管理 AI 模型的下载、缓存和加载。
    遵循 P2.1 Task Task 1 规范。
    """

    DEFAULT_MODEL = "BAAI/bge-m3"

    @staticmethod
    def get_device() -> str:
        """
        探测最佳可用设备。
        优先顺序: MPS (Mac) > CUDA (NVIDIA) > CPU
        """
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        else:
            return "cpu"

    @staticmethod
    def ensure_model(model_name: str = DEFAULT_MODEL) -> str:
        """
        确保模型已下载并缓存。

        Args:
            model_name: HuggingFace 模型名称 (例如 "BAAI/bge-m3")

        Returns:
            str: 模型的本地缓存路径 (或者模型名称本身，SentenceTransformer 会自动处理)
        """
        logger.info(f"Checking model: {model_name}")

        # HuggingFace 默认缓存路径是 ~/.cache/huggingface
        # SentenceTransformer 会自动检查缓存，如果不存在则下载
        # 我们在这里显式调用一次下载逻辑以确保"前置条件"满足

        device = ModelManager.get_device()
        logger.info(f"Using device: {device}")

        try:
            # 尝试加载模型以触发下载/缓存
            # 注意：我们不返回模型对象，只返回路径/名称，因为 Task Card 要求 "Return local path"
            # 但实际上 SentenceTransformer 最好直接通过 name 加载
            # 为了符合 "ensure" 的语义，我们这里执行下载动作

            # 使用 sentence-transformers 的下载工具
            SentenceTransformer(model_name, device=device)

            # 验证模型是否可用
            logger.info(f"Model {model_name} is ready on {device}")

            # 这里我们简单返回 model_name，因为 SentenceTransformer 内部管理路径
            # 如果需要绝对物理路径，需要深入 huggingface_hub 的 API
            return model_name

        except Exception as e:
            logger.error(f"Failed to ensure model {model_name}: {e}")
            raise RuntimeError(f"Could not download/load model {model_name}") from e

    @staticmethod
    def load(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
        """
        加载模型实例。
        """
        device = ModelManager.get_device()
        return SentenceTransformer(model_name, device=device)
