"""
Reranker Module

负责对初步检索结果（Text/Vector/Hybrid）进行重排序，提升 Top-K 准确率。
"""

import logging
from typing import List, Optional

from rich.console import Console

from dimcause.core.models import Event, get_model_config

logger = logging.getLogger(__name__)
console = Console()


class Reranker:
    """
    语义重排序器

    使用 Cross-Encoder 模型对 (Query, Document) 对进行打分。
    """

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Reranker, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Singleton init check
        if self._model is not None:
            return

        self.config = get_model_config()
        self.model_name = self.config.rerank_model

        try:
            import os

            from sentence_transformers import CrossEncoder

            # 临时强制离线模式：阻止 transformers tokenizer (XLMRobertaTokenizer) 在
            # local_files_only=True 时仍触发 is_base_mistral() → HF Hub 联网检查。
            # 使用 try/finally 确保加载完毕后恢复原始值，不污染进程其他模块。
            _prev = os.environ.get("HF_HUB_OFFLINE")
            os.environ["HF_HUB_OFFLINE"] = "1"
            try:
                # 1. First Code Path: Try standard local load
                try:
                    self._model = CrossEncoder(
                        self.model_name, max_length=512, local_files_only=True
                    )
                    logger.info(f"Loaded Reranker model (Standard Local): {self.model_name}")
                except Exception as e:
                    # 2. Second Code Path: Manual Snapshot Resolution (Backdoor for China/Offline)
                    # sentence-transformers sometimes tries to phone home even with local_files_only=True
                    # if the cache structure is slightly off. We force it by using the absolute path.
                    snapshot_path = self._resolve_local_path(self.model_name)
                    if snapshot_path:
                        console.print(f"[dim]Fallback: Loading from snapshot {snapshot_path}...[/]")
                        try:
                            self._model = CrossEncoder(
                                snapshot_path, max_length=512, local_files_only=True
                            )
                            logger.info(f"Loaded Reranker model (Snapshot Path): {self.model_name}")
                        except Exception as e2:
                            console.print(f"[red]Fallback load failed: {e2}[/]")
                            self._model = None
                    else:
                        # 3. Final Failure
                        console.print(
                            f"[yellow]Warning: Local Reranker model {self.model_name} not found.[/]"
                        )
                        console.print(
                            "[dim]Please run 'python scripts/download_models_cn.py' to fix.[/]"
                        )
                        logger.warning(f"Reranker load failed: {e}")
                        self._model = None
            finally:
                if _prev is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = _prev

        except ImportError:
            console.print(
                "[yellow]Warning: sentence-transformers not installed. Reranker disabled.[/]"
            )
            self._model = None
        except Exception as e:
            console.print(f"[red]Failed to load Reranker model: {e}[/]")
            self._model = None

    def _resolve_local_path(self, model_id: str) -> Optional[str]:
        """
        Manually resolve HuggingFace cache path to bypass 'connection error'
        when local_files_only=True fails.
        """
        import os

        try:
            # Standard HF Cache Structure
            cache_dir = os.path.expanduser(
                f"~/.cache/huggingface/hub/models--{model_id.replace('/', '--')}"
            )
            refs_path = os.path.join(cache_dir, "refs", "main")

            if os.path.exists(refs_path):
                with open(refs_path, "r") as f:
                    commit_hash = f.read().strip()
                snapshot_path = os.path.join(cache_dir, "snapshots", commit_hash)
                if os.path.exists(snapshot_path):
                    return snapshot_path
        except Exception:
            pass
        return None

    @classmethod
    def release_model(cls) -> None:
        """
        释放 Reranker 模型，归还 MPS/GPU 内存（用完即释放策略）

        遵循 RT-000 §4.2 设计：Embedding 和 Reranker 不同时驻留内存。
        释放后，下次调用 get_reranker() 会重新加载模型。
        """
        import gc

        if cls._instance is not None and cls._model is not None:
            try:
                # 先移回 CPU，再删除（确保 MPS 内存被释放）
                cls._model.model = cls._model.model.to("cpu")
            except Exception:
                pass
            del cls._model
            cls._model = None
            # 重置 Singleton，允许下次重新初始化
            cls._instance = None
            gc.collect()
            try:
                import torch

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                    torch.mps.synchronize()
            except Exception:
                pass

    def rank(self, query: str, events: List[Event], top_k: int = 10) -> List[Event]:
        """
        对 Events 进行重排序

        Args:
            query: 搜索查询
            events: 候选事件列表
            top_k: 返回数量

        Returns:
            排序后的 Top-K 事件
        """
        if not self._model or not events:
            return events[:top_k]

        # 准备 (Query, Text) 对
        # 使用 summary + content 作为文档内容，截断以适应模型
        pairs = []
        for event in events:
            # 组合文本：Title + Content
            text = f"{event.summary}\n{event.content}"
            # 简单截断，防止过长 (虽然 CrossEncoder 有 max_length，但预处理好些)
            if len(text) > 2000:
                text = text[:2000]
            pairs.append([query, text])

        try:
            # Predict scores
            scores = self._model.predict(pairs)

            # 组合 (Event, Score)
            scored_events = list(zip(events, scores, strict=False))

            # 按分数降序排序
            scored_events.sort(key=lambda x: x[1], reverse=True)

            # 返回 Event 对象
            return [e for e, s in scored_events[:top_k]]

        except Exception as e:
            logger.error(f"Rerank failed: {e}")
            return events[:top_k]


def get_reranker() -> Reranker:
    """获取单例 Reranker"""
    return Reranker()
